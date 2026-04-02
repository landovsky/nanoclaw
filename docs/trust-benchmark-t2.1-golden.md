# T2.1 Golden Dataset — Czech Query Recall Benchmark

Date: 2026-04-02
Graph: swan_crm (~1100 entities, ~2800 edges, ~570 episodes)
Models tested: bge-small-en-v1.5 (384-dim, EN-only) vs BGE-M3 (1024-dim, multilingual)

## Methodology

Each query has a **known expected entity UUID** from the graph. Scoring is binary:
- 1 = expected UUID appears in search_nodes top-5 results
- 0 = expected UUID does not appear

No subjective judgment. The "truth" is whether the specific entity was retrieved.

### Difficulty levels
- **exact**: query closely mirrors the stored entity name
- **synonym**: Czech synonym, inflection, or paraphrase of the entity name
- **alias**: abbreviation or common name vs formal stored name
- **conceptual**: describes the entity without using its name

## Golden Set (30 queries)

| # | Query | Difficulty | Expected Entity | Expected UUID |
|---|-------|-----------|----------------|---------------|
| 1 | parkovací stání | exact | parkovací stání | 372f75d9-0b55-43fc-828b-ef0984f3969e |
| 2 | Nadace Naše dítě | exact | Nadace Naše dítě | fda059bb-9cd1-4044-8573-ded739af3241 |
| 3 | AV technika | exact | AV technika | d6f56184-cb2b-457c-8408-d3901f8dd3ae |
| 4 | Prohlídka prostor | exact | Prohlídka prostor | 53a6e5a0-dec8-4660-adbf-339545cc33d2 |
| 5 | Hospodářská komora ČR | exact | Hospodářská komora ČR | d8dc9a47-c966-485a-9abe-6b51fd60bc46 |
| 6 | VIP večeře | exact | VIP večeře | 2380c00e-9874-4b4e-a83b-603c1ea229ec |
| 7 | DanceDifferent | exact | DanceDifferent | af6822b4-7610-4cf2-9393-b1c6ef6cebbe |
| 8 | Česká agentura pro standardizaci | exact | Česká agentura pro standardizaci | 5fe543e5-681c-4c60-b1a7-e3085e34d519 |
| 9 | parkování u budovy | synonym | parkovací stání | 372f75d9-0b55-43fc-828b-ef0984f3969e |
| 10 | podmínky rezervace | synonym | rezervačních podmínek | 0c2c2551-a1e7-4195-8a41-bef81edcca7b |
| 11 | zvuková technika ozvučení | synonym | ozvučení | ccc72d15-f314-4cd5-8d83-aa5b8dbd0904 |
| 12 | studené občerstvení raut | synonym | studený raut | 84fefefa-a6c6-466b-aa73-eb5b80016b71 |
| 13 | taneční večery salsa | synonym | DanceDifferent | af6822b4-7610-4cf2-9393-b1c6ef6cebbe |
| 14 | prohlídka budovy návštěva | synonym | Prohlídka prostor | 53a6e5a0-dec8-4660-adbf-339545cc33d2 |
| 15 | nezisková organizace sleva | synonym | nezisk | ac23a797-1406-413e-81ee-33951280f9e8 |
| 16 | uvítací drink přípitek | synonym | welcome drink | 8ab0eb52-3d37-4535-a2c4-c0a528c47adb |
| 17 | Akademie věd | alias | Středisko společných činností AV ČR, v.v.i. | 4b54d2a2-3c8d-4f2c-883a-e8d1ac44cee5 |
| 18 | NND nadace | alias | Nadace Naše dítě | fda059bb-9cd1-4044-8573-ded739af3241 |
| 19 | SOCR | alias | sekretariát SOCR | a846093d-83c0-4cb8-a5ff-a9a39c7069ac |
| 20 | Dr. Max | alias | Dr.Max CZE | 2380ce99-d90d-4d9c-a908-560200efb36b |
| 21 | KPMG | alias | KPMG Česká republika, s.r.o. | ac7d8f0e-bb36-461b-b96a-4083733345d5 |
| 22 | Seznam | alias | Seznam.cz, a.s. | a8a3e995-1495-4656-ba47-7ee86d6b6d59 |
| 23 | Svaz průmyslu | alias | Klub Svazu průmyslu a dopravy SP ČR | 5b3084e4-766e-46f3-9c50-85758a7682d8 |
| 24 | kde se dá zaparkovat | conceptual | parkovací stání | 372f75d9-0b55-43fc-828b-ef0984f3969e |
| 25 | firma co pořádá salsa večery v Labutí | conceptual | DanceDifferent | af6822b4-7610-4cf2-9393-b1c6ef6cebbe |
| 26 | virtuální realita zábava na akci | conceptual | Zero Latency Prague | 5365d8f1-2977-4255-96f5-7c7170696982 |
| 27 | vánoční dekorace ozdoby výzdoba | conceptual | vánoční výzdoba | da70f943-9388-4cab-b92e-ed3b2b8890f6 |
| 28 | farmaceutická firma léky | conceptual | Ferring-Léčiva a.s. | 887cf90c-9cec-4fdc-b8e7-a28e3f97d8fd |
| 29 | celý prostor pronájem všech pater | conceptual | Celá Labuť | 9ee2956c-1f87-4a1d-a75a-93bc8d7df2c1 |
| 30 | firemní akce s neomezeným pitím | conceptual | neomezený bar | d288e228-92e8-44be-a32d-a90fc7b137fe |

