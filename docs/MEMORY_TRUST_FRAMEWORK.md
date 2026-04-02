# Memory Trust Framework

Definitive version. Synthesized from three candidate designs (v1 structural metrics, research-integrated revision, research-first redesign). Every metric and threshold is justified by published work. The structure follows what the KG quality literature says matters, not what v1 happened to measure.

**Scope:** ~1600 entities, ~2800 facts, single developer, Czech content with English embeddings, Gemini Flash Lite extraction, Neo4j knowledge graph used as CRM for a Czech venue business.

---

## Three Findings That Drove the Redesign

**1. The embedding model is the single biggest quality lever.**
An English-only model (bge-small-en-v1.5) on a Czech-dominant CRM is a known 10-30% retrieval quality penalty [DaReCzech Nov 2024, 1.6M Czech query-document pairs from Seznam.cz]. No amount of data cleaning compensates for a retrieval layer that cannot find correct results. This must be addressed before fine-tuning other metrics.

**2. LLM extraction error rates are high and unavoidable.**
Zero-shot NER F1 of 35-50% and RE precision of 25-40% for Flash Lite-class models means roughly 20-35% of extracted triples contain errors [extrapolated from published benchmarks on similar-sized models]. The framework must assume noisy input and measure its consequences, not pretend extraction is reliable.

**3. Completeness means property coverage, not entity count.**
Zaveri et al.'s 18-dimension quality framework and Mattioli (AAAI 2025) both define completeness as "entities with all expected properties filled / total entities." The v1 entity-to-episode ratio measured extraction aggressiveness, not data quality. It is removed.

---

## Architecture: Two Tiers

The literature (Zaveri et al., Marchesin VLDB 2024, Mattioli AAAI 2025) consistently identifies four KG quality pillars: accuracy, completeness, consistency, freshness. For a ~2800-fact CRM that IS the primary database, these collapse into two practical tiers:

**Tier 1 — Can I trust what comes back?** (Accuracy + Consistency + Freshness)
The graph contains correct, non-contradictory, deduplicated, current facts.

**Tier 2 — Does the right thing come back?** (Completeness + Retrieval)
Queries find what exists, and entities have the properties needed to answer real questions.

Freshness is in Tier 1 because stale facts are inaccurate facts in a CRM. Operational discipline from v1 is in Tier 2 because if agents don't query memory, retrieval effectively fails regardless of graph quality.

---

## Metrics (10 total)

### Tier 1: Data Trustworthiness (5 metrics)

#### T1.1 — Sampled Fact Accuracy
**What:** Draw 50 random facts from `swan_crm`. Judge each as correct / incorrect / stale.
**Target:** >= 85% accurate.
**Frequency:** Monthly.
**Justification:** Marchesin (VLDB 2024) shows 100-200 sample triples from ~2800 facts give ~95% confidence, CI width +/-5%. At 50 samples the CI widens to roughly +/-10%, which is sufficient for a monthly canary. This directly measures the consequence of Flash Lite extraction errors rather than proxying through structural metrics.
**Action if failing:** Categorize errors. If >50% are extraction hallucinations, add post-extraction validation. If >50% are stale, tighten staleness policy (T1.4).

```cypher
MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
WHERE r.group_id = 'swan_crm' AND r.expired_at IS NULL
WITH r, a, b, rand() AS rnd
ORDER BY rnd LIMIT 50
RETURN a.name AS source, r.name AS relation, b.name AS target,
       r.fact AS fact_text, r.valid_at AS valid_at,
       r.created_at AS created_at, r.uuid AS uuid
```

#### T1.2 — Duplicate Entity Clusters
**What:** Case-insensitive + diacritics-normalized name collision within `swan_crm`.
**Target:** 0 new clusters per week.
**Frequency:** Weekly automated.
**Justification:** Graphiti's dedup (entropy filter, 3-gram shingles, MinHash, Jaccard 0.9) is conservative by design. But Czech inflection (Cerna/Cernou/Cerne Labut) and diacritics (Cerna vs Cerna) bypass character-level matching. This is a known gap — production already had 4+ variants of "Cerna Labut."
**Action if failing:** LLM-assisted candidate ranking with human approval. Do NOT automate merges. GPT-4 zero-shot entity matching outperforms fine-tuned PLMs by 40-68% on unseen types, but "outperforms" does not mean "reliable enough for unsupervised CRM operations."

