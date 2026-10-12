# cli-anything-jobnimbus

Agent-native CLI for reading and writing everything in a JobNimbus account.
The full command reference is in [skills/SKILL.md](skills/SKILL.md).

## Installation

```bash
python3 -m pip install --user .
```

## Configuration

```bash
export JOBNIMBUS_API_KEY="your-api-key-here"
export JOBNIMBUS_READ_ONLY=1        # optional: block every write
```

## Usage

```bash
# Read
jn contacts list --size=10
jn contacts search 'status_name:Lead AND city:Orlando'
jn jobs list --contact-id=JNID123
jn activities notes --job-id=JNID456 --search="leak"
jn --json related JNID123
jn export contacts > contacts.jsonl
jn summary

# Write
jn --dry-run contacts create --set first_name=Sam --set last_name=Kent \
    --set record_type_name=Customer --set status_name=Lead
jn jobs update JNID456 --set status_name=Completed
jn activities add-note JNID123 "Left a voicemail"
jn files upload ./photo.jpg --related JNID456 --type 2
jn contacts delete JNID123 --yes

# Anything else in the public API
jn api GET account/users
```

## Layout

| File | Purpose |
|------|---------|
| `core/resources.py` | Resource table: API path, list key, allowed writes, filter options |
| `core/query.py` | Translates `field:value AND ...` queries into the API's `filter` JSON |
| `core/client.py` | HTTP client: list / get / count / paginate, create / update / delete, files |
| `resource_commands.py` | Command groups generated from the resource table |
| `jobnimbus_cli.py` | Root command, cross-cutting commands, REPL |
| `utils/formatting.py` | Table and summary output |

Adding a resource is one entry in `core/resources.py`.
