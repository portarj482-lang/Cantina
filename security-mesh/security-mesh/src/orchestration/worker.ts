import { completeAgentTask, claimAgentTask, expireAgentTaskLeases, failAgentTask, renewAgentTaskLease, type LeasedAgentTask } from './task-queue.js';

export interface AgentHandler {
  agentId: string;
  contractVersion: string;
  validateInput(input: Record<string, unknown>): boolean;
  validateOutput(output: unknown): output is Record<string, unknown>;
  run(input: Record<string, unknown>, context: { task: LeasedAgentTask; signal: AbortSignal }): Promise<Record<string, unknown>>;
}

export type WorkerOutcome = { status: 'idle' } | { status: 'completed' | 'retry_queued' | 'failed' | 'lease_lost'; taskId: string };

/** Executes only application-registered handlers; task data can never supply executable code or shell text. */
export async function processOneTask(workerId: string, handlers: ReadonlyMap<string, AgentHandler>, leaseSeconds = 120): Promise<WorkerOutcome> {
  const task = await claimAgentTask(workerId, leaseSeconds);
  if (!task) return { status: 'idle' };
  const handler = handlers.get(task.agent_id);
  if (!handler || handler.contractVersion !== task.contract_version) {
    const result = await failAgentTask(task.id, workerId, task.lease_token, 'No handler is registered for the pinned agent contract version.');
    return { status: result, taskId: task.id };
  }
  if (!handler.validateInput(task.input)) {
    const result = await failAgentTask(task.id, workerId, task.lease_token, 'Task input failed the pinned handler schema.');
    return { status: result, taskId: task.id };
  }

  const controller = new AbortController();
  const timeoutMs = Math.max(1, task.max_runtime_seconds) * 1000;
  const heartbeatMs = Math.max(5000, Math.min(30_000, Math.floor(leaseSeconds * 1000 / 3)));
  const heartbeat = setInterval(() => {
    void renewAgentTaskLease(task.id, workerId, task.lease_token, leaseSeconds).then((ok) => {
      if (!ok) controller.abort(new Error('Task lease was lost.'));
    }).catch((error: unknown) => controller.abort(error));
  }, heartbeatMs);
  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    const output: unknown = await Promise.race([
      handler.run(task.input, { task, signal: controller.signal }),
      new Promise<never>((_, reject) => {
        timeout = setTimeout(() => {
          controller.abort(new Error('Agent task runtime limit exceeded.'));
          reject(new Error('Agent task runtime limit exceeded.'));
        }, timeoutMs);
      }),
    ]);
    if (!handler.validateOutput(output)) throw new Error('Worker output failed the pinned handler schema.');
    const completed = await completeAgentTask(task.id, workerId, task.lease_token, output);
    return { status: completed ? 'completed' : 'lease_lost', taskId: task.id };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown worker error.';
    const status = await failAgentTask(task.id, workerId, task.lease_token, message);
    return { status, taskId: task.id };
  } finally {
    if (timeout) clearTimeout(timeout);
    clearInterval(heartbeat);
  }
}

export async function runWorkerLoop(workerId: string, handlers: ReadonlyMap<string, AgentHandler>, signal: AbortSignal): Promise<void> {
  let lastRecovery = 0;
  while (!signal.aborted) {
    try {
      if (Date.now() - lastRecovery > 30_000) { await expireAgentTaskLeases(); lastRecovery = Date.now(); }
      const result = await processOneTask(workerId, handlers);
      if (result.status === 'idle') await new Promise((resolve) => setTimeout(resolve, 1000));
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
  }
}
