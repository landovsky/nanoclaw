# Rails API & Model for CRM Email Outreach

## Context

We're building a cold email outreach system for pharmacies to join the dostupnost-leku.cz platform. An AI agent (Andy) orchestrates campaigns and needs a Rails API to manage outreach state, send emails, and track events. **Rails is the single source of truth** — no external CRM. Andy queries the API to know what to send, sends it, and updates the record.

The Rails app already has:
- `Pharmacy` (with `deal_status`, `contact_owner`, `notes`, `primary_contact`, `sample_group`, `deliver_marketing_emails`) + `Company` + `Contract`
- `Email` + `EmailTracking` + `Campaign` models (send, track opens, campaign grouping)
- `PharmacyMailer.intro_campaign` (existing campaign send logic)
- Avo admin with a CRM panel on Pharmacy
- Bearer token API auth pattern in `ApiController`
- Sidekiq for background jobs

**Sender**: `tomas@dostupnost-leku.cz` (via MailJet)
**Authentication**: Bearer token via `Authorization: Bearer <token>` header. Store the token in `CRM_API_TOKEN` env var. Reject with 401 if missing/invalid.
**Event tracking**: MailJet webhooks deliver sent/open/click/bounce/spam/blocked/unsub events. Reply detection and goal tracking are handled externally by Andy.

---

## Part 1: Campaign Model Enhancements

The existing `Campaign` model needs new fields to support configurable campaign strategies and goals.

### Migration

```ruby
class AddStrategyFieldsToCampaigns < ActiveRecord::Migration[7.1]
  def change
    add_column :campaigns, :goal_primary, :string             # e.g. "meeting_booked", "demo_scheduled", "reply"
    add_column :campaigns, :goal_secondary, :string           # e.g. "replied", "clicked" (nullable)
    add_column :campaigns, :goal_secondary_auto, :boolean, null: false, default: false  # auto-mark when event fires
    add_column :campaigns, :strategy, :jsonb, null: false, default: {}
    add_column :campaigns, :status, :string, null: false, default: 'draft'
    add_column :campaigns, :started_at, :datetime
    add_column :campaigns, :completed_at, :datetime
    add_column :campaigns, :metadata, :jsonb, null: false, default: {}
  end
end
```

### Strategy JSON Schema

The `strategy` field defines the email sequence:

```jsonc
{
  "steps": [
    { "name": "initial",     "delay_days": 0, "template_key": "initial" },
    { "name": "follow_up_1", "delay_days": 5, "template_key": "follow_up_1" },
    { "name": "follow_up_2", "delay_days": 5, "template_key": "follow_up_2" }
  ],
  "stop_on": ["replied", "goal_primary", "opted_out", "bounced"],
  "max_attempts": 3
}
```

- `steps[].delay_days`: days after previous step (0 for first step = send immediately when ready)
- `stop_on`: event types that halt the sequence for a contact
- `max_attempts`: safety cap on total steps

### Model Changes

```ruby
class Campaign < ApplicationRecord
  # ... existing associations ...

  has_many :pharmacy_outreaches, dependent: :restrict_with_error

  enum :status, {
    draft: 'draft',
    active: 'active',
    paused: 'paused',
    completed: 'completed'
  }, prefix: true

  def step_count
    strategy.dig('steps')&.length || 0
  end

  def stop_events
    strategy.dig('stop_on') || []
  end
end
```

---

## Part 2: New Model — `PharmacyOutreach`

Tracks the outreach pipeline state per pharmacy per campaign.

### Migration

```ruby
class CreatePharmacyOutreaches < ActiveRecord::Migration[7.1]
  def change
    create_table :pharmacy_outreaches do |t|
      t.references :pharmacy, null: false, foreign_key: true
      t.references :campaign, null: false, foreign_key: true
      t.integer    :current_step, null: false, default: 0      # index into campaign.strategy.steps
      t.string     :status, null: false, default: 'active'     # active, paused, completed, opted_out
      t.string     :template_version                            # for A/B testing within a step
      t.string     :batch_name                                  # batch identifier
      t.boolean    :andy_can_communicate, null: false, default: true
      t.datetime   :next_action_at                              # when the next step is due
      t.string     :completed_reason                            # goal_achieved, opted_out, exhausted, manual, bounced
      t.text       :outreach_notes
      t.timestamps

      t.index [:pharmacy_id, :campaign_id], unique: true
    end

    # Prevent same pharmacy being actively targeted by multiple campaigns
    add_index :pharmacy_outreaches, [:pharmacy_id, :status],
              where: "status = 'active'",
              unique: true,
              name: 'index_pharmacy_outreaches_on_active_pharmacy'
  end
end
```

