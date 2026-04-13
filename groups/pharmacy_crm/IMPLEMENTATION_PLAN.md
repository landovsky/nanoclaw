# pharmacy-crm: Implementation Plan (Rails-Only + MailJet)

## Phase 0: Infrastructure Setup (Day 1-2)

### 0.1 Rails API Development (delegated to AI maintainer)
- [ ] Share `RAILS_API_PROMPT.md` with Rails app maintainer
- [ ] Review & merge PR (Campaign enhancements, PharmacyOutreach model, OutreachEvent model, migrations, API endpoints, CrmMailer, MailJet webhook, Avo resources)
- [ ] Generate `CRM_API_TOKEN`, store in OneCLI vault / .env
- [ ] Configure MailJet webhook URL (`POST /webhooks/mailjet`) in MailJet dashboard for events: Sent, Open, Click, Bounce, Spam, Blocked, Unsub
- [ ] Verify in Avo: PharmacyOutreach and OutreachEvent resources visible, filterable

### 0.2 NanoClaw Group Setup (parallel with 0.1)
- [ ] Slack channel `#pharmacy-crm` exists (done)
- [ ] Register NanoClaw group:
  - folder: `pharmacy_crm`
  - jid: `slack:{channel_id}` (get channel ID from Slack)
  - trigger: `@Andy`
- [ ] Write initial `CLAUDE.md` (group instructions for Andy)
- [ ] Configure container mounts:
  - Additional mount: `/home/tomas/git/pharmacy` (readonly, for reference)
- [ ] Store `CRM_API_TOKEN` in container environment (OneCLI vault)
- [ ] Test: Andy responds in `#pharmacy-crm`
- [ ] Test: Andy can call Rails CRM API from container

**Phase 0 exit criteria**: Andy can query/update outreach records and send a test email via the Rails API, and communicate in Slack. MailJet webhooks are flowing into OutreachEvent table.

---

## Phase 1: Campaign Setup & First Batch (Day 3)

### 1.1 Create Campaign
- [ ] Create campaign via `POST /api/v1/crm/campaigns` with:
  - Strategy: 3-step sequence (initial → follow_up_1 at +5d → follow_up_2 at +5d)
  - Primary goal: `meeting_booked`
  - Secondary goal: `replied` (auto-detected)
  - Stop conditions: reply, goal_primary, opt_out, bounce

### 1.2 Create First Batch
- [ ] Andy calls `POST /api/v1/crm/outreach/batch` to add pharmacies to campaign
- [ ] Select ~30 pharmacies for pilot batch (non-contracted, marketing-opted-in)
- [ ] Assign template versions: 15 x v1, 15 x v2 (A/B test)
- [ ] Verify in Avo: PharmacyOutreach records at status `active`, step 0

### 1.3 Validation
- [ ] No active-contract pharmacies in batch (auto-filtered by API)
- [ ] All pharmacies have valid email addresses
- [ ] Spot-check 5 records in Avo — correct data

**Phase 1 exit criteria**: Campaign created with strategy. 30 PharmacyOutreach records active, ready to send.

---

## Phase 2: Email Templates & Rules of Engagement (Day 2-3, parallel with Phase 0)

### 2.1 Initial Outreach Template
- [ ] Draft template v1 (Czech, formal-but-approachable tone)
- [ ] Draft template v2 (variant for A/B testing — different angle/CTA)
- [ ] For pharmacies with prior interaction notes: personalization prefix ("Navazujeme na nasi predchozi komunikaci...")
- [ ] Verify unsubscribe link works (existing Rails EmailSubscription system)
- [ ] Store templates in `groups/pharmacy_crm/templates/`

### 2.2 Follow-up Templates
- [ ] Follow-up 1 template (sent ~5 days after initial, shorter, different angle)
- [ ] Follow-up 2 template (sent ~5 days after FU1, final attempt, direct CTA)
- [ ] Define follow-up timing rules (configurable in CLAUDE.md)

### 2.3 Reply Rules of Engagement
Document in CLAUDE.md:
- [ ] Positive reply (interested) -> propose meeting times, record `goal_primary` event
- [ ] Neutral reply (questions) -> answer, keep conversation going
- [ ] Negative reply (not interested) -> polite close, record `opted_out` event
- [ ] Out-of-office -> reschedule follow-up
- [ ] "Who are you?" -> reference dostupnost-leku.cz, explain value prop
- [ ] All replies require Slack approval before sending

**Phase 2 exit criteria**: Templates reviewed and approved by Tomas. Rules of engagement documented in CLAUDE.md.

---

## Phase 3: First Emails & Automation (Day 4-5)

### 3.1 Pilot Send
- [ ] Andy sends pilot batch via `POST /api/v1/crm/emails` (one at a time, paced)
- [ ] Andy advances outreach step via `PATCH /api/v1/crm/outreach/:id`
- [ ] Verify: emails received (check 2-3 manually)
- [ ] Verify: MailJet webhooks creating OutreachEvent records (sent, open, click)
- [ ] Verify: Avo shows events on outreach records

