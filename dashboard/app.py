"""NanoClaw Scheduler Dashboard — Streamlit app.

Reads the NanoClaw SQLite database (read-only) and displays scheduled tasks
and their run history.

Usage:
    streamlit run dashboard/app.py --server.port 8502 --server.headless true
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

TZ = ZoneInfo("Europe/Prague")
DB_PATH = Path(__file__).resolve().parent.parent / "store" / "messages.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def fmt_dt(s: str | None) -> str:
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return s[:16] if s else "—"


def fmt_duration(ms: int | None) -> str:
    if ms is None:
        return "—"
    secs = ms / 1000
    if secs < 60:
        return f"{secs:.0f}s"
    if secs < 3600:
        return f"{secs / 60:.1f}m"
    return f"{secs / 3600:.1f}h"


def fmt_schedule(stype: str, svalue: str) -> str:
    if stype == "cron":
        return f"cron: {svalue}"
    if stype == "interval":
        try:
            ms = int(svalue)
            if ms >= 86400000:
                return f"every {ms // 86400000}d"
            if ms >= 3600000:
                return f"every {ms // 3600000}h"
            if ms >= 60000:
                return f"every {ms // 60000}m"
            return f"every {ms // 1000}s"
        except ValueError:
            return f"interval: {svalue}"
    if stype == "once":
        return f"once: {fmt_dt(svalue)}"
    return f"{stype}: {svalue}"


def status_icon(status: str) -> str:
    return {"active": "🟢", "paused": "⏸️", "completed": "✅"}.get(status, "❓")


def main():
    st.set_page_config(page_title="NanoClaw Scheduler", page_icon="🦞", layout="wide")
    st.title("🦞 NanoClaw Scheduler")

    if not DB_PATH.exists():
        st.error(f"Database not found: {DB_PATH}")
        return

    db = get_db()

    # --- Load tasks with stats ---
    now_utc = datetime.now(timezone.utc)
    cutoff_24h = (now_utc - timedelta(hours=24)).isoformat()

    tasks = db.execute(
        """
        SELECT t.*,
            (SELECT COUNT(*) FROM task_run_logs l
             WHERE l.task_id = t.id AND l.status = 'error'
             AND l.run_at >= ?) AS errors_24h,
            (SELECT COUNT(*) FROM task_run_logs l
             WHERE l.task_id = t.id) AS total_runs,
            (SELECT MAX(l.run_at) FROM task_run_logs l
             WHERE l.task_id = t.id) AS actual_last_run,
            (SELECT l.status FROM task_run_logs l
             WHERE l.task_id = t.id ORDER BY l.run_at DESC LIMIT 1) AS last_run_status
        FROM scheduled_tasks t
        ORDER BY
            CASE t.status
                WHEN 'active' THEN 0
                WHEN 'paused' THEN 1
                ELSE 2
            END,
            t.next_run
        """,
        (cutoff_24h,),
    ).fetchall()

    # --- Load group names ---
    groups = {}
    try:
        for row in db.execute("SELECT folder, name FROM registered_groups"):
            groups[row["folder"]] = row["name"]
    except Exception:
        pass

    if not tasks:
        st.info("No scheduled tasks. Tasks are created by agents via IPC.")
        return

    # --- Section A: Task list ---
    # Filter controls
    col_status, col_group, col_type = st.columns(3)
    with col_status:
        status_filter = st.selectbox(
            "Status", ["active", "(all)", "paused", "completed"], index=0
        )
    with col_group:
        all_groups = sorted(set(t["group_folder"] for t in tasks))
        group_filter = st.selectbox("Group", ["(all)"] + all_groups, index=0)
    with col_type:
        type_filter = st.selectbox(
            "Type", ["(all)", "cron", "interval", "once"], index=0
        )

    filtered = tasks
    if status_filter != "(all)":
        filtered = [t for t in filtered if t["status"] == status_filter]
    if group_filter != "(all)":
        filtered = [t for t in filtered if t["group_folder"] == group_filter]
    if type_filter != "(all)":
        filtered = [t for t in filtered if t["schedule_type"] == type_filter]

    rows = []
    for t in filtered:
        prompt_short = (t["prompt"] or "")[:80].replace("\n", " ")
        group_label = groups.get(t["group_folder"], t["group_folder"])
        last_status = t["last_run_status"]
        last_icon = (
            "✅" if last_status == "success" else "❌" if last_status == "error" else "—"
        )
        rows.append(
            {
                "": status_icon(t["status"]),
                "Group": group_label,
                "Prompt": prompt_short,
                "Schedule": fmt_schedule(t["schedule_type"], t["schedule_value"]),
                "Context": t["context_mode"] or "isolated",
                "Next run": fmt_dt(t["next_run"]),
                "Last run": fmt_dt(t["actual_last_run"]),
                "Last": last_icon,
                "Err 24h": int(t["errors_24h"] or 0),
                "Runs": int(t["total_runs"] or 0),
            }
        )

    st.caption(f"{len(filtered)} task(s)")
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)

    # --- Section B: Run history for selected task ---
    st.divider()
    st.subheader("Run history")

    task_labels = []
    task_ids = []
    for t in tasks:
        group_label = groups.get(t["group_folder"], t["group_folder"])
        prompt_short = (t["prompt"] or "")[:50].replace("\n", " ")
        label = f"{status_icon(t['status'])} [{group_label}] {prompt_short}"
        task_labels.append(label)
        task_ids.append(t["id"])

    if not task_labels:
        return

    selected_idx = st.selectbox(
        "Select task",
        range(len(task_labels)),
        format_func=lambda i: task_labels[i],
    )
    selected_task_id = task_ids[selected_idx]
    selected_task = tasks[selected_idx]

    # Task detail card
    with st.expander("Task details", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**ID:** `{selected_task['id']}`")
            st.markdown(f"**Group:** {groups.get(selected_task['group_folder'], selected_task['group_folder'])}")
            st.markdown(f"**Status:** {status_icon(selected_task['status'])} {selected_task['status']}")
            st.markdown(f"**Context:** {selected_task['context_mode'] or 'isolated'}")
            st.markdown(f"**Created:** {fmt_dt(selected_task['created_at'])}")
        with col2:
            st.markdown(f"**Schedule:** {fmt_schedule(selected_task['schedule_type'], selected_task['schedule_value'])}")
            st.markdown(f"**Next run:** {fmt_dt(selected_task['next_run'])}")
            st.markdown(f"**Last run:** {fmt_dt(selected_task['last_run'])}")
            st.markdown(f"**Chat JID:** `{selected_task['chat_jid']}`")
        st.markdown("**Prompt:**")
        st.code(selected_task["prompt"], language="text")
        if selected_task["script"]:
            st.markdown("**Pre-wake script:**")
            st.code(selected_task["script"], language="bash")

    # Run logs
    runs = db.execute(
        """
        SELECT * FROM task_run_logs
        WHERE task_id = ?
        ORDER BY run_at DESC
        LIMIT 100
        """,
        (selected_task_id,),
    ).fetchall()

    if not runs:
        st.info("No runs recorded for this task yet.")
        return

    run_rows = []
    for r in runs:
        run_rows.append(
            {
                "When": fmt_dt(r["run_at"]),
                "Duration": fmt_duration(r["duration_ms"]),
                "Status": "✅" if r["status"] == "success" else "❌",
                "Result": (r["result"] or "")[:120].replace("\n", " "),
                "Error": (r["error"] or "")[:120].replace("\n", " "),
            }
        )

    st.dataframe(run_rows, use_container_width=True, hide_index=True)

    # Log viewer for selected run
    st.divider()
    run_labels = [
        f"{fmt_dt(r['run_at'])}  {'✅' if r['status'] == 'success' else '❌'}  {fmt_duration(r['duration_ms'])}"
        for r in runs
    ]
    run_idx = st.selectbox(
        "View run details",
        range(len(run_labels)),
        format_func=lambda i: run_labels[i],
    )
    selected_run = runs[run_idx]

    col_result, col_error = st.columns(2)
    with col_result:
        st.caption("Result")
        st.code(selected_run["result"] or "(empty)", language="text")
    with col_error:
        st.caption("Error")
        st.code(selected_run["error"] or "(empty)", language="text")


if __name__ == "__main__":
    main()