## Results

| # | Query | Difficulty | Hit | Returned top-5 (name) | Notes |
|---|-------|-----------|-----|----------------------|-------|
| 1 | parkovací stání | exact | YES | **parkovací stání**, křeslům, coffee station, pronájem, hotelové prostory | |
| 2 | Nadace Naše dítě | exact | YES | **Nadace Naše dítě**, Zuzana Šafářová, Influenceři, PhDr. Iva Kozáková, Dovychovat.cz | |
| 3 | AV technika | exact | YES | **AV technika**, Centrum transferu AV ČR, audio/video, ozvučení, Středisko společných činností AV ČR | |
| 4 | Prohlídka prostor | exact | YES | **Prohlídka prostor**, prostor, prezentace prostor, Tereza Benešová, hotelové prostory | |
| 5 | Hospodářská komora ČR | exact | YES | **Hospodářská komora ČR**, Hospodářská komora Praha 1, Česko-singapurská obchodní komora, ČR, Svaz průmyslu a dopravy ČR | |
| 6 | VIP večeře | exact | YES | **VIP večeře**, VIP partnerů, večeře, doprovodů, Notix | |
| 7 | DanceDifferent | exact | YES | **DanceDifferent**, dance@dancedifferent.cz, Kateřina Loginov, BetterHotel, DJ | |
| 8 | Česká agentura pro standardizaci | exact | YES | **Česká agentura pro standardizaci**, česko-korejský workshop, Českou republiku, Česká spořitelna, Marcela Trägerová | |
| 9 | parkování u budovy | synonym | YES | Double-U, **parkovací stání**, U Aleše na střeše, Prohlídka prostor, sezení u oken | Position 2 |
| 10 | podmínky rezervace | synonym | YES | rezervace, **rezervačních podmínek**, nabídka, zvýhodněné nabídky, dvojí booking | Position 2 |
| 11 | zvuková technika ozvučení | synonym | YES | **ozvučení**, AV technika, konference, audio/video, podkreslující hudba | |
| 12 | studené občerstvení raut | synonym | YES | Rautové občerstvení, Raut I., **studený raut**, Raut II, občerstvení | Position 3 |
| 13 | taneční večery salsa | synonym | YES | Malá Salsa, Velká Salsa, program večera, **DanceDifferent**, lehká diskotéka | Position 4 |
| 14 | prohlídka budovy návštěva | synonym | YES | **Prohlídka prostor**, meeting, výstava, setkání s klienty, zasedací místnost | |
| 15 | nezisková organizace sleva | synonym | **NO** | organizace akcí pro klienty, zvýhodněné nabídky, firma/organizace, nabídka, OMT group | Entity "nezisk" not retrieved |
| 16 | uvítací drink přípitek | synonym | YES | **welcome drink**, Welcome drink II, Nealko welcome drink, Welcome drink vánoční punč, nápojový balíček | |
| 17 | Akademie věd | alias | **NO** | Hans-Jörg Schmidt, Českou republiku, European Parliament, Central Europe, Řecko | Complete miss — no semantic bridge to "Středisko společných činností AV ČR" |
| 18 | NND nadace | alias | YES | NND, **Nadace Naše dítě**, nealko, Zuzana Šafářová, 2N | |
| 19 | SOCR | alias | YES | **sekretariát SOCR**, sekretariat@socr.cz, socr.cz, CRM, Svaz obchodu a cestovního ruchu ČR | |
| 20 | Dr. Max | alias | YES | Dr. Max BDC, **Dr.Max CZE**, René Tran, Status, Lucie Maxová | |
| 21 | KPMG | alias | YES | **KPMG Česká republika, s.r.o.**, Lucie Vaněčková, TMR International, Event pro Expaty, McKinsey | |
| 22 | Seznam | alias | YES | Seznam Zprávy, **Seznam.cz, a.s.**, Radlická 3294/10 Praha 5, Soňa Borodáčová, osoby | |
| 23 | Svaz průmyslu | alias | YES | Svaz průmyslu a dopravy ČR, **Klub Svazu průmyslu a dopravy SP ČR**, Svaz pekařů a cukrářů, Asociace inovativního farmaceutického průmyslu, Svaz moderní energetiky | |
| 24 | kde se dá zaparkovat | conceptual | YES | vaječňák, **parkovací stání**, kreativní workshop, pronájem, Tereza Benešová | Position 2; "vaječňák" at #1 is noise |
| 25 | firma co pořádá salsa večery v Labutí | conceptual | **NO** | Velká Salsa, letní firemní večírek, Malá Salsa, firemní akce, PAVIAAN CO. | Found salsa events but not the organizer entity |
| 26 | virtuální realita zábava na akci | conceptual | **NO** | hosteska, firemní akce, Na Poříčí, soutěžní event, Na Florenci | No connection to "Zero Latency" — entity name shares no terms with query |
| 27 | vánoční dekorace ozdoby výzdoba | conceptual | YES | **vánoční výzdoba**, diy dekorace, Vánoční večírek PFC, vánoční večírek, Welcome drink vánoční punč | |
| 28 | farmaceutická firma léky | conceptual | **NO** | firma/organizace, zdravotnické firmy, státních firem, Asociace inovativního farmaceutického průmyslu, Česká lékárna HOLDING | "Ferring-Léčiva" not retrieved; got related pharma entities but not the expected one |
| 29 | celý prostor pronájem všech pater | conceptual | **NO** | pronájem, prostor, prezentace prostor, Prohlídka prostor, konferenční prostory | "Celá Labuť" name is a play-on-words; embedding can't bridge it |
| 30 | firemní akce s neomezeným pitím | conceptual | **NO** | firemní akce, akce, firemní večírek, Soukromá akce, letní firemní večírek | "neomezený bar" not retrieved — concept not in any returned entity |