### 3.2 Daily Round Automation
- [ ] Create NanoClaw scheduled task (cron: weekdays 9:00 CET):
  1. `GET /api/v1/crm/outreach?ready_to_send=true` — send new outreach emails
  2. `GET /api/v1/crm/outreach?due_for_follow_up=true` — send follow-ups
  3. Check for replies (IMAP)
  4. Post daily report to #pharmacy-crm (stats from `GET /api/v1/crm/campaigns/:id/stats`)
- [ ] Test scheduled task execution
- [ ] Verify daily report format and content

### 3.3 Reply & Handover Flow Test
- [ ] Simulate a reply (send from test email)
- [ ] Verify Andy drafts response in Slack thread
- [ ] Test approval flow (Tomas approves in thread)
- [ ] Test edit flow (Tomas suggests changes in thread)
- [ ] Test handover flow ("Prebiram komunikaci" -> andy_can_communicate=false)
- [ ] Test hand-back flow ("Andy, prevezmi [pharmacy]" -> andy_can_communicate=true)

**Phase 3 exit criteria**: First 30 emails sent, daily automation running, MailJet webhooks flowing, reply + handover flows tested end-to-end.

---

## Phase 4: Scale & Measure (Week 2+)

### 4.1 Ramp Up
- [ ] Add new batches of 30-50 pharmacies weekly to the campaign
- [ ] Monitor deliverability via MailJet dashboard (bounces, spam complaints)
- [ ] Increase batch size based on results

### 4.2 Performance Reporting
- [ ] Weekly: `GET /api/v1/crm/campaigns/:id/stats` — full funnel + template comparison
- [ ] Decide winning template variant, phase out underperformer
- [ ] Create new variants to test against winner

### 4.3 Ongoing Operations
- [ ] Daily: Andy sends emails, follows up, drafts replies, reports
- [ ] Weekly: Performance review, template optimization
- [ ] Monthly: Tomas reviews conversion pipeline in Avo, adjusts strategy
- [ ] Quarterly: Newsletter planning (future scope)

### 4.4 New Campaign Types (future)
- [ ] Upsell campaigns for existing customers (different goal, strategy, templates)
- [ ] Re-engagement campaigns for lapsed contacts
- [ ] Each new campaign type reuses the same infrastructure — just different strategy JSON and goal config

**Phase 4 exit criteria**: Steady state — 30-50 emails/week, measurable conversion funnel, MailJet metrics flowing automatically.

---

## Data Model Overview

```
Campaign
├── strategy (JSON: step sequence, stop conditions)
├── goal_primary (meeting_booked, demo_scheduled, reply, etc.)
├── goal_secondary (replied, clicked, etc. — nullable)
└── status (draft, active, paused, completed)

PharmacyOutreach (per pharmacy per campaign)
├── current_step (index into campaign strategy)
├── status (active, paused, completed, opted_out)
├── template_version (for A/B testing)
├── andy_can_communicate
└── next_action_at

OutreachEvent (event log — populated by MailJet webhooks + IMAP + manual)
├── pharmacy_outreach_id
├── event_type (sent, opened, clicked, bounced, spam, blocked, unsubscribed, replied, goal_primary, goal_secondary)
├── occurred_at
└── metadata (JSONB)
```

## Event Sources

| Event | Source |
|-------|--------|
| sent | MailJet webhook |
| opened | MailJet webhook |
| clicked | MailJet webhook |
| bounced | MailJet webhook |
| spam | MailJet webhook |
| blocked | MailJet webhook |
| unsubscribed | MailJet webhook |
| replied | IMAP detection (Andy's daily round) |
| goal_primary | Manual (Tomas in Avo or tells Andy) |
| goal_secondary | Auto-detected when matching event fires, or manual |

---

## Dependencies

```
Phase 0.1 (Rails API + MailJet webhooks) ──┐
                                            ├──> Phase 1 (Campaign + batch) ──> Phase 3 (Send & automate)
Phase 0.2 (NanoClaw group) ────────────────┘
                                                 Phase 2 (Templates) ──────────────────────┘
```

Phase 2 (templates) can happen in parallel with everything — it's just writing text.

## Risks

| Risk | Mitigation |
|------|------------|
| Rails API PR delayed | Template work (Phase 2) can proceed in parallel |
| MailJet rate limits | Send in small batches (30-50), paced across morning hours |
| Low open rates | Test subject lines, sender name, send times |
| Spam folder delivery | Warm up gradually, monitor MailJet reputation dashboard |
| MailJet webhook delivery failures | Implement idempotent event processing, MailJet retries automatically |

## Timeline Summary

| Phase | Duration | Notes |
|-------|----------|-------|
| Phase 0: Infrastructure | Day 1-2 | Rails API + NanoClaw group + MailJet webhook setup |
| Phase 1: Campaign setup | Day 3 | Campaign creation + first batch |
| Phase 2: Templates | Day 2-3 | Parallel with Phase 0 |
| Phase 3: First emails | Day 4-5 | After all above |
| Phase 4: Scale | Week 2+ | Ongoing |

**Total time to first emails sent: ~5 days.**
