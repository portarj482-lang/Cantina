/**
 * Minimal ESM loader hook for `node --experimental-strip-types`.
 *
 * Node's strip-types runner strips TypeScript syntax but does NOT remap
 * `.js` → `.ts` for transitive imports (only top-level CLI entry points are
 * resolved by the experimental flag).  This loader performs that remapping
 * for source files under the `src/` directory so that the smoke-check script
 * can import TypeScript files that themselves import other TypeScript files
 * using the standard NodeNext `.js` extension convention.
 *
 * This file is development/CI-only.  It is never bundled or shipped.
 */

import { existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';

/**
 * Resolve hook: rewrite `<path>.js` → `<path>.ts` when the `.ts` file exists
 * and the import originates from a `.ts` source file in this project.
 */
export async function resolve(specifier, context, nextResolve) {
  if (
    specifier.endsWith('.js') &&
    context.parentURL &&
    (context.parentURL.includes('/src/') || context.parentURL.includes('/scripts/'))
  ) {
    const tsSpecifier = specifier.slice(0, -3) + '.ts';
    try {
      const resolved = await nextResolve(tsSpecifier, context);
      const fsPath = fileURLToPath(resolved.url);
      if (existsSync(fsPath)) {
        return resolved;
      }
    } catch {
      // fall through to default resolution
    }
  }
  return nextResolve(specifier, context);
}
