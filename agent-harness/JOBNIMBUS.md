# JobNimbus CLI — Standard Operating Procedure

## Overview

This CLI gives agents read and write access to the JobNimbus Public API:
auditing, reporting, and creating / updating / soft-deleting records.

Command reference: `cli_anything/jobnimbus/skills/SKILL.md`.

## Authentication

- API key via `JOBNIMBUS_API_KEY` environment variable (preferred) or `--api-key`
- Keys come from JobNimbus Settings > API. The key's access profile decides what it may change.
- `--actor EMAIL` / `JOBNIMBUS_ACTOR` makes requests act as that JobNimbus user.

## Write Controls

| Control | Effect |
|---------|--------|
| `--dry-run` | Prints the request (method, URL, body); nothing is sent |
| `--read-only` / `JOBNIMBUS_READ_ONLY=1` | Every POST and PUT is refused |
| `delete --yes` | Deletes are soft (`is_active=false`) and need explicit confirmation |

Give audit-only agents `JOBNIMBUS_READ_ONLY=1`.

## API Facts (verified against the live API)

- **Base URL**: `https://app.jobnimbus.com/api1` — methods are GET, POST, PUT only.
- **Auth header**: `Authorization: Bearer {key}`
- **Filtering**: only `?filter=<JSON>` works (`must` / `should` / `must_not` with `term`,
  `terms`, `wildcard`, `prefix`, `range`, `exists`). Lucene `query_string` is rejected and
  unknown query parameters are silently ignored — the CLI translates `-q` queries for you.
- **Pagination**: `size` (max 1000 here) and `from`. `from >= 10000` returns 400; `export`
  re-anchors on the sort field to get past that.
- **Counting**: `size=0` is treated as "default page", so counts request `size=1&fields=jnid`.
- **v2 endpoints**: invoices, estimates, products, material orders, work orders. The v1
  single-record GET for invoices and estimates returns 404.
- **List keys**: activities come back under `activity`, files under `files`; the CLI
  always returns `results`.
- **No JSON single GET** for files, payments, credit memos (`GET files/<id>` returns the
  file bytes); the CLI looks those up through the list.
- **Delete** is `PUT {"is_active": false}`. `PUT` on activities and files works but is undocumented;
  the CLI offers `update` for them and no `delete`.
- **File upload**: `POST api.jobnimbus.com/files/v1/uploads/url` → `PUT` bytes to the
  presigned URL → `POST .../uploads/<jnid>/complete`.
- **Rate limits**: 429 is retried with backoff (3 attempts). Timeouts are not retried.
- **Timeout**: 60 seconds per request.

## Common Workflows

```bash
jn summary                                                          # account health
jn activities list --size=20                                        # recent activity
jn jobs list --sort-field=date_updated --sort-dir=asc --size=20     # stale jobs
jn --json contacts count --status=Lead                              # status distribution
jn activities notes --job-id=JNID --search=leak                     # note search on one job
jn --dry-run jobs update JNID --set status_name=Completed           # preview a change
```
