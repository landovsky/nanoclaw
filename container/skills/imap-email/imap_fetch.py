#!/usr/bin/env python3
"""Read-only IMAP email fetcher for NanoClaw container agents.

Connects to an IMAP mailbox, fetches emails without modifying them,
extracts structured data, and aggregates contact information.

Safety: Uses BODY.PEEK[] exclusively — never marks emails as read,
never deletes, moves, or modifies any messages.
"""

import argparse
import email
import email.utils
import imaplib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from email.header import decode_header as _decode_header
from email.utils import parseaddr, getaddresses


def decode_header(raw):
    """Decode an RFC 2047 encoded header into a Unicode string."""
    if raw is None:
        return ""
    parts = []
    for fragment, charset in _decode_header(raw):
        if isinstance(fragment, bytes):
            parts.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(fragment)
    return " ".join(parts)


def decode_address(raw):
    """Parse a single address header into (name, email) tuple."""
    decoded = decode_header(raw)
    name, addr = parseaddr(decoded)
    return name.strip(), addr.strip().lower()


def decode_address_list(raw):
    """Parse an address header that may contain multiple addresses."""
    if not raw:
        return []
    decoded = decode_header(raw)
    pairs = getaddresses([decoded])
    result = []
    for name, addr in pairs:
        if addr:
            result.append({"name": name.strip(), "email": addr.strip().lower()})
    return result


def extract_text_body(msg):
    """Extract plain text body from a MIME message.

    Walks the MIME tree looking for text/plain parts first.
    Falls back to stripping HTML tags from text/html if no plain text found.
    """
    plain_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    plain_parts.append(payload.decode(charset, errors="replace"))
            elif content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_parts.append(payload.decode(charset, errors="replace"))
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if content_type == "text/plain":
                plain_parts.append(text)
            elif content_type == "text/html":
                html_parts.append(text)

    if plain_parts:
        return "\n".join(plain_parts).strip()

    if html_parts:
        return strip_html("\n".join(html_parts)).strip()

    return ""


def strip_html(html):
    """Remove HTML tags and decode common entities."""
    # Remove style/script blocks
    text = re.sub(r"<(style|script)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Replace <br> and <p> with newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|tr|li)>", "\n", text, flags=re.IGNORECASE)
    # Remove remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    # Collapse excessive whitespace but preserve paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def extract_thread_id(msg):
    """Extract thread identifier from In-Reply-To or References headers."""
    in_reply_to = msg.get("In-Reply-To", "").strip()
    if in_reply_to:
        return in_reply_to

    references = msg.get("References", "").strip()
    if references:
        # The first message-id in References is the thread root
        ids = references.split()
        if ids:
            return ids[0]

    return None


def parse_date(date_str):
    """Parse an email date header into ISO 8601 string."""
    if not date_str:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(date_str)
        return parsed.isoformat()
    except Exception:
        return date_str


def fetch_emails(host, port, user, password, folder, limit, since, before=None):
    """Connect to IMAP server and fetch emails read-only."""
    conn = imaplib.IMAP4_SSL(host, port)
    try:
        conn.login(user, password)
        status, _ = conn.select(folder, readonly=True)
        if status != "OK":
            print(f"Error: could not select folder '{folder}'", file=sys.stderr)
            sys.exit(1)

        # Build search criteria
        criteria_parts = []
        if since:
            try:
                dt = datetime.strptime(since, "%Y-%m-%d")
                criteria_parts.append(f'SINCE {dt.strftime("%d-%b-%Y")}')
            except ValueError:
                print(f"Error: --since must be YYYY-MM-DD format, got '{since}'", file=sys.stderr)
                sys.exit(1)
        if before:
            try:
                dt = datetime.strptime(before, "%Y-%m-%d")
                criteria_parts.append(f'BEFORE {dt.strftime("%d-%b-%Y")}')
            except ValueError:
                print(f"Error: --before must be YYYY-MM-DD format, got '{before}'", file=sys.stderr)
                sys.exit(1)
        if criteria_parts:
            search_criteria = '(' + ' '.join(criteria_parts) + ')'
        else:
            search_criteria = "ALL"

        status, data = conn.search(None, search_criteria)
        if status != "OK":
            print("Error: IMAP search failed", file=sys.stderr)
            sys.exit(1)

        msg_ids = data[0].split()
        if not msg_ids:
            return []

        # Take the most recent N messages
        msg_ids = msg_ids[-limit:]

        emails = []
        for msg_id in msg_ids:
            # BODY.PEEK[] — read without marking as seen
            status, msg_data = conn.fetch(msg_id, "(BODY.PEEK[])")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            from_name, from_email_addr = decode_address(msg.get("From", ""))
            to_list = decode_address_list(msg.get("To", ""))
            cc_list = decode_address_list(msg.get("Cc", ""))

            emails.append({
                "message_id": msg.get("Message-ID", "").strip(),
                "date": parse_date(msg.get("Date")),
                "from_name": from_name,
                "from_email": from_email_addr,
                "to": to_list,
                "cc": cc_list,
                "subject": decode_header(msg.get("Subject")),
                "body_text": extract_text_body(msg),
                "thread_id": extract_thread_id(msg),
            })

        return emails

    finally:
        try:
            conn.close()
        except Exception:
            pass
        conn.logout()


