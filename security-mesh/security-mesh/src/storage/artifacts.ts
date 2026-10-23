import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { config } from '../config.js';

export function sha256(bytes: Buffer | string): string {
  return createHash('sha256').update(bytes).digest('hex');
}

function root(): string {
  return resolve(config.ARTIFACT_ROOT);
}

export async function putArtifact(bytes: Buffer, expectedSha256: string): Promise<{ storageKey: string; sha256: string; byteLength: number }> {
  if (bytes.byteLength > config.MAX_ARTIFACT_BYTES) throw new Error('Artifact exceeds configured size limit.');
  const actual = sha256(bytes);
  if (actual.toLowerCase() !== expectedSha256.toLowerCase()) throw new Error('Artifact SHA-256 mismatch.');
  const storageKey = `sha256/${actual.slice(0, 2)}/${actual}`;
  const destination = resolve(root(), storageKey);
  if (!destination.startsWith(`${root()}${process.platform === 'win32' ? '\\' : '/'}`)) throw new Error('Invalid artifact storage path.');
  await mkdir(dirname(destination), { recursive: true, mode: 0o700 });
  try {
    await writeFile(destination, bytes, { flag: 'wx', mode: 0o600 });
  } catch (error) {
    if (!(error && typeof error === 'object' && 'code' in error && error.code === 'EEXIST')) throw error;
    const current = await readFile(destination);
    if (sha256(current) !== actual) throw new Error('Content-addressed artifact collision or corruption detected.');
  }
  return { storageKey, sha256: actual, byteLength: bytes.byteLength };
}

export async function loadArtifactByStorageKey(storageKey: string): Promise<Buffer> {
  if (storageKey.startsWith('/') || storageKey.includes('..') || storageKey.includes('\\')) throw new Error('Invalid artifact key.');
  const target = resolve(root(), storageKey);
  if (!target.startsWith(`${root()}${process.platform === 'win32' ? '\\' : '/'}`)) throw new Error('Invalid artifact key.');
  const bytes = await readFile(target);
  if (sha256(bytes) !== target.split(/[\\/]/).at(-1)) throw new Error('Stored artifact failed integrity check.');
  return bytes;
}
