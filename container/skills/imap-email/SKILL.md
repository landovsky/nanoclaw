---
name: imap-email
description: Fetch and extract data from IMAP mailboxes read-only. Use when the user asks to check email, list contacts from a mailbox, summarize inbox contents, or extract email data. Never modifies the mailbox.
---

# IMAP Email Fetcher

Read-only IMAP email fetcher. Connects to any IMAP mailbox, fetches messages without marking them as read or modifying state, and extracts structured data including contacts.

## Safety

- Uses `BODY.PEEK[]` exclusively — emails are **never** marked as read
- Opens folder in `readonly=True` mode
- Never deletes, moves, or modifies any emails

## Usage

The script is at `${CLAUDE_SKILL_DIR}/imap_fetch.py`.

### JSON output (default)

```bash
python3 ${CLAUDE_SKILL_DIR}/imap_fetch.py \
  --host mail.example.com \
  --user user@example.com \
  --password "secret" \
  --output-format json
```

### Summary output (human-readable)

```bash
python3 ${CLAUDE_SKILL_DIR}/imap_fetch.py \
  --host mail.example.com \
  --user user@example.com \
  --password "secret" \
  --output-format summary
```

### With date filter and limit

```bash
python3 ${CLAUDE_SKILL_DIR}/imap_fetch.py \
  --host mail.example.com \
  --user user@example.com \
  --password "secret" \
  --since 2025-01-01 \
  --limit 100
```

## Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--host` | yes | — | IMAP server hostname |
| `--port` | no | 993 | IMAP server port (SSL) |
| `--user` | yes | — | IMAP username / email |
| `--password` | yes | — | IMAP password |
| `--folder` | no | INBOX | Mailbox folder name |
| `--limit` | no | 50 | Max emails to fetch (most recent) |
| `--since` | no | — | Date filter (YYYY-MM-DD) |
| `--output-format` | no | json | `json` or `summary` |

## Output

### JSON mode

Two top-level arrays:

- **emails** — per-message data: `message_id`, `date`, `from_name`, `from_email`, `to`, `cc`, `subject`, `body_text`, `thread_id`
- **contacts** — unique contacts (excluding mailbox owner): `name`, `email`, `seen_count`, `last_seen_date`

### Summary mode

- Contact table with name, email, and occurrence count
- Email subjects grouped by thread

## Dependencies

Python standard library only — no pip install needed. Uses `imaplib`, `email`, `json`, `argparse`.
