# T2.1 Czech Query Recall Benchmark — Baseline

Date: 2026-04-02
Embedding model: bge-small-en-v1.5 (33M params, 384-dim, English-only)
Graph: swan_crm (~1100 entities, ~540 episodes)

## Results

| # | Query | Type | Found? | Score |
|---|-------|------|--------|-------|
| 1 | firmy společnosti klienti | Czech generic | NO — 0 results | 0 |
| 2 | kontaktní osoby | Czech generic | NO — 0 results | 0 |
| 3 | poptávky akce events inquiry | Mixed CZ+EN | YES | 1 |
| 4 | Černá Labuť | Proper name CZ | PARTIAL — variants only | 0.5 |
| 5 | McKinsey | Proper name EN | YES | 1 |
| 6 | Tereza Landovská | Proper name CZ | YES | 1 |
| 7 | Kdo je kontaktní osoba pro McKinsey | Czech question | YES | 1 |
| 8 | firemní večírek prostor pronájem | Czech concept | YES | 1 |
| 9 | Bird & Bird | Proper name EN | YES | 1 |
| 10 | svatba wedding party | Mixed CZ+EN | YES | 1 |
| 11 | zrušené rezervace stornované akce | Czech concept | NO — wrong results | 0 |
| 12 | catering jídlo občerstvení | Czech concept | YES | 1 |
| 13 | Samsung | Proper name EN | YES | 1 |
| 14 | konference seminář školení | Czech concept | YES | 1 |
| 15 | eBay Karolína Schonová | Proper names | YES | 1 |
| 16 | nabídka odeslána čeká na potvrzení | Czech status | YES | 1 |
| 17 | Roche | Proper name EN | YES | 1 |
| 18 | kdo pracuje pro Seznam | Czech question | PARTIAL — indirect | 0.5 |
| 19 | Pravé křídlo Levé křídlo prostory | Czech proper name | YES | 1 |
| 20 | CzechInvest | Proper name EN | YES | 1 |

## Score: 15/20 = 75% recall@5

## Failure Analysis

- Pure Czech generic queries: 0/2 (total failure)
- Czech concept queries: 4/5 (one failure on "cancellations")
- Czech questions: 1.5/2 (partial on "kdo pracuje pro Seznam")
- Proper names (EN): 5/5 (perfect)
- Proper names (CZ): 2.5/3 (partial on Černá Labuť — returns variants not canonical)
- Mixed CZ+EN: 2/2 (perfect)

## Decision

Below 80% threshold → triggers Phase 2a: BGE-M3 migration.

---

# T2.1 Post-Migration Benchmark — BGE-M3

Date: 2026-04-02
Embedding model: BAAI/bge-m3 (567M params, 1024-dim, 100+ languages)
Graph: swan_crm (~1600 entities, ~2800 edges, ~570 episodes)

## Agent A — Score: 15.5/20 = 77.5%

| # | Query | Type | Found? | Score |
|---|-------|------|--------|-------|
| 1 | fakturace platby úhrady | Czech generic | YES | 1 |
| 2 | technické vybavení sálu projektor ozvučení | Czech generic | YES | 1 |
| 3 | kolik stojí pronájem na celý den | Czech question | PARTIAL | 0.5 |
| 4 | termíny obsazenost dostupnost | Czech generic | PARTIAL | 0.5 |
| 5 | smlouva smluvní podmínky | Czech generic | YES | 1 |
| 6 | kde se konají největší akce | Czech question | YES | 1 |
| 7 | firemní vánoční večírek | Czech concept | YES | 1 |
| 8 | kapacita počet osob míst | Czech generic | PARTIAL | 0.5 |
| 9 | jaké firmy pořádaly akce v minulosti | Czech question | YES | 1 |
| 10 | Chaos Czech | Proper name | YES | 1 |
| 11 | nabídka cena rozpočet kalkulace | Czech generic | YES | 1 |
| 12 | kdo odpovídá za organizaci akcí | Czech question | YES | 1 |
| 13 | teambuilding firemní program | Czech concept | YES | 1 |
| 14 | Deloitte | Proper name | NO — not in graph | 0 |
| 15 | parkovací možnosti doprava přístup | Czech generic | YES | 1 |
| 16 | plánované akce příští měsíc | Czech concept | PARTIAL | 0.5 |
| 17 | Lucie Cáliková | Proper name CZ | YES | 1 |
| 18 | storno podmínky zrušení záloha | Czech generic | PARTIAL | 0.5 |
| 19 | koktejl recepce raut | Czech concept | YES | 1 |
| 20 | Akademie věd vědecká konference | Czech institution | NO — stored as "Středisko společných činností AV ČR" | 0 |

## Agent B — Score: 12.5/20 = 62.5%