def aggregate_contacts(emails, own_email):
    """Build unique contact list from all emails, excluding the mailbox owner."""
    own = own_email.lower()
    contacts = defaultdict(lambda: {"name": "", "email": "", "count": 0, "last_seen": None})

    def track(name, addr, date_str):
        if not addr or addr == own:
            return
        key = addr
        entry = contacts[key]
        entry["email"] = addr
        if name and (not entry["name"] or len(name) > len(entry["name"])):
            entry["name"] = name
        entry["count"] += 1
        if date_str and (entry["last_seen"] is None or date_str > entry["last_seen"]):
            entry["last_seen"] = date_str

    for em in emails:
        track(em["from_name"], em["from_email"], em["date"])
        for addr in em["to"]:
            track(addr["name"], addr["email"], em["date"])
        for addr in em["cc"]:
            track(addr["name"], addr["email"], em["date"])

    result = []
    for entry in contacts.values():
        result.append({
            "name": entry["name"],
            "email": entry["email"],
            "seen_count": entry["count"],
            "last_seen_date": entry["last_seen"],
        })

    result.sort(key=lambda c: (-c["seen_count"], c["email"]))
    return result


def print_summary(emails, contacts):
    """Print a human-readable summary: contact table + threaded subjects."""
    print(f"=== {len(emails)} emails, {len(contacts)} unique contacts ===\n")

    # Contact table
    print("CONTACTS:")
    print(f"  {'Name':<30} {'Email':<40} {'Count':>5}")
    print("  " + "-" * 77)
    for c in contacts:
        name = c["name"] or "(no name)"
        print(f"  {name:<30} {c['email']:<40} {c['seen_count']:>5}")

    # Thread grouping
    print("\nEMAILS BY THREAD:")
    threads = defaultdict(list)
    standalone = []
    for em in emails:
        tid = em["thread_id"]
        if tid:
            threads[tid].append(em)
        else:
            standalone.append(em)

    thread_num = 0
    for tid, msgs in threads.items():
        thread_num += 1
        msgs.sort(key=lambda m: m["date"] or "")
        print(f"\n  Thread {thread_num}:")
        for m in msgs:
            date_short = (m["date"] or "")[:10]
            print(f"    [{date_short}] {m['from_name'] or m['from_email']}: {m['subject']}")

    if standalone:
        print("\n  Standalone:")
        for m in standalone:
            date_short = (m["date"] or "")[:10]
            print(f"    [{date_short}] {m['from_name'] or m['from_email']}: {m['subject']}")


def main():
    parser = argparse.ArgumentParser(
        description="Read-only IMAP email fetcher. Never modifies mailbox state."
    )
    parser.add_argument("--host", required=True, help="IMAP server hostname")
    parser.add_argument("--port", type=int, default=993, help="IMAP server port (default: 993)")
    parser.add_argument("--user", required=True, help="IMAP username / email address")
    parser.add_argument("--password", required=True, help="IMAP password")
    parser.add_argument("--folder", default="INBOX", help="Mailbox folder (default: INBOX)")
    parser.add_argument("--limit", type=int, default=50, help="Max emails to fetch (default: 50)")
    parser.add_argument("--since", help="Only fetch emails since this date (YYYY-MM-DD)")
    parser.add_argument("--before", help="Only fetch emails before this date (YYYY-MM-DD)")
    parser.add_argument(
        "--output-format",
        choices=["json", "summary"],
        default="json",
        help="Output format (default: json)",
    )

    args = parser.parse_args()

    emails = fetch_emails(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        folder=args.folder,
        limit=args.limit,
        since=args.since,
        before=args.before,
    )

    contacts = aggregate_contacts(emails, args.user)

    if args.output_format == "json":
        output = {
            "total_emails": len(emails),
            "total_contacts": len(contacts),
            "emails": emails,
            "contacts": contacts,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_summary(emails, contacts)


if __name__ == "__main__":
    main()