```cypher
MATCH (n:Entity)
WHERE n.group_id = 'swan_crm'
WITH toLower(n.name) AS lname, collect(n) AS nodes
WHERE size(nodes) > 1
RETURN lname, size(nodes) AS count,
       [n IN nodes | {name: n.name, uuid: n.uuid}] AS variants
```

Note: This query catches case variants but NOT diacritics or inflection. Proper Czech dedup requires normalization — either `apoc.text.clean()` in Cypher, Python `unidecode` + Czech stemmer, or a quarterly LLM-assisted review of all entity names.

#### T1.3 — Contradiction Rate (Sampled)
**What:** From the T1.1 sample, count facts that contradict other active facts about the same entity pair.
**Target:** < 5% of sampled facts.
**Frequency:** Monthly (piggybacks on T1.1 — zero incremental effort).
**Justification:** v1 dismissed contradiction detection as "hard to detect reliably." The research agrees for automated detection. But sample-based human detection is trivial and high-signal. Two active facts with conflicting relationship status for the same entity is a data corruption event in a CRM. Graphiti's bi-temporal model (t_valid/t_invalid) provides resolution infrastructure — the gap is detection, which sampling solves.
**Action if failing:** Expire the older fact. If contradictions are systematic, the extraction prompt is generating conflicting facts — tighten it.

#### T1.4 — Staleness Ratio
**What:** Percentage of active facts older than their staleness window with no update.
**Target:** < 15% stale.
**Frequency:** Monthly.
**Justification:** Research recommends per-fact-type staleness windows. For CRM:
- Contact info (email, phone): 6-month half-life
- Capacity/pricing: 12 months
- Relationship status: 3 months
- Task/action status: 1 month

Age decay from the literature: `freshness = exp(-ln(2) * days / half_life)`. A fact below 0.25 freshness (two half-lives past) is "stale."

```cypher
// Conservative: flat 180-day window until fact_type tagging exists
MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
WHERE r.group_id = 'swan_crm'
  AND r.expired_at IS NULL
  AND r.valid_at IS NOT NULL
WITH count(r) AS total,
     sum(CASE WHEN r.valid_at < datetime() - duration('P180D') THEN 1 ELSE 0 END) AS stale
RETURN stale, total, round(stale * 100.0 / total, 1) AS stale_pct
```

**Action if failing:** Flag stale facts in the weekly report. For relationship-status facts older than 6 months with no interaction, mark as "needs reconfirmation" rather than auto-expiring.

#### T1.5 — Null Temporal Data
**What:** Facts in `swan_crm` with `valid_at: null`.
**Target:** < 5%.
**Frequency:** Weekly automated.
**Justification:** Without temporal metadata, T1.4 is blind and temporal queries return unreliable results. Retained from v1 because the staleness model depends on it.
**Action if failing:** Backfill from episode timestamps. Enforce `valid_at` in extraction prompt for new facts.

```cypher
MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
WHERE r.group_id = 'swan_crm'
WITH count(r) AS total,
     sum(CASE WHEN r.valid_at IS NULL THEN 1 ELSE 0 END) AS null_count
RETURN null_count, total, round(null_count * 100.0 / total, 1) AS null_pct
```

### Tier 2: Retrieval Effectiveness (5 metrics)

#### T2.1 — Czech Query Recall (Golden Dataset Benchmark)
**What:** 30 queries with known expected entity UUIDs, tested against the live graph. Score: expected UUID appears in `search_nodes` top-5 results (binary, no subjective judgment).
**Target:** >= 80% recall@5.
**Frequency:** Monthly, and after any embedding model change.
**Golden dataset:** [`docs/trust-benchmark-t2.1-golden.md`](trust-benchmark-t2.1-golden.md)

**Justification:** This is the most important metric in the framework. Early versions used agent-judged scoring (agent runs queries, agent decides if results are "relevant"). Three independent runs produced scores of 62.5%, 77.5%, and 92.5% — a 30pp spread that made the metric useless for tracking trends. The golden dataset eliminates this by anchoring each query to a specific UUID, making scoring deterministic and repeatable.