| # | Query | Type | Found? | Score |
|---|-------|------|--------|-------|
| 1 | platební podmínky fakturace | Czech generic | YES | 1 |
| 2 | kolik lidí se vejde do sálu | Czech question | PARTIAL | 0.5 |
| 3 | technické vybavení projektor ozvučení | Czech generic | YES | 1 |
| 4 | kde se konala poslední vánoční akce | Czech question | YES | 1 |
| 5 | smlouva podmínky pronájmu | Czech generic | YES | 1 |
| 6 | Chaos Czech | Proper name | YES | 1 |
| 7 | jaké typy akcí se nejčastěji pořádají | Czech question | YES | 1 |
| 8 | kdy byla poslední prohlídka prostor | Czech question | YES | 1 |
| 9 | cenová nabídka rozpočet | Czech generic | YES | 1 |
| 10 | teambuilding firemní akce | Czech concept | YES | 1 |
| 11 | výzdoba květiny dekorace | Czech generic | PARTIAL | 0.5 |
| 12 | parkování doprava přístup | Czech generic | PARTIAL | 0.5 |
| 13 | Akademie věd | Proper name CZ | NO — alias mismatch | 0 |
| 14 | storno poplatek penále | Czech generic | NO — no anchor nodes | 0 |
| 15 | Lucie Cáliková | Proper name CZ | YES | 1 |
| 16 | koktejl recepce společenský večer | Czech concept | PARTIAL | 0.5 |
| 17 | jaký je stav otevřených poptávek | Czech question | YES | 1 |
| 18 | víkendový termín dostupnost | Czech generic | NO — abstract concept | 0 |
| 19 | kapacita stání banket divadlo | Czech concept | NO — polysemy "stání" | 0 |
| 20 | nájemce dlouhodobý pronájem | Czech generic | PARTIAL | 0.5 |

## Agent C — Score: 15.5/20 = 77.5%

| # | Query | Type | Found? | Score |
|---|-------|------|--------|-------|
| 1 | fakturační údaje IČO DIČ | Czech generic | YES | 1 |
| 2 | kolik lidí se vejde do sálu | Czech question | PARTIAL | 0.5 |
| 3 | termín dostupnost volný datum | Czech generic | PARTIAL | 0.5 |
| 4 | cena pronájmu za hodinu | Czech generic | YES | 1 |
| 5 | technické vybavení projektor ozvučení | Czech generic | YES | 1 |
| 6 | parkování v okolí budovy | Czech generic | YES | 1 |
| 7 | kde se konala vánoční akce | Czech question | YES | 1 |
| 8 | jaké firmy pořádaly teambuilding | Czech question | YES | 1 |
| 9 | kdo objednal catering pro více než 50 osob | Czech question | PARTIAL | 0.5 |
| 10 | smlouva platební podmínky záloha | Czech generic | YES | 1 |
| 11 | Chaos Czech | Proper name | YES | 1 |
| 12 | Lucie Cáliková | Proper name CZ | YES | 1 |
| 13 | kdy proběhla poslední prohlídka prostor | Czech question | YES | 1 |
| 14 | Akademie věd | Proper name CZ | NO — alias mismatch | 0 |
| 15 | nedokončené poptávky bez odpovědi | Czech status | PARTIAL | 0.5 |
| 16 | rooftop terasa střešní prostor | Czech generic | YES | 1 |
| 17 | výzdoba květiny dekorace | Czech generic | YES | 1 |
| 18 | Olga Malá | Proper name CZ | YES | 1 |
| 19 | kolik stojí pronájem celého patra | Czech question | PARTIAL | 0.5 |
| 20 | firemní oslava narozenin výročí | Czech concept | YES | 1 |

## Aggregate Results

| | Baseline (bge-small-en-v1.5) | Post-Migration (BGE-M3) |
|---|---|---|
| My benchmark | 75% | — |
| Agent A | 92.5%* | 77.5% |
| Agent B | 70% | 62.5% |
| Agent C | — | 77.5% |
| **Average** | **79%** | **72.5%** |

*Baseline Agent A used name-heavy queries (inflated score)

## Analysis

BGE-M3 scored 72.5% average vs 79% baseline — **no improvement, slight regression**.

### Consistent failures across all agents:
1. **"Akademie věd"** — entity stored as "Středisko společných činností AV ČR", no alias bridging
2. **Abstract status/workflow queries** — cancellations, availability, pricing logic
3. **Capacity/filtering queries** — "kolik lidí se vejde", "kolik stojí"
4. **Czech polysemy** — "stání" (standing arrangement vs parking)

### Root cause: NOT the embedding model
The failures are **graph coverage gaps** (missing entities, missing aliases, missing concepts), not embedding similarity failures. Both bge-small-en-v1.5 and BGE-M3 retrieve well when query terms overlap with stored entity names. The bottleneck is:
1. **Entity extraction quality** (Gemini Flash missing aliases, abbreviations, abstract concepts)
2. **Graph sparsity** (no nodes for cancellation policies, availability, capacity layouts)
3. **No alias/synonym layer** between user vocabulary and stored entity names

### Decision
T2.1 remains below 80%. The embedding model is not the bottleneck — further improvement requires better entity extraction and alias management (Phase 2a remaining items: post-extraction validation rules, entity enrichment).