### Model

```ruby
class PharmacyOutreach < ApplicationRecord
  belongs_to :pharmacy
  belongs_to :campaign
  has_many :outreach_events, dependent: :destroy

  enum :status, {
    active: 'active',
    paused: 'paused',
    completed: 'completed',
    opted_out: 'opted_out'
  }, prefix: true

  scope :due_for_follow_up, -> {
    where(andy_can_communicate: true, status: 'active')
      .where('current_step > 0')
      .where('next_action_at <= ?', Time.current)
  }

  scope :ready_to_send, -> {
    where(andy_can_communicate: true, status: 'active', current_step: 0)
  }

  scope :active_outreach, -> {
    where(status: 'active')
  }

  validates :pharmacy_id, uniqueness: { scope: :campaign_id }

  def current_step_name
    campaign.strategy.dig('steps', current_step, 'name')
  end

  def sequence_exhausted?
    current_step >= campaign.step_count
  end
end
```

### Avo Resource

Create `app/avo/resources/pharmacy_outreach.rb`. Fields to expose:

**Index columns:** pharmacy (link), campaign (link), status (badge), current_step, template_version, batch_name, next_action_at, andy_can_communicate

**Show/Edit panels:**
- **Main**: pharmacy (belongs_to), campaign (belongs_to), status (select), current_step, template_version, batch_name
- **Communication**: andy_can_communicate (boolean), outreach_notes (textarea), completed_reason
- **Timeline**: next_action_at
- **Events**: has_many :outreach_events (table showing event_type, occurred_at, metadata)

**Filters:**
- Status (select)
- Batch name (text)
- Andy can communicate (boolean)
- Campaign (select)

**Scopes (tabs on index):** All, Ready to send, Due for follow-up, Active, Completed, Opted out

---

## Part 3: New Model — `OutreachEvent`

Event log for all outreach interactions. Populated by MailJet webhooks, IMAP reply detection, and manual actions.

### Migration

```ruby
class CreateOutreachEvents < ActiveRecord::Migration[7.1]
  def change
    create_table :outreach_events do |t|
      t.references :pharmacy_outreach, null: false, foreign_key: true
      t.string     :event_type, null: false  # sent, opened, clicked, bounced, spam, blocked, unsubscribed, replied, goal_primary, goal_secondary
      t.datetime   :occurred_at, null: false
      t.jsonb      :metadata, null: false, default: {}  # e.g. email_id, mailjet_message_id, link_url, user_agent
      t.timestamps

      t.index [:pharmacy_outreach_id, :event_type]
      t.index :event_type
      t.index :occurred_at
    end
  end
end
```

### Model

```ruby
class OutreachEvent < ApplicationRecord
  belongs_to :pharmacy_outreach

  EVENT_TYPES = %w[sent opened clicked bounced spam blocked unsubscribed replied goal_primary goal_secondary].freeze

  validates :event_type, inclusion: { in: EVENT_TYPES }
  validates :occurred_at, presence: true

  scope :by_type, ->(type) { where(event_type: type) }
  scope :since, ->(time) { where('occurred_at >= ?', time) }

  after_create :check_stop_conditions
  after_create :check_goal_secondary_auto

  private

  def check_stop_conditions
    outreach = pharmacy_outreach
    campaign = outreach.campaign
    return unless outreach.status_active?

    if campaign.stop_events.include?(event_type)
      reason = case event_type
               when 'goal_primary' then 'goal_achieved'
               when 'opted_out', 'unsubscribed' then 'opted_out'
               when 'bounced' then 'bounced'
               else 'manual'
               end
      status = (event_type.in?(%w[opted_out unsubscribed]) ? 'opted_out' : 'completed')
      outreach.update!(status: status, completed_reason: reason)
    end
  end

  def check_goal_secondary_auto
    campaign = pharmacy_outreach.campaign
    return unless campaign.goal_secondary_auto
    return unless event_type == campaign.goal_secondary

    # Auto-create goal_secondary event if this event matches
    unless pharmacy_outreach.outreach_events.exists?(event_type: 'goal_secondary')
      pharmacy_outreach.outreach_events.create!(
        event_type: 'goal_secondary',
        occurred_at: occurred_at,
        metadata: { auto_from: event_type }
      )
    end
  end
end
```