**Benchmark design:**
The 30 queries are stratified into four difficulty tiers, each testing a different retrieval capability:
- **exact** (8 queries): query mirrors entity name — baseline sanity check
- **synonym** (8 queries): Czech synonym, inflection, or paraphrase — tests embedding quality on Czech morphology
- **alias** (7 queries): abbreviation or common name vs formal stored name — tests whether the graph has sufficient aliases
- **conceptual** (7 queries): describes the entity without naming it — tests architectural limits of name-only embedding search

**Baseline results (2026-04-02, A/B test):**

| Difficulty | bge-small-en-v1.5 (384d) | BGE-M3 (1024d) |
|-----------|:-:|:-:|
| exact (8) | 100% | 100% |
| synonym (8) | 87.5% | 87.5% |
| alias (7) | 85.7% | 85.7% |
| conceptual (7) | 14.3% | 28.6% |
| **Total (30)** | **73.3%** | **76.7%** |

The models differ on exactly 1 query out of 30. The embedding model is not the bottleneck. The 7 shared failures are: graph gaps (missing aliases), and architecture limitations (name-only search cannot match conceptual descriptions to brand-name entities like "Zero Latency" or "DanceDifferent").

**Action if failing:** Diagnose by tier. Exact/synonym failures → embedding model problem. Alias failures → graph gap, add aliases during extraction. Conceptual failures → architecture limitation, requires hybrid name+summary search.

#### T2.2 — CRM Entity Richness
**What:** Percentage of CRM entities with >= 3 distinct active relationship types (e.g., "contact_person", "email", "status", "located_in" each count as one type).
**Target:** >= 70%.
**Frequency:** Monthly.
**Justification:** Replaces v1 entity-to-episode ratio. Zaveri et al. and Mattioli (AAAI 2025) define completeness as property coverage. In a structured KG this means filled columns; in a free-text graph like Graphiti, the closest operationalizable proxy is distinct relationship types per entity. An entity connected by 3+ relationship types can answer "who is the contact?", "what's the status?", and "when did we last interact?" -- the minimum for CRM utility. An entity with only a name and one relationship cannot.

**Why not named properties?** Graphiti stores facts as free-text relationship edges, not structured fields. Counting "contact_name, email, phone" as discrete properties would require NLP classification of every edge. Counting distinct `r.name` values is cheap, deterministic, and correlates with the same underlying quality dimension.

```cypher
MATCH (n:Entity)
WHERE n.group_id = 'swan_crm'
OPTIONAL MATCH (n)-[r:RELATES_TO]-()
WHERE r.group_id = 'swan_crm' AND r.expired_at IS NULL
WITH n, count(DISTINCT r.name) AS relation_types
WITH count(*) AS total,
     sum(CASE WHEN relation_types >= 3 THEN 1 ELSE 0 END) AS rich
RETURN rich, total, round(rich * 100.0 / total, 1) AS richness_pct
```

To see which entities need enrichment:

```cypher
MATCH (n:Entity)
WHERE n.group_id = 'swan_crm'
OPTIONAL MATCH (n)-[r:RELATES_TO]-()
WHERE r.group_id = 'swan_crm' AND r.expired_at IS NULL
WITH n, count(DISTINCT r.name) AS relation_types
WHERE relation_types < 3
RETURN n.name, relation_types
ORDER BY relation_types ASC
```

**Action if failing:** Identify entities with 0-1 relationships. These are likely extraction artifacts (ghost entities) or genuinely thin records. Ghost entities should be deleted; thin records should be enriched through targeted data entry or improved extraction context.

#### T2.3 — CRM End-to-End Test
**What:** 10 real CRM scenarios as natural language questions. Score: correct AND complete answer.
**Target:** 10/10.
**Frequency:** Monthly.
**Justification:** This is RAGAS-lite. The full RAGAS framework (faithfulness >= 0.8, answer relevancy, context precision, context recall) is overhead for 10 test cases. But the principle is sound: measure the end-to-end pipeline, not just the graph.

Example scenarios:
1. "Jaky je aktualni status s [client X]?"
2. "Kdo je kontaktni osoba pro [company Y]?"
3. "Kdy jsme naposledy komunikovali s [client Z]?"
4. "Ktere firmy jsou ve fazi jednani?"
5. "Co vime o [new lead]?"

**Action if failing:** Diagnose root cause — retrieval miss (route to T2.1), wrong fact (route to T1.1), or missing property (route to T2.2).

