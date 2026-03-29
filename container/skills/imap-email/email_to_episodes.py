#!/usr/bin/env python3
"""
Convert extracted email data (from imap_fetch.py) into memory-store episodes.

Reads JSON from stdin or --input file (output of imap_fetch.py --output-format json),
groups emails by contact, and submits each contact as an episode to the memory-store
MCP server via HTTP.

Usage:
  python3 imap_fetch.py --output-format json ... | python3 email_to_episodes.py --group-id swan_crm
  python3 email_to_episodes.py --input emails.json --group-id swan_crm --dry-run
"""

import argparse
import json
import sys
import urllib.request
from collections import defaultdict


def init_mcp_session(base_url: str) -> str:
    """Initialize MCP session and return session ID."""
    req = urllib.request.Request(
        base_url,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "email_to_episodes", "version": "1.0"}
            }
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
    )
    resp = urllib.request.urlopen(req)
    session_id = resp.headers.get("mcp-session-id", "")
    # Read the response body to completion
    resp.read()
    return session_id


def add_episode(base_url: str, session_id: str, name: str, body: str,
                group_id: str, source_desc: str, req_id: int) -> dict:
    """Submit one episode to memory-store."""
    payload = {
        "jsonrpc": "2.0", "id": req_id, "method": "tools/call",
        "params": {
            "name": "add_memory",
            "arguments": {
                "name": name,
                "episode_body": body,
                "source": "text",
                "source_description": source_desc,
                "group_id": group_id
            }
        }
    }
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "mcp-session-id": session_id
        }
    )
    resp = urllib.request.urlopen(req)
    # Parse SSE response
    body_text = resp.read().decode()
    for line in body_text.split("\n"):
        if line.startswith("data: "):
            return json.loads(line[6:])
    return {"error": "no data in response"}


def build_contact_episode(contact: dict, emails: list) -> str:
    """Build episode text for a contact, summarizing their email interactions."""
    lines = []
    name = contact.get("name", "").strip()
    email = contact["email"]

    if name:
        lines.append(f"Kontakt: {name} <{email}>")
    else:
        lines.append(f"Kontakt: {email}")

    lines.append(f"Počet emailů: {contact.get('seen_count', len(emails))}")

    if emails:
        lines.append(f"Poslední komunikace: {emails[0].get('date', 'neznámé')}")
        lines.append("")
        lines.append("Historie komunikace:")
        for em in emails[:10]:  # Cap at 10 most recent per contact
            direction = "←" if em.get("from_email", "").lower() == email.lower() else "→"
            subject = em.get("subject", "(bez předmětu)")
            date = em.get("date", "")
            body_preview = em.get("body_text", "")[:200].replace("\n", " ").strip()
            lines.append(f"  {direction} [{date}] {subject}")
            if body_preview:
                lines.append(f"    {body_preview}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Submit email contacts as memory-store episodes")
    parser.add_argument("--input", "-i", help="Input JSON file (default: stdin)")
    parser.add_argument("--group-id", required=True, help="Memory-store group_id")
    parser.add_argument("--mcp-url", default="http://host.docker.internal:8051/mcp",
                        help="Memory-store MCP endpoint")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print episodes without submitting")
    parser.add_argument("--exclude-email", action="append", default=[],
                        help="Email addresses to exclude (repeatable)")
    args = parser.parse_args()

    # Read input
    if args.input:
        with open(args.input) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    contacts = data.get("contacts", [])
    emails = data.get("emails", [])

    if not contacts:
        print("No contacts found in input.", file=sys.stderr)
        sys.exit(1)

    # Build email index by contact email
    emails_by_contact = defaultdict(list)
    for em in emails:
        from_email = em.get("from_email", "").lower()
        emails_by_contact[from_email].append(em)
        # Also index by To addresses (list of {name, email} dicts)
        to_field = em.get("to", [])
        if isinstance(to_field, str):
            to_field = [{"email": t.strip()} for t in to_field.split(",") if t.strip()]
        for to in to_field:
            addr = to.get("email", "").strip().lower()
            if addr:
                emails_by_contact[addr].append(em)

    # Deduplicate and sort emails per contact
    for key in emails_by_contact:
        seen_ids = set()
        unique = []
        for em in emails_by_contact[key]:
            mid = em.get("message_id", id(em))
            if mid not in seen_ids:
                seen_ids.add(mid)
                unique.append(em)
        emails_by_contact[key] = sorted(unique, key=lambda e: e.get("date", ""), reverse=True)

    # Filter contacts
    exclude = {e.lower() for e in args.exclude_email}
    contacts = [c for c in contacts if c["email"].lower() not in exclude]

    print(f"Processing {len(contacts)} contacts from {len(emails)} emails", file=sys.stderr)

    if args.dry_run:
        for contact in contacts:
            contact_emails = emails_by_contact.get(contact["email"].lower(), [])
            episode_text = build_contact_episode(contact, contact_emails)
            print(f"\n{'='*60}")
            print(f"EPISODE: {contact.get('name', '')} <{contact['email']}>")
            print(f"{'='*60}")
            print(episode_text)
        print(f"\nDry run complete. {len(contacts)} episodes would be submitted.", file=sys.stderr)
        return

    # Initialize MCP session
    try:
        session_id = init_mcp_session(args.mcp_url)
        print(f"MCP session: {session_id}", file=sys.stderr)
    except Exception as e:
        print(f"Failed to connect to memory-store: {e}", file=sys.stderr)
        sys.exit(1)

    # Submit episodes
    success = 0
    for i, contact in enumerate(contacts, 1):
        contact_emails = emails_by_contact.get(contact["email"].lower(), [])
        episode_text = build_contact_episode(contact, contact_emails)
        name = contact.get("name") or contact["email"]
        episode_name = f"Email kontakt: {name}"

        try:
            result = add_episode(
                args.mcp_url, session_id, episode_name, episode_text,
                args.group_id, "imap email extraction", req_id=i + 1
            )
            success += 1
            print(f"  [{i}/{len(contacts)}] {name} — submitted", file=sys.stderr)
        except Exception as e:
            print(f"  [{i}/{len(contacts)}] {name} — FAILED: {e}", file=sys.stderr)

    print(f"\nDone. {success}/{len(contacts)} episodes submitted to group '{args.group_id}'.",
          file=sys.stderr)
    print(json.dumps({"submitted": success, "total": len(contacts), "group_id": args.group_id}))


if __name__ == "__main__":
    main()
