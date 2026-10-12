# Agent instructions

This repository is `jn`, a command-line tool that reads **and writes** a JobNimbus
CRM account. (It was read-only before v0.3.0, and the installed skill is still
named `jobnimbus-read-cli`; the tool itself is not read-only.)

## Using `jn` on someone's account

The full command reference is
[agent-harness/cli_anything/jobnimbus/skills/SKILL.md](agent-harness/cli_anything/jobnimbus/skills/SKILL.md).
Read it before running anything. `./install.sh` installs `jn` and copies that
file into the skills folder of Claude, Codex and OpenClaw when they are present.

Writes change the live CRM a business runs on:

- Only make a change the user asked for. Otherwise show them `jn --dry-run ...`
  output and get a yes first.
- `--read-only` or `JOBNIMBUS_READ_ONLY=1` blocks every write. If a write is
  refused as read-only, tell the user; do not work around it.
- `delete` is a soft delete and needs `--yes`.
- Read the record back after a write before reporting it done.
- Use `--json` and `--fields` for anything you parse.

## Working on this codebase

- Code is in `agent-harness/cli_anything/jobnimbus/`. Its
  [README](agent-harness/cli_anything/jobnimbus/README.md) lists what each file does.
  Adding a resource is one entry in `core/resources.py`.
- How the JobNimbus API really behaves (filter syntax, the 10,000-record paging
  limit, v2 endpoints) is recorded in
  [agent-harness/JOBNIMBUS.md](agent-harness/JOBNIMBUS.md). Check it before changing the client.
- Tests, from `agent-harness/`:

  ```bash
  python3 -m pytest cli_anything/jobnimbus/tests --ignore=cli_anything/jobnimbus/tests/test_full_e2e.py
  ```

  `test_full_e2e.py` needs `JOBNIMBUS_API_KEY` and hits a live account. It only
  reads. Never add a test that sends a write to JobNimbus: verify write paths
  with the mocked session or `--dry-run`.
- The installed `jn` is a copy of the package, not a link. After changing the
  code, rerun `./install.sh` for `jn` to pick it up.
- When you change a command, update `skills/SKILL.md` in the same change. That
  file is what other agents rely on.
- The README demo GIF is rendered from `videos/jn-readme-demo/` (HyperFrames).
  Everything on screen there is invented sample data; keep it that way.