#### T2.4 — Agent Memory Engagement
**What:** Percentage of CRM-related agent tasks with at least one `search_nodes` or `search_memory_facts` call.
**Target:** 100%.
**Frequency:** Continuous (proxy logs).
**Justification:** Circuit-breaker metric. If the agent doesn't query memory, retrieval completeness is zero regardless of graph quality.
**Action if failing:** Strengthen CLAUDE.md memory instructions. If persistent, add proxy-level warning on CRM task completion with zero memory reads.

#### T2.5 — Retrieval Precision (False Positive Risk)
**What:** 10 queries for things that definitely do NOT exist in the graph. Score: percentage of queries where the top results are clearly irrelevant (safe) vs confusingly plausible (misleading).
**Target:** <= 30% misleading (i.e., >= 70% safe).
**Frequency:** Quarterly.
**Golden dataset:** Negative query set in [`docs/trust-benchmark-t2.1-golden.md`](trust-benchmark-t2.1-golden.md)

**Justification:** T2.1 measures recall ("does the right thing come back?") but ignores precision ("does the wrong thing stay away?"). Graphiti's `search_nodes` always returns N results regardless of relevance — there is no "nothing found" signal and no confidence score. An agent querying for "veterinární klinika" gets back "IVF klinika, Klinika LaserPlastic, Urologická klinika" with no indication these are irrelevant. This is a trust problem: the agent cannot distinguish a strong match from the least-bad cosine similarity.

**Baseline (2026-04-02):** 7/10 irrelevant queries returned misleadingly plausible results — the system surfaced catering entities for "restaurace sushi", clinic entities for "veterinární klinika", rental entities for "pronájem bytu." Only 3/10 were clearly safe.

**Scoring criteria:**
- **safe**: no returned entity is plausibly related to the query domain — an agent would likely ignore the results
- **misleading**: at least one returned entity could fool an agent into believing relevant data exists (e.g., "jídlo" for a sushi query, "Klinika LaserPlastic" for a vet query)

**Action if failing:** The root cause is architectural — no relevance threshold exists. Mitigation options ranked by effort:
1. **Agent-side prompt guardrails** (low effort): instruct agents to critically evaluate whether results match the query, not blindly trust top-N
2. **Domain-scoped search** (medium effort): add `entity_types` filtering to narrow results (e.g., search only Company entities for company queries)
3. **Relevance gate wrapper** (medium effort): compute pairwise cosine similarity between query embedding and each result's name embedding; filter results below a threshold before returning to the agent
4. **Upstream confidence scores** (high effort): modify Graphiti to expose cosine similarity in search results, enabling the agent to self-threshold

---

## Trust Score

Single composite number for trend tracking. A canary, not a KPI.

```
Trust Score = (Trustworthiness * 0.6) + (Retrieval * 0.4)
```

Weighting: wrong answers erode confidence faster than slow answers. A CRM with accurate but hard-to-find data is annoying; a CRM with easily-found but inaccurate data is dangerous.

### Trustworthiness (0-100)

```
T1 = (T1.1_accuracy_pct * 0.40)
   + (max(0, 100 - T1.2_dup_clusters * 15) * 0.15)
   + (max(0, 100 - T1.3_contradiction_pct * 5) * 0.15)
   + (max(0, 100 - T1.4_stale_pct) * 0.15)
   + (max(0, 100 - T1.5_null_pct * 2) * 0.15)
```

T1.1 gets 0.40 weight because it's the only direct measurement -- everything else is a proxy.

Penalty multipliers: T1.2 uses `* 15` (each duplicate cluster costs 15 points -- duplicates are high-severity in a CRM), T1.3 uses `* 5` (contradictions are serious but rarer), T1.5 uses `* 2` (null timestamps are a data gap, not an error). T1.4 staleness percentage maps 1:1 since it's already a percentage.

### Retrieval (0-100)

```
T2 = (T2.1_recall_pct * 0.35)
   + (T2.2_richness_pct * 0.15)
   + (T2.3_e2e_score * 10 * 0.20)
   + (T2.4_engagement_pct * 0.15)
   + (T2.5_safe_pct * 0.15)
```

T2.1 + T2.3 together get 0.55 weight because they measure what the user experiences. T2.5 gets 0.15 because false positives erode trust even when recall is high — an agent that confidently returns wrong information is worse than one that returns nothing.

### Thresholds

| Score | Status | Action |
|-------|--------|--------|
| >= 80 | Healthy | Steady-state monitoring |
| 65-79 | Degraded | Fix lowest-scoring metrics within 2 weeks |
| < 65 | Broken | Stop feature work. Fix data quality first |