### Avo Resource

Create `app/avo/resources/outreach_event.rb`:

**Index columns:** pharmacy_outreach (link), event_type (badge), occurred_at, metadata
**Filters:** event_type (select), date range

---

## Part 4: Email Model Changes

### Migration

```ruby
class AddOutreachFieldsToEmails < ActiveRecord::Migration[7.1]
  def change
    add_column :emails, :template_version, :string
    add_reference :emails, :pharmacy, foreign_key: true
    add_column :emails, :mailjet_message_id, :string  # for webhook correlation
    add_reference :emails, :pharmacy_outreach, foreign_key: true

    add_index :emails, :mailjet_message_id, unique: true
  end
end
```

This links every sent email back to a pharmacy and outreach record, and stores the MailJet message ID for webhook correlation.

### Model change

Add to `Email`:
```ruby
belongs_to :pharmacy, optional: true
belongs_to :pharmacy_outreach, optional: true
```

### Avo change

Add `pharmacy` (belongs_to, shown on index and show) to the Email resource.
Add a `has_many :emails` panel to the Pharmacy resource show view (recent outreach emails).

---

## Part 5: API Endpoints

All endpoints under `api/v1/crm` namespace. Add to existing `api/v1` namespace in `config/routes.rb`.

---

### 5.1 `POST /api/v1/crm/campaigns`

Create a new campaign with strategy and goals.

**Request body:**
```json
{
  "name": "pharmacy-outreach-q2-2026",
  "subject": "Spoluprace s Dostupnost-leku.cz",
  "goal_primary": "meeting_booked",
  "goal_secondary": "replied",
  "goal_secondary_auto": true,
  "strategy": {
    "steps": [
      { "name": "initial", "delay_days": 0, "template_key": "initial" },
      { "name": "follow_up_1", "delay_days": 5, "template_key": "follow_up_1" },
      { "name": "follow_up_2", "delay_days": 5, "template_key": "follow_up_2" }
    ],
    "stop_on": ["replied", "goal_primary", "opted_out", "bounced"],
    "max_attempts": 3
  },
  "metadata": {}
}
```

**Behavior:**
1. Create `Campaign` with provided fields. Set `status: 'draft'`, `utm_source: 'crm'`, `utm_medium: 'email'`.
2. Return the campaign record.

**Response (201):**
```json
{
  "id": 78,
  "name": "pharmacy-outreach-q2-2026",
  "status": "draft",
  "goal_primary": "meeting_booked",
  "goal_secondary": "replied",
  "strategy": { "..." },
  "created_at": "2026-04-01T09:00:00Z"
}
```

---

### 5.2 `PATCH /api/v1/crm/campaigns/:id`

Update campaign status or strategy. Used to activate, pause, or complete a campaign.

**Request body (all fields optional):**
```json
{
  "status": "active",
  "strategy": { "..." },
  "goal_primary": "meeting_booked",
  "metadata": {}
}
```

**Behavior:** Updates the campaign. Sets `started_at` when status transitions to `active`. Sets `completed_at` when status transitions to `completed`.

---

### 5.3 `GET /api/v1/crm/outreach`

Andy's main query endpoint. Returns outreach records with pharmacy details inlined.

**Query params:**
- `status` — comma-separated list (e.g. `active`, `active,paused`)
- `batch_name` — exact match
- `andy_can_communicate` — boolean
- `due_for_follow_up` — if `true`, returns records where `next_action_at <= now`, status=active, current_step > 0
- `ready_to_send` — if `true`, returns records at current_step=0, status=active, andy_can_communicate=true
- `limit` — max records (default 50, max 200)
- `campaign_id` — filter by campaign

