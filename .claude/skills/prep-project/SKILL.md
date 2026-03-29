---
name: prep-project
description: Prepare a self-contained project document for a new Andy sub-project. Explores existing infrastructure, defines objectives and funnel, surfaces open questions, and produces a checklist-driven doc in /home/tomas/nano-claw-workdir/.
---

# /prep-project — New Andy Sub-Project Setup

Produces a self-contained project document that can be used to track progress from planning through to autonomous operation. Run this at the start of any new Andy project idea.

## Step 0: Check Prior Work & Architecture

Before anything else:

1. **Read the architecture document** at `/home/tomas/nano-claw-workdir/nanoclaw-architecture.md`. This is the authoritative reference for how domains work in NanoClaw. Understand:
   - The five architectural questions every domain must answer (Section 3)
   - Existing access patterns (Section 5) — prefer reusing one over inventing a new one
   - Data ownership principles (Section 6) — where different types of data should live
   - The domain registry (Section 4) — what already exists

2. Check `/home/tomas/nano-claw-workdir/assessments/` for any existing assessment on this project.

3. Query the memory-store (`group_id: "global"` and the project's group_id) for prior context, decisions, or notes.

4. Check if a NanoClaw group already exists for this project (`groups/` directory, DB registration).

5. If prior work exists, read it and carry forward anything still relevant. Don't re-explore what's already been explored.

## Step 1: Gather Context

Ask the user (or infer from conversation) the following if not already known:

1. **Project name / ID** — short slug, becomes the NanoClaw `group_id` (e.g. `lekarny`, `swan_crm`)
2. **What does Andy need to accomplish?** — the primary loop Andy will run (e.g. outreach, monitoring, research)
3. **What systems are involved?** — repos, databases, external APIs, Slack channels
4. **What's the end state?** — how do we know this is "done and running well"?

If the user provides a rough description, proceed with Step 2 without asking all four — infer where possible.

## Step 2: Explore Existing Infrastructure

**If there's a local codebase** (Rails app, Node project, etc.):
- Read the schema (db/schema.rb, prisma schema, migrations)
- Read key models, mailers, jobs related to the domain
- Identify existing tracking/reporting infrastructure
- Check for existing email templates, campaign systems, API endpoints

**If there's no local codebase** (external APIs, managed services, IoT):
- Document what APIs/services are involved and what credentials are needed
- Check for existing integrations in the NanoClaw container or skills
- Identify what Andy can already access vs. what needs to be set up

Summarize findings as two lists: **What already exists** and **What's missing**.

## Step 3: Understand the Product / Domain

This is critical — Andy can't do useful work without domain knowledge. Find:

- What is the product/service? What problem does it solve?
- Who are the users/customers? What do they care about?
- What's the value proposition / sales pitch?
- Read marketing copy, landing pages, email templates, README, or ask the user

This becomes the "About the Platform" section and feeds into the "Context for Andy" draft CLAUDE.md.

## Step 4: Define the Funnel

Write a short ASCII funnel showing the end-to-end flow Andy will manage:

```
Starting state (e.g. lead in DB)
  → Andy action 1 (e.g. sends personalized email)
    → Signal (e.g. reply or open)
      → Andy action 2 (e.g. logs call, advances stage)
        → End state (e.g. paying customer)
```

## Step 5: Answer the Five Architectural Questions

Reference the architecture document (Section 3). For this domain, answer:

1. **Where does truth live?**
2. **What role does memory-store play?**
3. **How does Andy access the domain?**
4. **What does Andy own vs. what does Tomas own?**
5. **What's the feedback loop?**

If any question can't be answered yet, flag it as an open question — but explain the implications of deferring it (what gets built on assumptions, what might need rework).

## Step 6: Check for Architecture Implications

Compare this domain's needs against the architecture document:

- Does this domain introduce a **new access pattern** not listed in Section 5?
- Does it change the **data ownership model** in a way that conflicts with Section 6?
- Does it require **new shared infrastructure** (a new MCP server, a new credential type)?
- Does it create **cross-domain dependencies** (e.g. a pharmacy that also uses Černá Labuť)?

If yes to any: write an **"Architecture Implications"** section in the project document. This section:
- Describes what would change at the platform level
- Proposes specific edits to the architecture document
- Does NOT modify the architecture document directly
- Flags the change for Tomas to review and consciously approve

## Step 7: Write the Project Document

Save to `/home/tomas/nano-claw-workdir/{project-id}-project.md` using this structure:

```markdown
# {Project Name} — Project Document

**Project ID:** `{id}`
**Slack channel:** TBD or known ID
**NanoClaw group:** `{id}` (created / not yet created)
**Last updated:** {date}
**Status:** Planning

## Objective
One paragraph. What Andy does, why it matters, what the outcome is.

## About the Platform / Domain
What the product/service does. The pitch. Key numbers.
Mark anything uncertain with: > **TOMAS: [question]**

## The Funnel
ASCII diagram.

## Success Criteria
Table: Metric | Target | How tracked
Note: flag any targets that are aspirational guesses vs. grounded in data.

## What Already Exists
Tables or bullets of existing schema, infrastructure, integrations.

## Personalization Data / Input Data
What data is available for Andy to work with. Table format.

## What's Missing
Bullet list of gaps.

## Scope
### In Scope (checkboxes)
### Out of Scope (bullets, with brief reason)

## Domain Architecture (Five Questions)
Table answering the five questions from nanoclaw-architecture.md Section 3.

## Architecture
How Andy talks to the system (API, DB, MCP tools, bash scripts).
Memory-store integration: what goes in the graph vs. the primary DB.
NanoClaw group config.
Key flows (one per major Andy action).
Sending pace / rate limits if applicable.

## Architecture Implications (if any)
Proposed changes to nanoclaw-architecture.md.
Only present if this domain introduces new patterns.

## To-Do Checklist
Phased. Each item is a checkbox. Owner in parens: (Tomas), (Claude Code), (Andy).
Phase 1: Access & Infrastructure
Phase 2: First Run
Phase 3: Tracking & Reporting
Phase 4: Iterate

## Open Questions
Table: # | Question | Who | Blocks | Impact (HIGH/MEDIUM/LOW)
Sort by impact. Mark the 2-3 that must be answered before anything can be built.
Include implications of deferring each question.

## Context for Andy (draft CLAUDE.md)
Three subsections:
1. Product knowledge — what Andy needs to know about the domain
2. Rules — what Andy must/must not do, approval workflows, guardrails
3. Operational details — tone, language, personalization approach, memory-store usage
Write in whatever language Andy will operate in (Czech for Czech-facing projects).
Mark anything the user needs to verify with: > **TOMAS: [question]**

## Decisions Log
Table: Date | Decision | By
```

### Formatting rules for the document

- Items that need the user's attention must stand out. Use blockquotes:
  > **TOMAS: [specific question or review request]**
- Every open question in the table should include an impact rating AND what happens if deferred
- The "Context for Andy" section is NOT just rules — it must include the domain knowledge Andy needs to actually do the job (product pitch, customer segments, key numbers)
- When a project has an existing codebase, read the schema before writing the architecture section — never guess at model names or column names
- Success criteria should note whether targets are grounded in data or aspirational

## Step 8: Validate with the User

After writing the document, post a brief summary:

- Where the document was saved
- The 2–3 open questions that block all build work
- Any architecture implications that need review
- Call out the `> TOMAS:` markers — these need review before the doc becomes the source of truth
- **Explicitly state what cannot be built yet and why** — hold the user accountable for deferred decisions

Do NOT treat the first draft as final. The user will have corrections, especially on the product pitch, success targets, and Andy rules.

Do NOT begin implementation while HIGH-impact open questions remain unanswered, unless the user explicitly acknowledges what's being assumed and the rework risk.

## Output Location

Always save to: `/home/tomas/nano-claw-workdir/{project-id}-project.md`

Never save to the nanoclaw repo or the project's own repo — this is a living planning document, not checked-in code.

## Reference

- **Architecture document:** `/home/tomas/nano-claw-workdir/nanoclaw-architecture.md` — read before every new project
- **Lekarny CRM project:** `/home/tomas/nano-claw-workdir/lekarny-crm-project.md` — worked example for structure and detail