Floor at 0, cap at 100 per axis.

---

## The Embedding Problem

The research is unambiguous. This section is a decision framework, not a recommendation to defer.

**Current state:** bge-small-en-v1.5 (33M params, 384-dim, English-only) encoding Czech text.

**Why it dominates everything else:** Every metric downstream of retrieval — T2.1, T2.3, and indirectly T1.1 through what gets surfaced for extraction context — is bounded by embedding quality. You cannot out-metric a broken retrieval layer.

**Decision protocol:**

1. Run T2.1 with current embeddings. Record baseline recall@5.
2. If recall@5 >= 80%: the English model is surprisingly adequate. Monitor quarterly. Skip step 3.
3. If recall@5 < 80% (likely): migrate.

**Baseline result (2026-04-02, subjective):** Three independent agent-judged benchmarks scored 75%, 92.5%, 70% (avg 79%). The 30pp spread revealed the methodology was unreliable — agent scoring is not deterministic. These results are superseded by the golden dataset benchmark below.

**A/B result (2026-04-02, golden dataset):** Head-to-head on 30 UUID-anchored queries:
- bge-small-en-v1.5: 22/30 = 73.3%
- BGE-M3: 23/30 = 76.7%
- Difference: exactly 1 query out of 30 (+3.3pp)

The models are effectively equivalent. The 7 shared failures are graph gaps and architecture limitations, not embedding quality. Full results at [`docs/trust-benchmark-t2.1-golden.md`](trust-benchmark-t2.1-golden.md).

**Decision:** BGE-M3 deployed (2026-04-02). Marginal improvement, no downside, architecturally correct for Czech+English content. Further embedding model changes are not justified — the bottleneck is elsewhere.

**Where the bottleneck actually is:**
1. **Graph coverage** — missing entity aliases (e.g., "Akademie věd" not linked to "Středisko společných činností AV ČR")
2. **Name-only search** — `search_nodes` embeds entity names, not summaries. Conceptual queries ("virtuální realita zábava") cannot match brand-name entities ("Zero Latency") because the name embedding has no semantic overlap. Fix: hybrid search combining name embedding + fulltext summary search.
3. **No relevance threshold** — see T2.5. The system always returns N results, even for completely off-topic queries.

**Migration reference (for future model changes):**

| Model | Params | Dims | Evidence |
|-------|--------|------|----------|
| BGE-M3 (deployed) | 567M | 1024 | SOTA on MIRACL/MKQA multilingual |
| Seznam Czech | 15-20M | 256 | AAAI 2024: Czech-specific, competitive |
| Qwen-3-Embedding-0.6B | 600M | varies | Beats BGE-M3 by 7.9% on MMTEB |

Re-embedding script: `nano-claw-memory-store/scripts/reembed.py` (~4 min for full graph on CPU with BGE-M3).

---

## What Was Removed From v1 (and Why)

| v1 Metric | Disposition | Rationale |
|-----------|------------|-----------|
| C2: Bare email entities | Subsumed by T1.1 + post-extraction validation | A bare email is an accuracy error. Dedicated metrics for specific error subtypes don't scale. The post-extraction validation rule (Phase 2) also prevents new bare-email entities from entering the graph. |
| C3: Ghost entity ratio | Subsumed by T1.1 + T2.2 | Ghosts are accuracy errors (false extractions) or completeness failures (no properties). T1.1 catches the first, T2.2 the second. |
| C5: Entity-to-episode ratio | Replaced by T2.2 | No research basis. Measured extraction volume, not quality. A high ratio could mean over-extraction OR an entity-rich domain. |
| D1: group_id cross-contamination | Engineering control | Prevention beats measurement. A proxy `if` statement that rejects mismatched group_ids is more effective than counting violations after the fact. |

---

## What We Are Not Tracking (and Why)

