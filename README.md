<p align="center">
  <img src="assets/logo.png" alt="JobNimbus Read CLI" width="200">
</p>

<h1 align="center">JobNimbus Read CLI</h1>

<p align="center">
  <strong>Read-only, agent-native CLI for auditing everything in a JobNimbus CRM account.</strong><br>
  Built for AI agents to query contacts, jobs, tasks, activities, invoices, estimates, products, files, and workflows — with zero risk of data modification.
</p>

<p align="center">
  The installer can also add a ready-to-use skill for Claude, Codex, and OpenClaw.<br>
  You can review that skill here: <a href="agent-harness/cli_anything/jobnimbus/skills/SKILL.md">SKILL.md</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.2.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/python-3.9+-green" alt="Python">
  <img src="https://img.shields.io/badge/mode-read--only-orange" alt="Read Only">
  <img src="https://img.shields.io/badge/tests-61%20passed-brightgreen" alt="Tests">
</p>

---

## Why

JobNimbus has no built-in reporting CLI. This tool lets AI agents (or humans) query the full JobNimbus API from the terminal with structured JSON output, ElasticSearch queries, pagination, and bulk export — all strictly read-only.

## One-Line Install

### CLI Only (macOS / Linux)

```bash
git clone https://github.com/Cryptic0011/jobnimbus-read-cli.git && cd jobnimbus-read-cli && ./install.sh
```

### Agent Installs (macOS / Linux)

These use the same installer on purpose. The difference is which agent you already have on your machine.

**Claude Code**

```bash
git clone https://github.com/Cryptic0011/jobnimbus-read-cli.git && cd jobnimbus-read-cli && ./install.sh
```

**Codex**

```bash
git clone https://github.com/Cryptic0011/jobnimbus-read-cli.git && cd jobnimbus-read-cli && ./install.sh
```

**OpenClaw**

```bash
git clone https://github.com/Cryptic0011/jobnimbus-read-cli.git && cd jobnimbus-read-cli && ./install.sh
```

### Windows (PowerShell)

```powershell
git clone https://github.com/Cryptic0011/jobnimbus-read-cli.git; cd jobnimbus-read-cli; powershell -ExecutionPolicy Bypass -File .\install.ps1
```

For normal CLI users, the installer just gives you a global `jn` command.

For Claude/Codex/OpenClaw users, the same installer also handles agent setup when it finds that agent's home directory.

The installer:
- Installs `jn` as a user-level Python command with `pip install --user`
- Copies the skill into `~/.claude/skills/` if `~/.claude` exists
- Copies the skill into `${CODEX_HOME:-~/.codex}/skills/` if Codex is installed
- Copies the skill into `~/.openclaw/skills/` if OpenClaw is installed
- Tells you if your Python user `bin` directory still needs to be added to `PATH`

## Set Your API Key

**macOS/Linux** — add to `~/.zshrc` or `~/.bashrc`:
```bash
export JOBNIMBUS_API_KEY="your-api-key"
```

**Windows PowerShell:**
```powershell
[System.Environment]::SetEnvironmentVariable("JOBNIMBUS_API_KEY", "your-api-key", "User")
```

**Claude Code** — add to `~/.claude/settings.json`:
```json
{
  "env": {
    "JOBNIMBUS_API_KEY": "your-api-key"
  }
}
```

**OpenClaw** — add to `~/.openclaw/openclaw.json`:
```json
{
  "env": {
    "JOBNIMBUS_API_KEY": "your-api-key"
  }
}
```

Get your API key from JobNimbus: **Settings > API Keys**.

## Quick Start

```bash
# Account overview
jn summary

# List recent contacts
jn contacts list --size=10

# Search jobs
jn jobs search "status_name:Completed"

# Find unpaid invoices
jn --json invoices search "status:Unpaid"

# Pull everything for a contact
jn --json related CONTACT_JNID

# Export all notes as JSONL
jn export activities --query="record_type_name:note" > notes.jsonl
```

## Commands

| Command | Description |
|---------|-------------|
| `jn contacts` | Customers, leads, companies |
| `jn jobs` | Projects, work orders |
| `jn tasks` | To-dos, assignments |
| `jn activities` | Notes, emails, calls, audit trail |
| `jn invoices` | Billing, line items, payment status |
| `jn estimates` | Quotes, proposals |
| `jn products` | Material/labor catalog, pricing |
| `jn files` | Documents, photos, attachments |
| `jn workflows` | Pipeline stages and statuses |
| `jn find <JNID>` | Auto-detect resource type |
| `jn related <JNID>` | All records for a contact/job |
| `jn export <resource>` | Bulk JSONL with auto-pagination |
| `jn summary` | Record counts for all resources |
| `jn repl` | Interactive session |

Most resources support `list`, `get`, `count`, and `search`.
Exceptions:
- `jn products` supports `list`, `get`, and `search`
- `jn files` supports `list`, `get`, and `count`

## Common Options

```
--json              Output raw JSON (for agents)
--size N            Records per page (max 1000)
--offset N          Pagination offset
--sort-field F      Sort by field (default: date_updated)
--sort-dir asc|desc Sort direction (default: desc)
--query Q           ElasticSearch/Lucene query
--fields F          Comma-separated fields (saves tokens)
--columns F         Custom table columns
```

## Query Syntax

The `--query` parameter supports ElasticSearch/Lucene syntax:

```bash
# Field match
jn contacts search "status_name:Lead"

# Wildcards
jn jobs search "name:*Smith*"

# Boolean
jn contacts search "city:Miami AND state_text:FL"

# Range
jn invoices search "total:[1000 TO *]"

# Combined
jn activities search "note:*leak* AND record_type_name:note"
```

## Agent Usage

The installer copies the skill into Claude and Codex only if those homes already exist on your machine. That keeps the install safe for first-time users while still making the tool available to agents you already use.

For agent use, make sure:
- `jn` works in a fresh terminal
- `JOBNIMBUS_API_KEY` is set in the environment the agent will run with

Just talk naturally:
- *"How many unpaid invoices do I have in JobNimbus?"*
- *"Pull all activity notes for contact JNID123"*
- *"What jobs were updated today?"*
- *"Give me a summary of my JN account"*

## Read-Only Guarantee

This CLI **only implements HTTP GET requests**. The API client class:
- Exposes no `create`, `update`, or `delete` methods
- The `_request()` method only calls `session.get()`
- Verified by automated tests that inspect the source code

## Tests

```bash
# Unit tests (no API key needed)
python3 -m pytest agent-harness/cli_anything/jobnimbus/tests/test_core.py -v

# E2E tests (requires API key)
export JOBNIMBUS_API_KEY="your-key"
python3 -m pytest agent-harness/cli_anything/jobnimbus/tests/test_full_e2e.py -v
```

## License

No license file has been added yet. Until one is added, treat the code as all rights reserved.
