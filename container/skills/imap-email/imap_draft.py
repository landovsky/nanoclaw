#!/usr/bin/env python3
"""Create email drafts and reply drafts via IMAP.

Saves messages to the Drafts folder — never sends anything.

Usage:
    # New draft
    python3 imap_draft.py --new-draft \
        --host mail.example.com --user me@example.com --password secret \
        --to recipient@example.com --subject "Hello" --body "Message body"

    # Reply draft
    python3 imap_draft.py --reply-to "<original-message-id@example.com>" \
        --host mail.example.com --user me@example.com --password secret \
        --body "Reply body"
"""

import argparse
import imaplib
import json
import sys
import time
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, formataddr, parsedate_to_datetime


def connect(host: str, port: int, user: str, password: str) -> imaplib.IMAP4_SSL:
    conn = imaplib.IMAP4_SSL(host, port)
    conn.login(user, password)
    return conn


def find_message_by_id(conn: imaplib.IMAP4_SSL, message_id: str, search_folder: str = "INBOX") -> tuple:
    """Fetch original message by Message-ID. Returns (EmailMessage, raw_bytes) or raises."""
    conn.select(search_folder, readonly=True)
    # Search by Message-ID header
    typ, data = conn.search(None, f'HEADER Message-ID "{message_id}"')
    if typ != "OK" or not data[0]:
        raise ValueError(f"Message with ID {message_id} not found in {search_folder}")
    uid = data[0].split()[-1]  # take last match
    typ, msg_data = conn.fetch(uid, "(RFC822)")
    if typ != "OK":
        raise ValueError(f"Failed to fetch message {uid}")
    raw = msg_data[0][1]
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    return msg


def build_new_draft(from_addr: str, to: str, subject: str, body: str,
                    cc: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(body, charset="utf-8")
    return msg


def build_reply_draft(original: EmailMessage, from_addr: str, body: str,
                      to: str | None = None, cc: str | None = None,
                      subject: str | None = None) -> EmailMessage:
    reply = EmailMessage()

    # From
    reply["From"] = from_addr

    # To: use provided --to, or fall back to original From/Reply-To
    if to:
        reply["To"] = to
    else:
        reply["To"] = original.get("Reply-To", original["From"])

    if cc:
        reply["Cc"] = cc

    # Subject
    orig_subject = original.get("Subject", "")
    if subject:
        reply["Subject"] = subject
    elif orig_subject.lower().startswith("re:"):
        reply["Subject"] = orig_subject
    else:
        reply["Subject"] = f"Re: {orig_subject}"

    # Threading headers
    orig_msg_id = original["Message-ID"]
    if orig_msg_id:
        reply["In-Reply-To"] = orig_msg_id
        orig_refs = original.get("References", "")
        refs = f"{orig_refs} {orig_msg_id}".strip() if orig_refs else orig_msg_id
        reply["References"] = refs

    reply["Date"] = formatdate(localtime=True)

    # Quote original body
    orig_body = original.get_body(preferencelist=("plain",))
    quoted = ""
    if orig_body:
        orig_text = orig_body.get_content()
        orig_date = original.get("Date", "unknown date")
        orig_from = original.get("From", "unknown sender")
        quoted = f"\n\nOn {orig_date}, {orig_from} wrote:\n"
        for line in orig_text.splitlines():
            quoted += f"> {line}\n"

    reply.set_content(body + quoted, charset="utf-8")
    return reply


def save_draft(conn: imaplib.IMAP4_SSL, msg: EmailMessage, drafts_folder: str) -> None:
    raw = msg.as_bytes()
    date_time = imaplib.Time2Internaldate(time.time())
    typ, _ = conn.append(drafts_folder, "\\Draft", date_time, raw)
    if typ != "OK":
        raise RuntimeError(f"APPEND to {drafts_folder} failed")


def main():
    parser = argparse.ArgumentParser(description="Create email drafts via IMAP (never sends)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--new-draft", action="store_true", help="Create a new draft")
    mode.add_argument("--reply-to", metavar="MESSAGE_ID", help="Reply to message with this Message-ID")

    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=993)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)

    parser.add_argument("--from", dest="from_addr", help="From address (defaults to --user)")
    parser.add_argument("--to", help="Recipient address")
    parser.add_argument("--cc", help="CC address(es)")
    parser.add_argument("--subject", help="Email subject")
    parser.add_argument("--body", help="Email body text")
    parser.add_argument("--body-file", help="Read body from file instead of --body")
    parser.add_argument("--drafts-folder", default="INBOX.Drafts", help="IMAP drafts folder name")
    parser.add_argument("--search-folder", default="INBOX", help="Folder to search for original message (reply mode)")

    args = parser.parse_args()

    # Resolve body
    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8") as f:
            body = f.read()
    elif args.body:
        body = args.body
    else:
        print(json.dumps({"status": "error", "message": "Either --body or --body-file is required"}))
        sys.exit(1)

    from_addr = args.from_addr or args.user

    try:
        conn = connect(args.host, args.port, args.user, args.password)

        if args.new_draft:
            if not args.to:
                print(json.dumps({"status": "error", "message": "--to is required for --new-draft"}))
                sys.exit(1)
            if not args.subject:
                print(json.dumps({"status": "error", "message": "--subject is required for --new-draft"}))
                sys.exit(1)
            msg = build_new_draft(from_addr, args.to, args.subject, body, cc=args.cc)
        else:
            original = find_message_by_id(conn, args.reply_to, search_folder=args.search_folder)
            msg = build_reply_draft(original, from_addr, body,
                                    to=args.to, cc=args.cc, subject=args.subject)

        save_draft(conn, msg, args.drafts_folder)
        subject = msg["Subject"]
        print(json.dumps({"status": "ok", "draft_folder": args.drafts_folder, "subject": subject}))

        conn.logout()
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