## Scores by Difficulty

| Difficulty | Queries | Hits | Score |
|-----------|---------|------|-------|
| exact | 8 | 8 | **100%** |
| synonym | 8 | 7 | **87.5%** |
| alias | 7 | 6 | **85.7%** |
| conceptual | 7 | 2 | **28.6%** |
| **Total** | **30** | **23** | **76.7%** |

## Failure Analysis (7 misses)

| # | Query | Why it failed |
|---|-------|--------------|
| 15 | nezisková organizace sleva | Entity is named "nezisk" (colloquial shorthand). The query "nezisková organizace" should be semantically close but BGE-M3 didn't bridge the nominalization. |
| 17 | Akademie věd | Entity stored as "Středisko společných činností AV ČR, v.v.i." — a subsidiary name. "Akademie věd" is the parent institution; the graph has no alias linking them. This is a **graph gap**, not an embedding failure. |
| 25 | firma co pořádá salsa večery v Labutí | Found "Velká Salsa" and "Malá Salsa" (event names) but not "DanceDifferent" (the organizer). The embedding correctly identified salsa context but the organizer entity name has zero Czech/salsa terms — it's an English brand name. |
| 26 | virtuální realita zábava na akci | "Zero Latency Prague" shares no terms with "virtuální realita". The entity name is a brand; the summary mentions VR but node search embeds names, not summaries. |
| 28 | farmaceutická firma léky | Got "Asociace inovativního farmaceutického průmyslu" and "Česká lékárna HOLDING" — both more relevant than the expected "Ferring-Léčiva". The expected entity was arbitrary; the retrieval was actually reasonable. **Questionable golden set entry.** |
| 29 | celý prostor pronájem všech pater | "Celá Labuť" literally means "Whole Swan" — a venue name that is a pun. No semantic path from "celý prostor" to this specific brand name. |
| 30 | firemní akce s neomezeným pitím | "neomezený bar" is a concept node, not semantically close to "neomezené pití" in embedding space. Also, the concept is buried among 1100 entities. |