- **Per-triple trust scores** — `source_weight * accuracy + freshness_decay + structural_confidence` is the literature standard. Elegant but over-engineered for a 2800-fact graph with one data source. Revisit at 10K+ facts or multiple input channels. See "Future Enhancement" below.
- **Full RAGAS suite** — Faithfulness, Context Precision, Context Recall require an instrumented RAG pipeline. T2.3 captures the same signal at 1/10th the infrastructure cost.
- **ANoT anomaly detection** — PR-AUC 0.83 for stale fact detection. Interesting, but T1.4 staleness windows + monthly T1.1 sampling cover the same ground with zero ML infrastructure.
- **Extraction NER F1** — Requires gold-standard annotated corpus. Build one only if T1.1 drops below 75% and extraction is identified as the cause.
- **Session-start recall rate** — Incentivizes wasteful rote queries.
- **Token cost tracking** — Not actionable. Memory ops are a rounding error.

---

## Measurement Infrastructure

### 1. Weekly Automated Scan

Covers T1.2, T1.5. Runs as a NanoClaw scheduled task, posts to Slack/Telegram.

```
Weekly Memory Health — 2026-W14
Duplicate clusters: 0 (target: 0)       [PASS]
Null valid_at: 3.1% (target: <5%)       [PASS]
Trust Score: 84 (weekly partial, T1 only)
```

### 2. Monthly Manual Review (~45 min)

Covers T1.1, T1.3, T1.4, T2.1, T2.2, T2.3.

1. Run T1.1 Cypher — draw 50 random facts (5 min)
2. Judge each: correct / incorrect / stale / contradictory (20 min) — also yields T1.3
3. Run T2.1: 20 Czech queries, check top-5 results (10 min)
4. Run T2.3: 10 CRM scenarios, check answers (10 min)
5. Run T1.4 + T2.2 Cypher queries (2 min)
6. Compute Trust Score, append to `data/trust-scores.jsonl`

### 3. Continuous Proxy Logging

Covers T2.4. Add to `container/agent-runner/src/memory-store-proxy.ts`:

```typescript
// In CallToolRequestSchema handler, before return:
const logEntry = {
  ts: new Date().toISOString(),
  tool: request.params.name,
  group_id: (request.params.arguments as Record<string, unknown>)?.group_id ?? null,
  session: process.env.SESSION_ID ?? null,
  group_folder: process.env.GROUP_FOLDER ?? null,
};
process.stderr.write(JSON.stringify(logEntry) + '\n');
```

Also add group_id validation — reject mismatched group_ids. This replaces v1 D1 with an engineering control.

### 4. Trust Score History

`data/trust-scores.jsonl`, one JSON object per measurement:

```jsonl
{"date":"2026-04-01","type":"weekly","t1_2":0,"t1_5":3.1}
{"date":"2026-04-01","type":"monthly","t1_1":88,"t1_2":0,"t1_3":2,"t1_4":12,"t1_5":3.1,"t2_1":72,"t2_2":65,"t2_3":90,"t2_4":100,"score_t1":85,"score_t2":76,"trust_score":81}
```

---

## Per-Fact Trust (Future Enhancement)

The literature consistently models trust at the triple level:

```
trust(fact) = w1 * accuracy_confidence
            + w2 * freshness_score
            + w3 * source_reliability
            + w4 * corroboration_bonus
```

Where:
- `accuracy_confidence`: 1.0 human-verified, 0.7 LLM-extracted from conversation, 0.4 LLM-inferred
- `freshness_score`: `exp(-ln(2) * days / half_life)` per fact type
- `source_reliability`: direct user input = 1.0, LLM extraction = 0.7, LLM inference = 0.4
- `corroboration_bonus`: +0.1 per independent source confirming the same fact

This requires schema changes to Graphiti edges (`source_type`, `confidence` fields). Not in the current plan. But the graph-level metrics are designed to be replaceable by per-fact scores when the infrastructure supports it.

---

## Implementation Plan

### Phase 1: Baseline (Week 1-2)

Know where you stand before changing anything.

| Task | Effort | Enables |
|------|--------|---------|
| Add proxy logging + group_id validation | 30 min | T2.4 + cross-contamination prevention |
| Run T2.1 Czech recall benchmark (20 queries) | 2 hrs | Embedding migration decision |
| Run T1.1 sampled accuracy (50 facts) | 30 min | Baseline accuracy |
| Run T1.2, T1.5 Cypher scans | 15 min | Baseline hygiene |
| Merge known duplicates, delete ghosts | 1-2 hrs | Immediate accuracy improvement |
| Compute first Trust Score | 15 min | Baseline for comparison |

**Decision gate:** T2.1 result determines Phase 2 priority.

### Phase 2: Act on Baseline (Week 3-4)

