# JobNimbus CLI — Tests

Run from `agent-harness/`:

```bash
# Unit tests: no API key, no network (the HTTP session is mocked)
python3 -m pytest cli_anything/jobnimbus/tests --ignore=cli_anything/jobnimbus/tests/test_full_e2e.py

# E2E: needs JOBNIMBUS_API_KEY, hits the live API, read-only
python3 -m pytest cli_anything/jobnimbus/tests/test_full_e2e.py
```

| File | Covers |
|------|--------|
| `test_query.py` | Query language → filter JSON; unsupported syntax raises instead of being ignored |
| `test_core.py` | Client: request building, error handling, pagination past the 10k window, find / related, create / update / delete, read-only lock, dry run, upload / download, formatting |
| `test_cli.py` | Commands end to end with a mocked API: filters reach the API, `--set` / `--data`, delete needs `--yes`, `--dry-run`, `--read-only`, error output, REPL |
| `test_full_e2e.py` | Live reads only: list / get / count shapes, filters really narrow results, related returns linked records |

No test ever sends a write to JobNimbus. Write paths are verified against a mocked
session and with `--dry-run`.