**Response (200):**
```json
{
  "outreach": [
    {
      "id": 42,
      "pharmacy_id": 123,
      "pharmacy_name": "Lekarna U Nemocnice",
      "pharmacy_email": "lekarna@example.cz",
      "primary_contact": "PharmDr. Jana Nova",
      "primary_contact_phone": "+420777999888",
      "campaign_id": 78,
      "current_step": 0,
      "current_step_name": "initial",
      "status": "active",
      "template_version": "v1",
      "batch_name": "batch-01",
      "andy_can_communicate": true,
      "next_action_at": null,
      "outreach_notes": null,
      "pharmacy_notes": "Jednali jsme v lednu 2025...",
      "pharmacy_deal_status": "to_be_contacted",
      "has_active_contract": false,
      "events_summary": {
        "sent": 0,
        "opened": 0,
        "clicked": 0,
        "replied": 0
      }
    }
  ],
  "meta": {
    "count": 1,
    "limit": 50
  }
}
```

---

### 5.4 `PATCH /api/v1/crm/outreach/:id`

Update outreach record state. Andy calls this after sending an email, detecting a reply, etc.

**Request body (all fields optional):**
```json
{
  "current_step": 1,
  "status": "completed",
  "completed_reason": "goal_achieved",
  "next_action_at": "2026-04-06T09:00:00Z",
  "andy_can_communicate": false,
  "outreach_notes": "Pharmacist replied, interested in a call next week.",
  "template_version": "v1"
}
```

**Response (200):** Returns the updated outreach record (same shape as GET).
**404** if not found.

---

### 5.5 `POST /api/v1/crm/outreach/batch`

Create outreach records for a batch of pharmacies in an existing campaign.

**Request body:**
```json
{
  "campaign_id": 78,
  "batch_name": "batch-01",
  "pharmacy_ids": [123, 456, 789],
  "template_version": "v1"
}
```

**Behavior:**
1. Find `Campaign` by `campaign_id`. Return 404 if not found.
2. For each pharmacy_id:
   - Skip if pharmacy has active contract (`company.active_contract.active?`)
   - Skip if `deliver_marketing_emails` is false
   - Skip if `PharmacyOutreach` already exists for this pharmacy+campaign (idempotent)
   - Skip if pharmacy has another active outreach (unique index on active status)
   - Create `PharmacyOutreach` at status `active`, current_step 0
3. Return created count and skipped count with reasons.

**Response (201):**
```json
{
  "created": 45,
  "skipped": 5,
  "skipped_reasons": {
    "active_contract": 2,
    "marketing_opt_out": 1,
    "already_exists": 1,
    "active_in_other_campaign": 1
  },
  "campaign_id": 78
}
```

---

### 5.6 `POST /api/v1/crm/emails`

Send a personalized email to a pharmacy on behalf of `tomas@dostupnost-leku.cz` via MailJet.

**Request body:**
```json
{
  "pharmacy_outreach_id": 42,
  "subject": "Spoluprace s Dostupnost-leku.cz",
  "body_html": "<p>Dobry den, ...</p>",
  "template_version": "v1",
  "reply_to": "tomas@dostupnost-leku.cz"
}
```

**Behavior:**
1. Find `PharmacyOutreach` by `pharmacy_outreach_id`. Return 404 if not found.
2. Resolve pharmacy and campaign from the outreach record.
3. Generate `correlation_id` as SHA256 of `[pharmacy.email, pharmacy_id, campaign_id, current_step].join('-')`.
4. **Idempotency**: If an `Email` with this `correlation_id` already exists, return it without re-sending (200 with `already_sent: true`).
5. Create `Email` record with: email, email_hash, subject, msg_id=correlation_id, correlation_id, campaign_id, html=body_html, template_version, pharmacy_id, pharmacy_outreach_id.
6. Send via `CrmMailer#outreach`:
   - `from: 'Tomas Landovsky <tomas@dostupnost-leku.cz>'`
   - `reply_to:` from request (defaults to `tomas@dostupnost-leku.cz`)
   - Uses `plain_mailer` layout (includes footer with unsubscribe link)
   - Body is raw HTML from `body_html` param (rendered inside layout)
   - Pass `CustomID: "outreach-#{pharmacy_outreach_id}"` as MailJet custom header for webhook correlation
   - Delivers via `deliver_later` (Sidekiq)
