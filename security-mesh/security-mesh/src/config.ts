import 'dotenv/config';
import { z } from 'zod';

const secret = z.string().min(32, 'Must be at least 32 characters');
const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  HOST: z.string().default('127.0.0.1'),
  PORT: z.coerce.number().int().min(1).max(65535).default(8788),
  DATABASE_URL: z.string().min(1),
  API_TOKEN: secret,
  ADMIN_API_TOKEN: secret,
  HUMAN_APPROVAL_TOKEN: secret,
  RUNNER_TOKEN: secret.optional().default(''),
  RUNNER_ID: z.string().min(3).default('dev-runner-single-operator'),
  RUNNER_PUBLIC_KEY_PEM: z.string().optional().default(''),
  ARTIFACT_ROOT: z.string().default('./artifacts'),
  GEMINI_API_KEY: z.string().optional().default(''),
  GEMINI_MODEL: z.string().min(1).default('gemini-flash-latest'),
  GEMINI_TRIAGE_ENABLED: z.enum(['true', 'false']).default('false').transform((value) => value === 'true'),
  MAX_ARTIFACT_BYTES: z.coerce.number().int().min(1024).max(100_000_000).default(20_000_000),
});

const result = envSchema.superRefine((value, context) => {
  if (value.NODE_ENV !== 'production' && value.RUNNER_TOKEN.length < 32) {
    context.addIssue({ code: 'custom', path: ['RUNNER_TOKEN'], message: 'Must be at least 32 characters outside production.' });
  }
}).safeParse(process.env);
if (!result.success) {
  const messages = result.error.issues.map((issue) => `${issue.path.map(String).join('.')}: ${issue.message}`).join('; ');
  throw new Error(`Invalid environment configuration: ${messages}`);
}

export const config = Object.freeze({
  ...result.data,
  RUNNER_PUBLIC_KEY_PEM: result.data.RUNNER_PUBLIC_KEY_PEM.replace(/\\n/g, '\n'),
});
