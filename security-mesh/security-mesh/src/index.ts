import { startServer } from './server.js';

startServer().catch((error: unknown) => {
  console.error('Antigravity Security Mesh failed to start:', error instanceof Error ? error.message : 'unknown error');
  process.exitCode = 1;
});
