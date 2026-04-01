#!/usr/bin/env python3
"""
NanoClaw Session Metrics — Event Extractor

Scans Claude Code JSONL session files and emits flat, per-event records
as a JSON array. No aggregation — that belongs in the dashboard layer.

Each record has a consistent schema with dimensions for slicing:
  project, session_id, agent_type, week, timestamp,
  event_kind, role, tool_name, tool_category, memory_tech, memory_op, detail

Usage:
  python3 scripts/memory-usage-metrics.py                     # all projects
  python3 scripts/memory-usage-metrics.py -p nanoclaw          # single project
  python3 scripts/memory-usage-metrics.py -p nanoclaw -o out.json
"""

import json
import sys
import argparse
import re
from pathlib import Path
from datetime import datetime

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"

# --- Memory file detection ---

MEMORY_FILE_PATTERNS = [
    re.compile(r"/\.claude/projects/.*/memory/.*\.md$"),
    re.compile(r"/\.claude/.*MEMORY\.md$"),
]


def is_memory_file(file_path: str) -> bool:
    if not file_path:
        return False
    return any(p.search(file_path) for p in MEMORY_FILE_PATTERNS)


# --- Tool categorization ---

KG_TOOLS = {
    "search_nodes": "recall",
    "search_memory_facts": "recall",
    "get_episodes": "recall",
    "get_entity_edge": "recall",
    "get_status": "recall",
    "add_memory": "store",
    "delete_episode": "delete",
    "delete_entity_edge": "delete",
    "clear_graph": "delete",
}

FILE_READ_TOOLS = {"Read", "Glob", "Grep"}
FILE_WRITE_TOOLS = {"Write", "Edit"}

CATEGORY_MAP = {
    "Read": "file-read", "Glob": "file-read", "Grep": "file-read",
    "Write": "file-write", "Edit": "file-write",
    "Bash": "shell",
    "Agent": "agent",
    "WebSearch": "web", "WebFetch": "web",
    "ToolSearch": "other", "Skill": "other",
    "TaskCreate": "other", "TaskUpdate": "other", "TaskGet": "other",
    "TaskList": "other", "TaskOutput": "other", "NotebookEdit": "other",
}


def classify_tool(tool_name: str, tool_input: dict) -> dict:
    """Returns dict with: tool_category, memory_tech, memory_op, detail."""
    # Normalize legacy graphiti prefix
    suffix = None
    for prefix in ("mcp__memory-store__", "mcp__graphiti__"):
        if tool_name.startswith(prefix):
            suffix = tool_name[len(prefix):]
            break

    if suffix and suffix in KG_TOOLS:
        mem_op = KG_TOOLS[suffix]
        gid = tool_input.get("group_id") or tool_input.get("group_ids", [])
        if isinstance(gid, list):
            gid = ",".join(gid) if gid else None
        return {
            "tool_category": "memory-kg",
            "memory_tech": "knowledge-graph",
            "memory_op": mem_op,
            "detail": gid or None,
        }

    file_path = tool_input.get("file_path", "")
    if tool_name in FILE_READ_TOOLS and is_memory_file(file_path):
        return {
            "tool_category": "memory-md",
            "memory_tech": "markdown-file",
            "memory_op": "recall",
            "detail": file_path.replace(str(Path.home()), "~"),
        }
    if tool_name in FILE_WRITE_TOOLS and is_memory_file(file_path):
        return {
            "tool_category": "memory-md",
            "memory_tech": "markdown-file",
            "memory_op": "store",
            "detail": file_path.replace(str(Path.home()), "~"),
        }

    cat = CATEGORY_MAP.get(tool_name)
    if not cat and tool_name.startswith("mcp__"):
        cat = "mcp-other"
    if not cat:
        cat = "other"

    return {"tool_category": cat, "memory_tech": None, "memory_op": None, "detail": None}


# --- Helpers ---

def iso_week(ts_str: str | None) -> str | None:
    if not ts_str:
        return None
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        y, w, _ = dt.isocalendar()
        return f"{y}-W{w:02d}"
    except (ValueError, TypeError):
        return None


def project_name(dir_path: str) -> str:
    name = Path(dir_path).name
    for pfx in ("-home-tomas-git-", "-home-tomas--", "-home-tomas-"):
        if name.startswith(pfx):
            return name[len(pfx):]
    return name


# --- Scanner ---

def scan_jsonl(file_path: Path, proj: str, agent_type: str) -> list[dict]:
    """Yield flat event records from one JSONL file."""
    events = []
    try:
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = obj.get("type", "")
                if msg_type not in ("user", "assistant", "system"):
                    continue

                ts = obj.get("timestamp")
                sid = obj.get("sessionId")
                week = iso_week(ts)
                model = None

                # Base message event
                base = {
                    "project": proj,
                    "session_id": sid,
                    "agent_type": agent_type,
                    "week": week,
                    "timestamp": ts,
                }

                if msg_type == "assistant":
                    msg = obj.get("message", {})
                    model = msg.get("model")

                events.append({
                    **base,
                    "event_kind": "message",
                    "role": msg_type,
                    "model": model,
                    "tool_name": None,
                    "tool_category": None,
                    "memory_tech": None,
                    "memory_op": None,
                    "detail": None,
                })

                # Tool use events (from assistant messages)
                if msg_type == "assistant":
                    msg = obj.get("message", {})
                    content = msg.get("content", [])
                    if not isinstance(content, list):
                        continue
                    for block in content:
                        if not isinstance(block, dict) or block.get("type") != "tool_use":
                            continue
                        tname = block.get("name", "")
                        tinput = block.get("input", {})
                        cls = classify_tool(tname, tinput)

                        events.append({
                            **base,
                            "event_kind": "tool_use",
                            "role": None,
                            "model": model,
                            "tool_name": tname,
                            **cls,
                        })
    except (OSError, PermissionError):
        pass
    return events


def scan_project(project_dir: Path) -> list[dict]:
    proj = project_name(str(project_dir))
    events = []

    for item in project_dir.iterdir():
        if item.suffix == ".jsonl" and item.is_file():
            events.extend(scan_jsonl(item, proj, "main"))
        elif item.is_dir():
            subagents_dir = item / "subagents"
            if subagents_dir.is_dir():
                for sa in subagents_dir.glob("*.jsonl"):
                    events.extend(scan_jsonl(sa, proj, "subagent"))
            for jf in item.glob("*.jsonl"):
                if jf.parent.name != "subagents":
                    events.extend(scan_jsonl(jf, proj, "main"))

    return events


def main():
    parser = argparse.ArgumentParser(description="Extract flat session events as JSON")
    parser.add_argument("--project", "-p", help="Filter to a single project name")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    args = parser.parse_args()

    if not PROJECTS_DIR.is_dir():
        print(f"Projects directory not found: {PROJECTS_DIR}", file=sys.stderr)
        sys.exit(1)

    all_events = []
    for pd in sorted(PROJECTS_DIR.iterdir()):
        if not pd.is_dir():
            continue
        pname = project_name(str(pd))
        if args.project and args.project != pname:
            continue
        all_events.extend(scan_project(pd))

    if not all_events:
        print("No events found.", file=sys.stderr)
        sys.exit(1)

    out = json.dumps(all_events, default=str)
    if args.output:
        Path(args.output).write_text(out)
        print(f"Wrote {len(all_events)} events to {args.output}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