7. After delivery, store the MailJet message ID on the Email record (`mailjet_message_id`).

**Response (201):**
```json
{
  "id": 456,
  "correlation_id": "sha256-hash",
  "pharmacy_outreach_id": 42,
  "pharmacy_id": 123,
  "campaign_id": 78,
  "already_sent": false
}
```

**Important**: The `body_html` is the complete email body content. The layout wraps it with the standard footer (including unsubscribe link). Do NOT apply any template on top — the caller controls the full body.

---

### 5.7 `POST /api/v1/crm/outreach/:id/events`

Manually record an outreach event. Used by Andy for events not covered by MailJet webhooks (replies, goals).

**Request body:**
```json
{
  "event_type": "goal_primary",
  "occurred_at": "2026-04-05T14:00:00Z",
  "metadata": { "note": "Meeting booked for April 10" }
}
```

**Behavior:**
1. Find `PharmacyOutreach` by id. Return 404 if not found.
2. Create `OutreachEvent` with provided fields.
3. After-create callbacks handle stop conditions and goal_secondary auto-detection.

**Response (201):** Returns the created event.

---

### 5.8 `GET /api/v1/crm/campaigns/:id/stats`

Aggregate performance for a campaign. Accepts campaign `id`.

**Response (200):**
```json
{
  "campaign_id": 78,
  "campaign_name": "pharmacy-outreach-q2-2026",
  "status": "active",
  "goal_primary": "meeting_booked",
  "goal_secondary": "replied",
  "total_contacts": 30,
  "funnel": {
    "sent": 28,
    "delivered": 27,
    "opened": 15,
    "clicked": 8,
    "replied": 5,
    "bounced": 1,
    "spam": 0,
    "blocked": 0,
    "unsubscribed": 1
  },
  "goals": {
    "primary": { "label": "meeting_booked", "achieved": 3, "rate": 0.107 },
    "secondary": { "label": "replied", "achieved": 5, "rate": 0.179 }
  },
  "by_template_version": {
    "v1": {
      "contacts": 15,
      "sent": 14,
      "opened": 10,
      "clicked": 5,
      "replied": 3,
      "goal_primary": 2
    },
    "v2": {
      "contacts": 15,
      "sent": 14,
      "opened": 5,
      "clicked": 3,
      "replied": 2,
      "goal_primary": 1
    }
  },
  "by_step": {
    "initial": { "sent": 28, "opened": 15, "clicked": 8 },
    "follow_up_1": { "sent": 12, "opened": 6, "clicked": 2 },
    "follow_up_2": { "sent": 5, "opened": 2, "clicked": 0 }
  },
  "by_status": {
    "active": 10,
    "completed": 14,
    "opted_out": 3,
    "paused": 3
  }
}
```

**Implementation note**: All funnel metrics come from `OutreachEvent` counts grouped by event_type, scoped to the campaign's outreach records. `delivered` = `sent` - `bounced` - `blocked`. `by_template_version` groups by `pharmacy_outreach.template_version`. `by_step` requires joining events to the email's step (stored in event metadata or derived from outreach current_step at time of send). Goal rates are `achieved / total_contacts`.

---

### 5.9 `POST /webhooks/mailjet`

MailJet webhook receiver. **Not under the `/api/v1/crm` namespace** — this is a public endpoint called by MailJet.

**MailJet sends events as JSON array:**
```json
[
  {
    "event": "open",
    "time": 1712000000,
    "MessageID": 123456789,
    "CustomID": "outreach-42",
    "email": "lekarna@example.cz"
  }
]
```

**Behavior:**
1. Parse the event array.
2. For each event:
   - Extract `pharmacy_outreach_id` from `CustomID` (format: `outreach-{id}`)
   - Map MailJet event type to OutreachEvent event_type:
     - `sent` → `sent`
     - `open` → `opened`
     - `click` → `clicked`
     - `bounce` → `bounced`
     - `spam` → `spam`
     - `blocked` → `blocked`
     - `unsub` → `unsubscribed`
   - Create `OutreachEvent` with the mapped type, `occurred_at` from event timestamp, and full MailJet payload in metadata
   - **Idempotent**: Skip if an event with the same MailJet MessageID + event_type already exists (use metadata lookup or a unique constraint)
