# JobNimbus Read-Only CLI — Standard Operating Procedure

## Overview

This CLI provides **read-only** access to the JobNimbus Public API for auditing
accounts, monitoring job progress, scraping notes, and analyzing activity trails.

**STRICT READ-ONLY**: Only HTTP GET methods are implemented. There are zero
POST, PUT, or DELETE operations. This guarantees no data modification.

## Authentication

- API key via `JOBNIMBUS_API_KEY` environment variable (preferred)
- Or `--api-key` flag on any command
- Keys are obtained from JobNimbus Settings > API Keys

## API Details

- **Base URL**: `https://app.jobnimbus.com/api1`
- **Auth Header**: `Authorization: Bearer {key}`
- **Rate Limits**: 429 responses handled with exponential backoff
- **Timeout**: 30 seconds per request, 3 retries max

## Resources

| Resource   | Description                              |
|------------|------------------------------------------|
| contacts   | Customers, leads, and company contacts   |
| jobs       | Projects, work orders, estimates         |
| tasks      | To-dos, assignments, reminders           |
| activities | Notes, emails, calls, system events      |

## Query Capabilities

### ElasticSearch Syntax
The `--query` / `-q` parameter supports Lucene query syntax:
- Field queries: `status_name:Lead`
- Wildcards: `name:*Smith*`
- Boolean: `city:Miami AND state_text:FL`
- Range: `date_created:[1700000000 TO *]`

### Pagination
- `--size` / `-s`: Records per page (default 50, max 1000)
- `--offset` / `-o`: Starting index (0-based)

### Sorting
- `--sort-field`: Any field name (default: `date_updated`)
- `--sort-dir`: `asc` or `desc` (default: `desc`)

### Field Selection
- `--fields`: Comma-separated list to reduce response size
- Example: `--fields=note,date_created,jnid` for lean note scraping

## Output Modes

- **Table** (default): Human-readable summary format
- **JSON** (`--json`): Raw API response for programmatic consumption
- **Columns** (`--columns`): Custom table columns

## Common Audit Workflows

### 1. Account Health Check
```bash
jn summary
```

### 2. Recent Activity Audit
```bash
jn activities list --sort-field=date_updated --sort-dir=desc --size=20
```

### 3. Note Scraping for Keywords
```bash
jn activities search "note:*leak*" --fields=note,date_created --json
```

### 4. Stale Jobs Detection
```bash
jn jobs list --sort-field=date_updated --sort-dir=asc --size=20
```

### 5. Contact Status Distribution
```bash
jn contacts list --status=Lead --json | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['count'])"
```