## A/B Comparison: bge-small-en-v1.5 vs BGE-M3

Both models were tested against the same golden set on the same graph data. Only the embedding model changed; entity data, graph structure, and search logic were identical.

| # | Query | Difficulty | bge-small | BGE-M3 | Delta |
|---|-------|-----------|:-:|:-:|:-:|
| 1 | parkovací stání | exact | YES | YES | = |
| 2 | Nadace Naše dítě | exact | YES | YES | = |
| 3 | AV technika | exact | YES | YES | = |
| 4 | Prohlídka prostor | exact | YES | YES | = |
| 5 | Hospodářská komora ČR | exact | YES | YES | = |
| 6 | VIP večeře | exact | YES | YES | = |
| 7 | DanceDifferent | exact | YES | YES | = |
| 8 | Česká agentura pro standardizaci | exact | YES | YES | = |
| 9 | parkování u budovy | synonym | YES | YES | = |
| 10 | podmínky rezervace | synonym | YES | YES | = |
| 11 | zvuková technika ozvučení | synonym | YES | YES | = |
| 12 | studené občerstvení raut | synonym | YES | YES | = |
| 13 | taneční večery salsa | synonym | YES | YES | = |
| 14 | prohlídka budovy návštěva | synonym | YES | YES | = |
| 15 | nezisková organizace sleva | synonym | NO | NO | = |
| 16 | uvítací drink přípitek | synonym | YES | YES | = |
| 17 | Akademie věd | alias | NO | NO | = |
| 18 | NND nadace | alias | YES | YES | = |
| 19 | SOCR | alias | YES | YES | = |
| 20 | Dr. Max | alias | YES | YES | = |
| 21 | KPMG | alias | YES | YES | = |
| 22 | Seznam | alias | YES | YES | = |
| 23 | Svaz průmyslu | alias | YES | YES | = |
| 24 | kde se dá zaparkovat | conceptual | **NO** | **YES** | **+M3** |
| 25 | firma co pořádá salsa večery | conceptual | NO | NO | = |
| 26 | virtuální realita zábava na akci | conceptual | NO | NO | = |
| 27 | vánoční dekorace ozdoby výzdoba | conceptual | YES | YES | = |
| 28 | farmaceutická firma léky | conceptual | NO | NO | = |
| 29 | celý prostor pronájem všech pater | conceptual | NO | NO | = |
| 30 | firemní akce s neomezeným pitím | conceptual | NO | NO | = |

### Scores by Difficulty

| Difficulty | bge-small-en-v1.5 | BGE-M3 | Delta |
|-----------|:-:|:-:|:-:|
| exact (8) | 8/8 = 100% | 8/8 = 100% | 0 |
| synonym (8) | 7/8 = 87.5% | 7/8 = 87.5% | 0 |
| alias (7) | 6/7 = 85.7% | 6/7 = 85.7% | 0 |
| conceptual (7) | 1/7 = 14.3% | 2/7 = 28.6% | +1 |
| **Total** | **22/30 = 73.3%** | **23/30 = 76.7%** | **+3.3pp** |

### The one difference: Query #24

"kde se dá zaparkovat" (where can one park) → expected "parkovací stání" (parking spot).

- **bge-small-en-v1.5**: returned vaječňák, Dům zahraniční spolupráce, workshop, asistentka, Na Florenci — complete miss
- **BGE-M3**: returned vaječňák, **parkovací stání** (position 2), workshop, pronájem, Tereza Benešová — hit

BGE-M3 bridged the Czech conceptual gap ("kde se dá zaparkovat" → "parkovací stání") that the English-only model could not.

## Key Insights