3. Return 200 OK (MailJet expects this).

**Security**: MailJet doesn't sign webhooks. Options:
- Secret token in URL path: `/webhooks/mailjet/{secret_token}` — simple, effective
- IP allowlisting for MailJet's IP ranges

**Error handling**: Never return non-200 to MailJet or it will retry aggressively. Log errors internally, always return 200.

---

## Part 6: CrmMailer

```ruby
class CrmMailer < ApplicationMailer
  layout 'plain_mailer'
  default from: 'Tomas Landovsky <tomas@dostupnost-leku.cz>'

  def outreach(email_address:, subject:, body_html:, msg_id:, outreach_id:, reply_to: nil)
    self.msg_id = msg_id
    @body_html = body_html

    headers['X-MJ-CustomID'] = "outreach-#{outreach_id}"

    mail(
      to: email_address,
      subject: subject,
      reply_to: reply_to || 'tomas@dostupnost-leku.cz'
    )
  end
end
```

View template `app/views/crm_mailer/outreach.html.erb`:
```erb
<%= raw @body_html %>
```

The `plain_mailer` layout handles footer (including unsubscribe link). No tracking pixel needed — MailJet handles open tracking.

**Note on MailJet setup**: If the Rails app currently sends via wegblobe.cz SMTP directly, the SMTP settings need to be updated to route through MailJet's SMTP relay (`in-v3.mailjet.com:587`) or use the `mailjet` gem for API-based sending. MailJet SMTP relay automatically adds open/click tracking and processes the `X-MJ-CustomID` header.

---

## Part 7: Routes

```ruby
namespace 'api' do
  namespace 'v1' do
    # ... existing routes ...

    namespace 'crm' do
      resources :campaigns, only: [:create, :update] do
        member do
          get :stats
        end
      end
      resources :outreach, only: [:index, :update], controller: 'outreach' do
        collection do
          post :batch
        end
        member do
          post :events
        end
      end
      resources :emails, only: [:create]
    end
  end
end

# MailJet webhook (outside API namespace)
post '/webhooks/mailjet/:token', to: 'webhooks/mailjet#create'
```

---

## Part 8: Auth

```ruby
module Api
  module V1
    module Crm
      class BaseController < ActionController::API
        before_action :authenticate_api_token!

        private

        def authenticate_api_token!
          token = request.headers['Authorization']&.delete_prefix('Bearer ')
          head :unauthorized unless token.present? && ActiveSupport::SecurityUtils.secure_compare(
            token, ENV.fetch('CRM_API_TOKEN')
          )
        end
      end
    end
  end
end
```

All CRM controllers inherit from this.

The MailJet webhook controller uses URL-token auth instead:

```ruby
module Webhooks
  class MailjetController < ActionController::API
    before_action :verify_token!

    def create
      # Process events...
      head :ok
    end

    private

    def verify_token!
      head :unauthorized unless ActiveSupport::SecurityUtils.secure_compare(
        params[:token], ENV.fetch('MAILJET_WEBHOOK_TOKEN')
      )
    end
  end
end
```

---

## File Summary

| File | Purpose |
|------|---------|
| `db/migrate/xxx_add_strategy_fields_to_campaigns.rb` | Campaign strategy, goals, status |
| `db/migrate/xxx_create_pharmacy_outreaches.rb` | PharmacyOutreach table |
| `db/migrate/xxx_create_outreach_events.rb` | OutreachEvent table |
| `db/migrate/xxx_add_outreach_fields_to_emails.rb` | template_version, pharmacy_id, mailjet_message_id, pharmacy_outreach_id on emails |
| `app/models/pharmacy_outreach.rb` | Model with enum, scopes, validations |
| `app/models/outreach_event.rb` | Event log model with after_create callbacks |
| `app/avo/resources/pharmacy_outreach.rb` | Avo admin resource |
| `app/avo/resources/outreach_event.rb` | Avo admin resource |
| `app/controllers/api/v1/crm/base_controller.rb` | Bearer token auth |
| `app/controllers/api/v1/crm/campaigns_controller.rb` | create, update, stats |
| `app/controllers/api/v1/crm/outreach_controller.rb` | index, update, batch, events |
| `app/controllers/api/v1/crm/emails_controller.rb` | create |
| `app/controllers/webhooks/mailjet_controller.rb` | MailJet webhook receiver |
| `app/mailers/crm_mailer.rb` | outreach method with X-MJ-CustomID header |
| `app/views/crm_mailer/outreach.html.erb` | raw body_html template |

