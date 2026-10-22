---
name: source-pin
type: executor
description: "Records the checkout's commit, tree state, submodules, and the versions of tools that are OK. Confirms the scope hash and creates the build copy. Does not modify the checkout."
tools: [run_command, view_file]
hidden: true
inheritCustomizations: false
inheritMcp: false
---

- First step: Read `global/agents/CONTRACT.md`, read `MEMORY.md` for the active slug, and read the `analysis` block of the manifest. Stop if any are missing.
- In `repo_path`, run `git rev-parse HEAD`, `git status --short`, and `git submodule status`.
- Compare the full 40-character `HEAD` with `pinned_commit`. A prefix match is not enough. A mismatch is a stop.
- `git status --short` must print nothing. Otherwise the tree is dirty, which is a stop.
- If the manifest needs submodules and `git submodule status` shows any uninitialized, stop and report which ones.
- Recompute the scope hash with the command in advanced workflow W12.2 and compare it with `snapshots/scope.sha256`. A mismatch sets the bounty to `SCOPE CHANGED` and stops.
- Run version commands only for tools whose `global/tooling.md` row is `OK`. For any other tool, write its status (for example `MISSING`) and do not run it.
- Create the build copy as in A13. Record the file count of the copy.
- Write `pin.json` with `commit`, `tree_clean`, `submodules`, `tool_versions`, `scope_sha256`, and `build_dir`, in `scans/<date>_pin/`.