**If T2.1 < 80% (likely):**

| Task | Effort | Impact |
|------|--------|--------|
| Deploy BGE-M3, re-embed all entities/facts | 4-6 hrs | 10-30% retrieval improvement |
| Re-run T2.1 to validate | 1 hr | Confirms migration value |
| Add post-extraction validation rules | 1 hr | Catches worst extraction errors before they enter the graph |
| Create weekly scan scheduled task | 2 hrs | Automates T1.2, T1.5 |
| Sharpen CLAUDE.md memory instructions | 15 min | Improves T2.4 |

**If T2.1 >= 80%:**

| Task | Effort | Impact |
|------|--------|--------|
| Tighten extraction prompt | 2-4 hrs | Reduces extraction errors |
| Add post-extraction validation rules | 1 hr | Catches worst extraction errors before they enter the graph |
| Create weekly scan scheduled task | 2 hrs | Automates T1.2, T1.5 |
| Add Czech diacritics normalization to dedup | 1 hr | Catches inflection dupes |

**Post-extraction validation rules** (referenced above): Three lightweight checks applied after Gemini Flash Lite extraction, before graph insertion. (1) Reject entities that are bare email addresses or URLs -- these should be properties of a person/org entity, not standalone entities. (2) Reject facts where source and target are the same entity. (3) Reject facts with relationship names longer than 50 characters -- these are typically sentence fragments that the extractor failed to compress. At ~20-35% extraction error rate from Flash Lite, even crude filters have high ROI.

### Phase 3: Steady State (Month 2+)

- Weekly automated: T1.2, T1.5 (15 seconds to read)
- Monthly manual: T1.1, T1.3, T1.4, T2.1, T2.2, T2.3 (45 min)
- Continuous: T2.4 from proxy logs
- Quarterly: T2.5 false positive check, review staleness windows, refresh T2.1 golden dataset queries

---

## Success Criteria

1. Trust Score above 80 for 4 consecutive monthly measurements
2. T2.1 Czech recall above 80% (with appropriate embedding model)
3. T1.1 sampled accuracy above 85%
4. "Jaky je aktualni status s [any CRM client]?" returns one correct, current answer
5. Zero new duplicate clusters for 4 consecutive weeks
6. T2.4 agent memory engagement at 100%

---

## Appendix: Research Bibliography

| Tag | Source | Key finding | Used in |
|-----|--------|-------------|---------|
| Zaveri et al. | "Quality Assessment for Linked Data: A Survey" | 18 quality dimensions; completeness = property coverage | Framework structure, T2.2 |
| VLDB 2024 | Marchesin, efficient accuracy estimation | 100-200 samples from ~3K facts give 95% CI | T1.1 sample size |
| AAAI 2025 | Mattioli, KG qualification process | Per-characteristic KPIs for trustworthiness | Tier structure |
| DaReCzech | Nov 2024, 1.6M Czech pairs from Seznam.cz | Multilingual > English-only by 10-30% on Czech | Embedding decision |
| AAAI 2024 | Seznam Czech embedding models | "Competitive with significantly larger counterparts" | Embedding fallback |
| MMTEB | Multilingual MTEB leaderboard | Qwen-3-Embedding-0.6B beats BGE-M3 by 7.9% | Embedding ranking |
| Graphiti arch | Source code / docs | Entropy-gated fuzzy matching, Jaccard 0.9 | T1.2 limitations |
| Graphiti temporal | Source code / docs | Bi-temporal model, t_valid / t_invalid | T1.3, T1.4 |
| LLM NER lit | Zero-shot NER benchmarks | F1 40-60%, RE high recall / low precision | T1.1 error expectations |
| Flash Lite est | Extrapolated from model size | NER F1 35-50%, RE precision 25-40% | T1.1 baseline |
| GPT-4 matching | Zero-shot entity matching | 40-68% better than fine-tuned PLMs | T1.2 merge approach |
| KG Trust lit | Triple-level trust scoring | source * accuracy + freshness + structure | Future per-fact trust |
| Temporal KG | Staleness policy research | Per-type windows: status 1mo, relationships 3mo, contacts 6mo | T1.4 windows |
| RAGAS | RAG evaluation framework | Faithfulness >= 0.8, context recall | T2.3 design rationale |
| ANoT | Anomaly detection for temporal KGs | PR-AUC 0.83 for stale fact detection | Decided against |