---

## Testing Checklist

### Campaigns
- [ ] POST campaign with strategy and goals -> 201, campaign created with status=draft
- [ ] PATCH campaign status to active -> sets started_at
- [ ] PATCH campaign status to completed -> sets completed_at
- [ ] GET campaign stats -> correct funnel from OutreachEvent counts

### Outreach
- [ ] POST batch with valid campaign_id and pharmacy_ids -> 201, outreach records created
- [ ] POST batch skips pharmacies with active contracts
- [ ] POST batch skips pharmacies with deliver_marketing_emails=false
- [ ] POST batch skips pharmacies with active outreach in another campaign
- [ ] POST batch is idempotent (re-run doesn't duplicate)
- [ ] GET outreach with status filter -> correct results
- [ ] GET outreach with ready_to_send=true -> only current_step=0 + status=active + andy_can_communicate
- [ ] GET outreach with due_for_follow_up=true -> only due records
- [ ] PATCH outreach/:id -> updates fields, returns updated record
- [ ] POST outreach/:id/events with goal_primary -> creates event, triggers stop condition

### Emails
- [ ] POST email with valid pharmacy_outreach_id -> 201, email record created, Sidekiq job enqueued
- [ ] POST email with same outreach+step -> 200, `already_sent: true`, no duplicate
- [ ] POST email with invalid pharmacy_outreach_id -> 404
- [ ] Email includes X-MJ-CustomID header with outreach ID
- [ ] Email arrives with correct from, reply-to, subject, body
- [ ] Unsubscribe link present in email footer (via layout)
- [ ] Email record has pharmacy_id, pharmacy_outreach_id, template_version set

### MailJet Webhook
- [ ] POST /webhooks/mailjet/:token with valid token -> 200
- [ ] POST /webhooks/mailjet/:token with invalid token -> 401
- [ ] Open event creates OutreachEvent with event_type=opened
- [ ] Click event creates OutreachEvent with event_type=clicked
- [ ] Bounce event creates OutreachEvent with event_type=bounced AND triggers stop condition
- [ ] Duplicate events are idempotent (no duplicate OutreachEvent)
- [ ] Malformed payload returns 200 (never fail MailJet)

### Campaign Stats
- [ ] GET campaign stats -> correct funnel from OutreachEvent
- [ ] GET campaign stats -> correct by_template_version breakdown
- [ ] GET campaign stats -> correct by_step breakdown
- [ ] GET campaign stats -> correct goal counts and rates
- [ ] GET campaign stats with unknown campaign -> 404

### Event Callbacks
- [ ] OutreachEvent with "bounced" -> outreach status=completed, reason=bounced (if in stop_on)
- [ ] OutreachEvent with "replied" -> outreach status=completed (if in stop_on)
- [ ] OutreachEvent with "replied" + goal_secondary_auto -> auto-creates goal_secondary event
- [ ] OutreachEvent on already-completed outreach -> no status change

### Auth
- [ ] All CRM endpoints without Bearer token -> 401
- [ ] All CRM endpoints with wrong token -> 401

### Avo Admin
- [ ] PharmacyOutreach shows on sidebar, filterable by status/batch/campaign
- [ ] OutreachEvent shows on PharmacyOutreach detail page
- [ ] Pharmacy show page includes outreach emails panel
- [ ] Email index shows pharmacy link
- [ ] Campaign shows goal_primary, goal_secondary, status

## Non-Goals

- No email scheduling in Rails (Andy controls timing externally)
- No template storage in Rails (templates managed in NanoClaw agent config)
- No reply detection in Rails (Andy handles via IMAP separately)
- No batch sending endpoint (Andy sends one at a time for controlled pacing)
- No tracking pixel (MailJet handles open tracking)
- No link redirect service (MailJet handles click tracking)
