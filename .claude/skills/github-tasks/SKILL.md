---
name: github-tasks
description: Manage tasks in GitHub Issues — create, triage, approve, work, delegate, and report results. Use when handling the 4-hourly todo cycle or when the user asks to create/manage tasks.
---

# GitHub Tasks

Manage the task backlog in `landovsky/nanoclaw-tasks` using GitHub Issues and `gh` CLI.

## Repository

- **Repo**: `landovsky/nanoclaw-tasks` (private)
- **Project board**: https://github.com/users/landovsky/projects/7/views/1

## Task Lifecycle

```
[create] → [draft] → [ready] → [approved] → [in-progress] → [review] → [done]
                                      ↘ [blocked] ↗           ↗
```

### 1. Create

Anyone (Tomas via mobile, Claude via CLI, cron cycle) creates an issue using the template:

```markdown
## Goal
What should be done? One sentence.

## Context
Why is this needed? Link to related issues/conversations if relevant.

## Deliverable
What does "done" look like? File, report, code change, message?

## Notes
Optional: constraints, preferences, who should do this (Andy?), links.
```

```bash
gh issue create --repo landovsky/nanoclaw-tasks \
  --title "Short description" \
  --body "$(cat <<'EOF'
## Goal
...

## Context
...

## Deliverable
...
EOF
)"
```

New issues start unlabelled (implicit `draft`). The template is also available in GitHub's "New issue" UI.

### 2. Triage (Claude's gate before approval)

During each cycle, assess every unlabelled issue against three criteria:

1. **Goal clear?** — Is the expected outcome unambiguous?
2. **Scope bounded?** — Can it be completed in one work session (<30 min)?
3. **Inputs available?** — Data, access, dependencies, context — all resolved?

**Decision:**

- **All three pass** → add `ready` label + comment: "Ready for approval. [1-line summary of what I'll do]"
- **Any fail** → add `blocked` label + comment with **numbered questions** for Tomas to answer

```bash
# Example: issue is incomplete
export GH_TOKEN=$(/home/tomas/.dotfiles/bin/github-app-token)
gh issue edit --repo landovsky/nanoclaw-tasks <N> --add-label blocked
gh issue comment --repo landovsky/nanoclaw-tasks <N> --body "Needs clarification before this can be approved:
1. What date range should the report cover?
2. Should the output be CSV or markdown?"
```

When Tomas answers, the next cycle re-triages: remove `blocked`, reassess, label `ready` if resolved.

### 3. Approve

Tomas adds the `approved` label (via GitHub mobile or web). Only `approved` issues get worked on. **Never self-approve** — wait for Tomas.

### 4. Work

Pick approved issues, smallest scope first:

```bash
# Get app token for bot identity
export GH_TOKEN=$(/home/tomas/.dotfiles/bin/github-app-token)

# Signal start
gh issue comment --repo landovsky/nanoclaw-tasks <number> \
  --body "Starting work on this."

# ... do the work ...

# Post results and move to review
gh issue edit --repo landovsky/nanoclaw-tasks <number> \
  --remove-label approved --add-label review
gh issue comment --repo landovsky/nanoclaw-tasks <number> \
  --body "Done. <summary of what was done + results>"
```

If stuck, remove `approved`, add `blocked`, comment explaining why:

```bash
gh issue edit --repo landovsky/nanoclaw-tasks <number> \
  --remove-label approved --add-label blocked
gh issue comment --repo landovsky/nanoclaw-tasks <number> \
  --body "Blocked: <reason>"
```

### 5. Review

Tomas reviews results on the issue. **Claude never closes issues** — only Tomas does.

- **Satisfied** → Tomas closes the issue
- **Needs changes** → Tomas comments with feedback, removes `review`, adds `approved` → Claude reworks next cycle

### 6. Report

When a task produces a deliverable (report, CSV, analysis):
1. Save to `/home/tomas/nano-claw-workdir/` with a descriptive filename
2. Post the full content as a GitHub issue comment (Tomas reads on mobile)

