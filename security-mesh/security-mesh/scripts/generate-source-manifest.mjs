#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { lstat, readFile } from 'node:fs/promises';
import path from 'node:path';

const [repoArg, repositoryUrl, commitArg] = process.argv.slice(2);
if (!repoArg || !repositoryUrl || !commitArg) {
  console.error('Usage: node scripts/generate-source-manifest.mjs <clean-checkout-path> <approved-https-repository-url> <full-commit-sha>');
  process.exit(2);
}
if (!repositoryUrl.startsWith('https://')) throw new Error('Repository URL must use HTTPS.');
if (!/^(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})$/.test(commitArg)) throw new Error('Commit must be a full 40- or 64-character SHA.');
const repo = path.resolve(repoArg);
const git = (...args) => execFileSync('git', ['-C', repo, ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
const commit = git('rev-parse', 'HEAD');
if (commit.toLowerCase() !== commitArg.toLowerCase()) throw new Error(`HEAD mismatch: expected ${commitArg}, got ${commit}`);
const normalizeRepo = (url) => url.replace(/\/+$/, '').replace(/\.git$/i, '').toLowerCase();
const origin = git('remote', 'get-url', 'origin');
if (!origin.startsWith('https://') || normalizeRepo(origin) !== normalizeRepo(repositoryUrl)) {
  throw new Error(`Repository origin mismatch: expected HTTPS origin ${repositoryUrl}, got ${origin}`);
}
const status = git('status', '--porcelain=v1', '--untracked-files=all', '--ignored');
if (status) throw new Error(`Checkout must be clean; git status reported changes:\n${status}`);
const pathsRaw = execFileSync('git', ['-C', repo, 'ls-files', '-z'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
const paths = pathsRaw.split('\0').filter(Boolean).sort((a, b) => a.localeCompare(b));
if (paths.length === 0) throw new Error('No tracked files found.');
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
const trackedFiles = [];
for (const relative of paths) {
  if (relative.startsWith('/') || relative.split(/[\\/]/).some((part) => part === '..' || part === '.')) throw new Error(`Unsafe git path: ${relative}`);
  const absolute = path.join(repo, relative);
  const stat = await lstat(absolute);
  if (!stat.isFile()) throw new Error(`Unsupported tracked non-regular file (symlink/submodule): ${relative}`);
  trackedFiles.push({ path: relative.replaceAll(path.sep, '/'), sha256: sha256(await readFile(absolute)) });
}
const treeMaterial = trackedFiles.map((file) => `${file.path}\t${file.sha256}\n`).join('');
const manifest = {
  schemaVersion: 1,
  repositoryUrl,
  commitSha: commit,
  cleanCheckout: true,
  treeSha256: sha256(Buffer.from(treeMaterial, 'utf8')),
  trackedFiles,
};
process.stdout.write(`${JSON.stringify(manifest, null, 2)}\n`);