1. **Exact, synonym, alias: identical.** Both models score identically on 23/30 queries. The English-only model handles Czech entity names surprisingly well because entity names contain enough lexical overlap.
2. **Conceptual: marginal BGE-M3 edge.** The only difference is one Czech conceptual query. The improvement is real but tiny (+3.3pp).
3. **7 shared failures are NOT embedding failures.** They are graph gaps (missing aliases, missing entities) and architecture limitations (name-only search can't match conceptual descriptions to brand names).
4. **The previous subjective benchmarks measured noise.** Agent-judged scoring varied by 30pp between runs (62.5%–92.5%). The golden benchmark shows the actual model difference is 3.3pp.

## Actionable Conclusions

**The embedding model is not the bottleneck.** Both models achieve ~75% on this golden set. The 7 failures fall into two categories:

**A. Graph gaps (fixable with better extraction):**
- Missing aliases (#17: Akademie věd → Středisko společných činností AV ČR)
- Missing concept nodes (#15: "nezisk" too colloquial, no formal entity for "nezisková organizace")

**B. Architecture limitation — name-only search (requires design change):**
- Queries #25-26, #28-30 describe what an entity *does* but the entity name is a brand/proper noun (Zero Latency, DanceDifferent, Celá Labuť, Ferring-Léčiva, neomezený bar)
- Node search embeds entity names only, not summaries
- Potential fix: hybrid search combining name embeddings + fulltext summary search

**Recommendation:** Keep BGE-M3 (it doesn't hurt, costs nothing extra, and is architecturally correct for Czech). Focus improvement efforts on entity extraction quality and hybrid search, not embedding models.

---

## Negative Query Set — False Positive Analysis

10 queries for things that should NOT exist in the graph. The system always returns 5 results regardless — there is no "nothing found" signal. This tests whether results could mislead an agent into believing false information exists.

### Scoring
- **safe**: results are clearly irrelevant — low risk of agent misinterpretation
- **misleading**: results are tangentially related and could fool an agent into treating them as real matches

| # | Query | Domain | Risk | Top results | Why risky / safe |
|---|-------|--------|------|------------|-----------------|
| 1 | hotel booking Brno | wrong city | **misleading** | Brno, dvojí booking, hotelové prostory, Marriott Prague | "Brno" and "hotelové prostory" exist in the CRM — agent could think hotel bookings in Brno are tracked |
| 2 | autoservis pneumatiky výměna oleje | car repair | safe | rekonstrukce klimatizace, servis číšník, pojišťovna | Nothing car-related; clearly irrelevant |
| 3 | restaurace sushi japonská kuchyně | restaurant | **misleading** | jídlo, občerstvení, večeře, oběd, oběd bufet | CRM has catering entities — agent could think sushi catering exists |
| 4 | letenky do Barcelony | flights | safe | druhý kolega, Etihad Airways, nezisk | Etihad is an event client, not a flight booking; low confusion risk |
| 5 | účetní software fakturoid pohoda | accounting | **misleading** | HR software, First Line Software, finanční oddělení | Software companies are event clients — agent could confuse domains |
| 6 | pronájem bytu 3+1 Žižkov | apartment | **misleading** | Národní 1009/3, pronájem, Praha 3 | CRM has "pronájem" (venue rental) and Prague addresses — easy to confuse |
| 7 | veterinární klinika očkování psa | vet clinic | **misleading** | IVF klinika, Klinika LaserPlastic, Urologická klinika | Clinics exist as event clients — agent could hallucinate a vet connection |
| 8 | kurz angličtiny pro začátečníky | language course | **misleading** | baristický kurz, workshop, Event pro Expaty | Courses and workshops exist in the CRM |
| 9 | hokejový zápas vstupenky | sports tickets | safe | soutěžní event, poker, meeting | Tangential but clearly not hockey tickets |
| 10 | dětské hřiště prolézačky | playground | **misleading** | herna pro děti, Prohlídka prostor, diy dekorace | "herna pro děti" (children's playroom) genuinely exists in the venue! |

### Results

- **Safe (no false positive risk):** 3/10 (queries 2, 4, 9)
- **Misleading (could cause agent hallucination):** 7/10 (queries 1, 3, 5, 6, 7, 8, 10)

### Analysis

The system has **no confidence threshold** — it always returns 5 results, even for queries completely outside the domain. Because the CRM contains diverse entities (catering, addresses, clinics, software companies, workshops, children's facilities), most irrelevant queries surface *tangentially plausible* results.

This is a significant reliability problem: an agent querying memory-store for "veterinární klinika" gets back "IVF klinika, Klinika LaserPlastic, Urologická klinika" and has no signal that these are irrelevant. The results look like real matches.

### Mitigation Options

1. **Expose similarity scores** — if Graphiti returned cosine similarity, the agent could threshold (e.g., ignore results below 0.7). Requires upstream change.
2. **Agent-side prompt guardrails** — instruct agents to critically evaluate whether results actually match the query, not just accept top-N.
3. **Domain-scoped search** — add entity_type filtering so queries like "firma" only search Company entities, reducing noise from catering items and addresses.
4. **Minimum relevance gate** — a wrapper that embeds the query AND each result name, computes pairwise similarity, and filters results below a threshold before returning to the agent.