## Labels

| Label | Meaning |
|-------|---------|
| *(none)* | Draft — needs triage |
| `ready` | Triaged, all 3 criteria pass, waiting for Tomas to approve |
| `approved` | Tomas approved — work on it next cycle |
| `review` | Work done, results posted — waiting for Tomas to review and close |
| `blocked` | Missing info or dependency — questions posted as comment |

## Authentication

Two tokens, two purposes:

| Token | Source | Use for |
|-------|--------|---------|
| `GITHUB_TOKEN` | `~/.dotfiles/.github_token` | Reading issues, listing labels |
| App token | `/home/tomas/.dotfiles/bin/github-app-token` | Posting comments as `nanoclaw-agent-kopernici[bot]` |

**Rule**: Always use the app token (`GH_TOKEN`) when commenting so comments appear as the bot, not as Tomas. Use `GITHUB_TOKEN` (or default `gh` auth) for reads.

```bash
# Pattern for commenting
export GH_TOKEN=$(/home/tomas/.dotfiles/bin/github-app-token)
gh issue comment --repo landovsky/nanoclaw-tasks <number> --body "..."
unset GH_TOKEN  # revert to default auth for subsequent reads
```

## Delegation to Andy

When an approved issue requires swan_crm work (CRM, venues, prospects, emails):

```bash
cat > /home/tomas/git/nanoclaw/data/ipc/swan_crm/tasks/task-$(date +%Y%m%d-%H%M).json << 'EOF'
{
  "type": "schedule_task",
  "prompt": "Task description for Andy...",
  "targetJid": "slack:C0APKCNF4KE",
  "schedule_type": "once",
  "schedule_value": "NOW"
}
EOF
```

After delegating, comment on the issue that work was delegated to Andy.

## 4-Hourly Cycle Protocol

The cron job (`17 */4 * * *`) triggers the cycle via IPC. When executing a cycle:

### Phase 1: Poll & Triage
1. List all open issues: `gh issue list --repo landovsky/nanoclaw-tasks --state open --json number,title,labels,body,comments`
2. Check for new comments from Tomas (login: `landovsky`) — respond to questions
3. Triage unlabelled issues — assess against 3 criteria (goal clear? scope bounded? inputs available?), label `ready` or `blocked` with comment
4. Post board summary to chat

### Phase 2: Work (30 min budget)
1. List approved issues: `gh issue list --repo landovsky/nanoclaw-tasks --label approved --state open`
2. Work on each, smallest first
3. For each: comment start → do work → comment results → label `review` (or `blocked`)
4. Save deliverables to `/home/tomas/nano-claw-workdir/` AND post to issue

### Rules
- **30 min total** work budget per cycle
- **Never work on unapproved issues**
- **Smallest scope first** — maximize throughput
- **Deliverables go to both** file and issue comment
- **Bot identity** for all comments (use app token)
- Comments from Claude show as `nanoclaw-agent-kopernici[bot]`
- Comments from Tomas show as `landovsky`

## Quick Reference

```bash
# List all open issues
gh issue list --repo landovsky/nanoclaw-tasks --state open

# List approved issues
gh issue list --repo landovsky/nanoclaw-tasks --label approved --state open

# Create an issue
gh issue create --repo landovsky/nanoclaw-tasks --title "..." --body "..."

# Add/remove labels
gh issue edit --repo landovsky/nanoclaw-tasks <N> --add-label approved
gh issue edit --repo landovsky/nanoclaw-tasks <N> --remove-label approved --add-label blocked

# Comment as bot
export GH_TOKEN=$(/home/tomas/.dotfiles/bin/github-app-token)
gh issue comment --repo landovsky/nanoclaw-tasks <N> --body "..."

# Move to review (after work is done)
gh issue edit --repo landovsky/nanoclaw-tasks <N> --remove-label approved --add-label review

# View issue details
gh issue view --repo landovsky/nanoclaw-tasks <N>
```
