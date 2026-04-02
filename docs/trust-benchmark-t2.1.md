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
