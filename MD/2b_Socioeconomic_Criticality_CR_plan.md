# Plan: `2b_Socioeconomic_Criticality_CR` — IDS-attributed criticality

Source notebook: `notebooks/2_Main_Network_Criticality_Analysis_CR.ipynb` (unchanged)
Target notebook: `notebooks/2b_Socioeconomic_Criticality_CR.ipynb` (new)

Aim: split every criticality metric that is currently reported per road (VHL, PHL, …) into the
share borne by each **MIDEPLAN IDS 2023 district quintile**, and map the result. Related:
[district_income_shares_CR.md](district_income_shares_CR.md) (why IDS is a development ranking,
not an income measure), [gravity_model_adjusted.md](gravity_model_adjusted.md).

Status: **built and run.** `notebooks/2b_Socioeconomic_Criticality_CR.ipynb` executes clean
top-to-bottom (45 cells, both routes). Everything marked ✅ is measured, not assumed.

---

## 1. What already exists — 2b recomputes none of it

| Artefact | Where | 2b uses it |
|---|---|---|
| Directed network, 9 764 edges ✅ | `intermediate_results/gpkg/network/main_network_directed.gpkg` | read only |
| Percolation results, 5 012 physical roads ✅ | `intermediate_results/gpkg/travel_disruptions/physical_criticality_results.gpkg` (layer `criticality`) | read only — **the percolation is never re-run in the default path** |
| Directed criticality, 9 764 rows ✅ | `intermediate_results/gpkg/travel_disruptions/criticality_results.gpkg` | read only |
| IDS 2023 districts, 492 polygons, EPSG:8908 ✅ | `input_files/ids_2023_distrital/ids_2023_distrito.shp` | join key `CODIGO_DTA`, class `QUINTIL` (I–V) |
| Localities, 493 points ✅ | `input_files/CENTROS_POBLACION/centros_poblados_localidades.shp` | OD nodes, key `CÓDIGO_DTA` |

The one thing 2b **must** rebuild is the OD demand matrix, because notebook 2 never saved it.
That is cheap: graph build + snap + one all-pairs run is **0.2 s for the 485×485 matrix** ✅, so
the whole reconstruction is well under a minute and is deterministic — same code, same numbers.

Everything expensive that 2b does add is cached to parquet and skipped on re-run.

---

## 2. Data audit — verified facts that shape the method

- **The OD layer is already district-level.** 493 localities, 493 distinct `CÓDIGO_DTA` ✅ — one
  point per district (`Poblado/Cabecera de Distrito`) carrying the district's projected
  population, 5 167 278 total ✅. So "merge origin and destination municipalities to the IDS
  ranking" is a plain code join, no spatial aggregation, no areal interpolation.
- **Snapping collapses 8 localities onto 6 shared network nodes** ✅ (485 OD nodes from 493
  localities). Those 6 nodes each carry 2–3 districts, and in every case the districts sit in
  *different* quintiles → handled with a population-weighted quintile *membership vector* per
  node rather than an arbitrary label. For the other 479 nodes the vector is one-hot.
- **IDS quintiles are equal-count in districts, not in people** ✅: 98 districts each, but
  Q-I = 583 672 people (11.3 %) and Q-V = 1 284 096 (24.9 %). Any statement of the form "quintile V carries most of
  the PHL" is therefore partly mechanical — every headline number needs a population-share
  denominator (see §7).
- **Three localities have no quintile on the code join** ✅ (11 220 people = 0.22 %); the spatial
  fallback resolves two of them, leaving 4 823 people = 0.09 % unclassified:
  - `50405` Pijije (Bagaces) and `60310` Cabagra (Buenos Aires) — districts created after the IDS
    2023 district set; **resolved by spatial fallback**: the point falls inside the parent
    district's IDS polygon, so join on code first, then containment for the residual.
  - `40207` Puente Salas (Barva) — present in IDS but with `IDS_2023 = 0.0` and `QUINTIL = None`,
    i.e. a genuine data gap. 4 823 people = 0.09 %. Kept as an explicit `unclassified` class,
    never silently dropped, never imputed to quintile I.
  - Note `IDS_2023 = 0.0` is missing-data, not a real score — use `QUINTIL`, never a fresh
    numeric cut on `IDS_2023`. `Isla del Coco` (60110) has no locality and no network ✅.

---

## 3. How A→B and B→A counting works — the AADT question

This has to be settled before any attribution, because getting it wrong doubles or halves
everything downstream. What the pipeline actually does ✅ (from 1b and cell 28 of notebook 2):

1. **1b splits a bidirectional road's two-way AADT evenly across its two directed edges**
   (`aadt_direction_factor = 0.5`); a unidirectional road keeps the full count on its single edge.
   So on a *directed edge* `total_aadt` is a **per-direction** flow.
2. **`physical_results` sums the traffic columns over the road's directed edges**, recovering the
   full **two-way** daily figure. Verified numerically: 9 764 directed edges, mean `total_aadt`
   4 252; 5 012 physical roads, mean `total_aadt` 8 283 ≈ 2× ✅.
3. `average_time_disruption` is a property of the **physical road** and is identical on both
   directed edges — the percolation deletes both at once.

So today's `phl = Δt × Σ_k occ_k · AADT_k` on a physical road already counts each direction
exactly once. There is no double counting to fix; there is a *decomposition* to add.

**Now the attribution.** The gravity matrix is symmetric by construction (`D_ab = D_ba`), but the
network is directed, so the path a→b and the path b→a need not use the same edges. Assignment
therefore produces flow per **directed** edge, and on directed edge `A→B`:

```
flow(A→B)  =  Σ over OD pairs (o,d) whose shortest path uses A→B  of  D_od
```

Attribute each of those trips to the quintile of its **origin** district `q_o`. Then for a
bidirectional physical road, summing its two directed edges gives

```
road_flow[q]  =  Σ_{o: q_o = q} D_od  over paths using A→B
              +  Σ_{o: q_o = q} D_od  over paths using B→A
```

and because `D_ab = D_ba`, every OD pair contributes `D_ab` under `q_a` (outbound) and the same
`D_ab` under `q_b` (return). **Origin attribution summed over both directions is therefore
identical to splitting each round trip 50/50 between the two districts' quintiles.** That
equivalence is what makes the road-level result well defined regardless of which direction you
look from, and it is the reason no direction is counted twice: each direction is counted once and
charged to its own trip producer.

Two consequences worth stating in the paper:

- On a **one-way** road only one direction exists, so only the origins whose paths use it are
  charged. That asymmetry is real network behaviour, not an artefact.
- If you want **per-direction** results (e.g. a corridor that serves commuting into San José in
  the morning), keep the directed-edge table and do *not* sum — the directed layer is written out
  for exactly this.

**Invariants asserted in the notebook:** `Σ_q flow_q[e] == flow[e]` on every directed edge, and
`Σ_q phl_q[road] == phl[road]` on every physical road, to floating-point tolerance.

---

## 4. Core method (Route A — default, no percolation re-run)

### 4.1 Build the quintile membership of each OD node

```
locality --CÓDIGO_DTA--> IDS district --QUINTIL--> q ∈ {1..5, unclassified}
node w[q] = Σ_localities_at_node pop · 1[quintile = q] / Σ pop      (one-hot for 478 of 485 nodes)
```

### 4.2 Assign demand to paths, keeping a 6×6 tensor

One pass over origins, exactly the loop already in cell 47 of notebook 2, with the accumulator
widened from one array to a `(6, 6, n_edges)` tensor (5 quintiles + unclassified, origin × destination):

```python
for o in origins:
    paths = graph.get_shortest_paths(o, to=destinations, weights="fft", output="epath")
    for d, path in zip(destinations, paths):
        F[q_o, q_d, path] += D[o, d]
```

Cost is the same order as cell 47 (~1–2 min); memory is 36 × 9 764 floats — nothing. Cached to
`intermediate_results/parquet/socioeconomic/od_quintile_flow.parquet`, so the notebook only ever
computes it once. Keeping the full 6×6 is free and means every collapse rule below is a
post-processing choice rather than a re-run.

### 4.3 Collapse the tensor to a quintile share per directed edge

| Rule | Definition | Reading |
|---|---|---|
| **Origin** (default) | `f[q] = Σ_j F[q, j]` | who *produces* the trip — matches production-side logic in `gravity_model_adjusted.md` |
| Destination | `f[q] = Σ_i F[i, q]` | who is being *reached* |
| 50/50 pair | `f[q] = ½(Σ_j F[q,j] + Σ_i F[i,q])` | identical to Origin once both directions of a road are summed (§3) |
| Worst-off | `f[min(i,j)] += F[i,j]` | equity-conservative: a trip between Q-I and Q-V counts as Q-I |

All four preserve `Σ_q f[q] = total flow`, so all four are additive decompositions. The default is
Origin; the others are one-line switches and are computed for the sensitivity table.

```
share_q[e] = f_q[e] / Σ_q f_q[e]
```

### 4.4 Rescale onto observed AADT and derive the metric columns

Composition comes from the gravity model, **magnitude from observed AADT** — the gravity scale is
arbitrary anyway (notebook 2 says so explicitly), so this is the only defensible pairing.

Per directed edge `e`, per quintile `q`:

```
aadt_q[e]      = total_aadt[e] · share_q[e]          # "count_AADT_modelled_quantile_k"
pct_aadt_q[e]  = 100 · share_q[e]                    # "%age_AADTS_quantile_k"
vhl_q[e]       = average_time_disruption[e] · aadt_q[e]
phl_q[e]       = average_time_disruption[e] · (Σ_k occ_k · AADT_k[e]) · share_q[e]
pkl_q[e]       = average_dist_disruption[e] · (Σ_k occ_k · AADT_k[e]) · share_q[e]
```

`PASSENGER_FACTORS` is re-declared identically to notebook 2 so the totals reconcile exactly.

**Aggregate flow first, divide second.** At the *physical road* level the shares are computed from
the summed flow of the road's directed edges, not by summing per-edge splits. The distinction is
not cosmetic: 115 directed edges ✅ carry `PHL > 0` while attracting no assigned flow **in their own
direction** — a bidirectional road can pull traffic one way only, while its removal (which deletes
both edges) still delays people. Dividing per edge would drop those edges' share of the road's
disruption on the floor; dividing after the sum is exact. The directed layer keeps the per-edge
shares anyway, flagged as diagnostic.

**Edge case that cannot bite:** demand is `np.ceil(...)` so every off-diagonal pair has ≥ 1 trip,
hence any *road* with `average_time_disruption > 0` necessarily lies on at least one shortest path
and has positive modelled flow. `{PHL > 0} ⊆ {flow > 0}` at road level — asserted, not assumed, and
the converse is asserted too (no-flow roads must have zero disruption).

**Coverage to report:** 3 056 of 5 012 roads receive a split, covering **76.1 % of the two-way
AADT** ✅. The remaining roads carry observed traffic but lie on no modelled shortest path; their
disruption is zero, so no PHL is lost, but their AADT has no attribution and that bound belongs in
the write-up.

---

## 5. Route B — exact per-quintile disruption (optional, ~20 min, cached)

Route A assumes that, on a given road, **the delay per trip is the same whatever quintile the trip
comes from**. There is good reason to doubt it — remote, low-IDS districts sit on tree-like network
branches, take the longest detours, and are the ones that collect `ISOLATION_PENALTY_HOURS` when a
link fails — so the assumption gets tested rather than asserted. **Result: it holds.** See §5.1.

The fix needs the per-pair delay matrix at each removal, which notebook 2 did not store. Re-running
the percolation while accumulating, per origin quintile,

```
num_q = Σ_{delayed pairs} D_od · W[o, q] · (t_fail − t_base)
den_q = Σ_{delayed pairs} D_od · W[o, q]
```

gives both the quintile-specific mean delay `Δt_q = num_q / den_q` **and an exactly additive
decomposition**, because `Σ_q num_q / Σ_q den_q` is by construction notebook 2's
`average_time_disruption`. The share of a road's disruption borne by quintile *q* is therefore

```
β_q = num_q / Σ_q num_q         and        phl_road[q] = phl_road · β_q
```

with `Σ_q phl_road[q] == phl_road` to floating point. So Route A and Route B decompose the *same*
published totals under two different weightings — flow share vs delay share — and are directly
comparable. The notebook asserts that the recomputed `average_time_disruption` and
`average_dist_disruption` reproduce the saved values (max abs error is reported), which doubles as
a check that the rebuilt demand matrix is identical to notebook 2's.

**Measured cost: 0.198 s per all-pairs solve × 5 012 roads ≈ 17 min** ✅ (call it 20–30 with graph
copies). Cached to `intermediate_results/parquet/socioeconomic/quintile_disruption.parquet` behind a
`RUN_EXACT` flag, so it is paid once. The cache also stores `num_time_noiso_*`, the same numerators
with isolated pairs excluded, for the sensitivity in §8.6.

Recommendation: build Route A as the always-available path, run Route B once, report Route B as the
headline and Route A vs B as a validation panel. The gap between them *is* a result — it measures
how much of the inequity comes from exposure versus from lack of redundancy.

### 5.1 What Route B actually found ✅

Measured cost came in at **15.9 min**, and Route B reproduces notebook 2's `average_time_disruption`
to **7.1 × 10⁻¹⁵ h**, which also proves the rebuilt demand matrix is identical to notebook 2's.

| | Q-I | Q-II | Q-III | Q-IV | Q-V |
|---|---|---|---|---|---|
| Route A share of PHL | 26.04 % | 15.10 % | 20.62 % | 20.14 % | 18.04 % |
| Route B share of PHL | 25.63 % | 15.13 % | 20.61 % | 20.13 % | 18.46 % |
| shift | −0.41 pp | +0.02 | −0.01 | −0.01 | +0.42 |
| **mean delay when a road fails** | **49.1 min** | 27.9 | 26.6 | 19.6 | **17.4 min** |

The two decompositions agree to within half a percentage point — so the equal-delay assumption is
close to harmless **at road level** — while the network-level delay gap is a factor of **2.8**
between Q-I and Q-V.

Those two facts are consistent, and together they locate the inequity: it is almost entirely an
**exposure** effect. Low-IDS districts depend on roads whose failure is expensive — long detours,
few alternatives, outright isolation — rather than being treated worse on the roads everyone
shares. That is the more actionable finding, because it points at redundancy in identifiable
corridors rather than at a diffuse gradient.

Two consequences. The expectation stated above — that Route A would understate low-quintile impact —
is not borne out; the (tiny) error runs the other way. And Route A is a sound approximation *for
this network*, usable when the cache is unavailable, but that is a property of this topology rather
than a theorem, so the check should be re-run on any other network.

---

## 6. Outputs

```text
intermediate_results/parquet/socioeconomic/od_quintile_flow.parquet     (cache, 6x6 x directed edge)
intermediate_results/parquet/socioeconomic/quintile_disruption.parquet  (cache, Route B)
intermediate_results/gpkg/travel_disruptions/socioeconomic_criticality.gpkg
    layer physical_by_quintile   (5 012 rows)
    layer directed_by_quintile   (9 764 rows — per-direction results)

figures/SPOF_PHL_by_IDS_quintile.png   5 panels phl_q1..phl_q5 + an IDS district panel, shared breaks
figures/SPOF_VHL_by_IDS_quintile.png   same for vhl
```

Equity shares, location quotients, the Route A vs B comparison, the dominant-quintile road counts
and the split by road class are printed as tables in section 11 rather than drawn as figures.

Column contract on `physical_by_quintile` (95 columns as built, both routes present ✅). Classes run `q1..q5` for IDS
quintiles I–V plus `qNA` for the unclassified residual:

```
identity     physical_edge_id NOMBRE CLASE ID_TRAMO ID_RUTA ADMIN road_length speed
published    total_aadt aadt_imputed pct_isolated pct_unaffected pct_delayed
             average_time_disruption average_dist_disruption phl vhl pkl
composition  flow_mod_q*  share_q*  aadt_q*  pct_aadt_q*
Route A      phl_q*  vhl_q*  pkl_q*
Route B      phl_exact_q*  vhl_exact_q*  pkl_exact_q*  beta_q*  delay_min_q*
derived      dominant_quintile  dominant_share  attribution_rule  headline_route  geometry
```

`delay_min_q*` is the quintile-specific mean delay in minutes — a diagnostic, not a total, and the
column that shows directly whether the low quintiles wait longer. Location quotients are printed in
section 11 of the notebook rather than stored, since they are network-level, not per road.

---

## 7. Reporting: never quote a raw quintile share

Because the quintiles are equal-count in districts but not in people (§2), report a **location
quotient** alongside every share:

```
LQ_q = (PHL borne by quintile q / total PHL) / (population in quintile q / total population)
```

`LQ_q > 1` = quintile q bears more disruption than its population share. That is the number that
supports an equity claim; the raw share is not.

---

## 8. Methodology review — what is sound, what is assumed, what breaks

**Sound.** The decomposition is exactly additive and reconciles to the published totals; the
district↔OD-node mapping is 1:1 with no areal interpolation; composition-from-model /
magnitude-from-observation is the standard hybrid and the gravity scale genuinely cancels; the
A→B/B→A treatment is verified against 1b's direction factor rather than assumed.

**Assumed, and it should be stated in the paper.**

1. **Trip production per capita is income-independent.** The gravity mass is population. Real trip
   rates and car ownership rise steeply with income, so a population-based model **overstates
   Q-I's share of vehicle flow and understates Q-V's**. Known sign, unknown magnitude. Optional
   fix: multiply origin production by an income-dependent trip rate — needs a source (ENAHO
   mobility, vehicle registry, or `INDICE_ECO` as a crude proxy) and would be a modelling choice
   worth its own defence.
2. **IDS is not income.** It is a five-dimension composite (economic, electoral participation,
   health, education, security). Claim "districts ranked by social development", never "income
   group". See the companion memo for what an income-share estimate would actually require.
3. **One population point per district.** Inherited from notebook 2, but it interacts badly here:
   the low-IDS districts are the large rural ones, so precisely the population whose equity we are
   measuring is the most spatially misplaced. Worth a sentence in Limitations.
4. **Route A's equal-delay assumption** (§5) — tested in §5.1 and found to hold for this network
   (shares move by <0.5 pp). Route B remains the headline because it is the estimator that does not
   need the assumption, not because the assumption failed.
5. **Freight is not population-driven.** `thl`/`tkl` should **not** be attributed to residential
   IDS quintiles with this demand model; a tonne-hour lost on a banana corridor is not borne by
   the adjacent district's residents. Recommend excluding tonnage from the socio-economic split
   and saying why, rather than producing a number that will be quoted.
6. **Isolation penalty.** Isolated pairs receive `2 × max baseline time`; those pairs are
   disproportionately remote and low-IDS, so the penalty choice directly moves the equity result.
   Report the equity numbers with and without isolated pairs.

**Breaks / do not do.** Do not cut fresh quintiles from `IDS_2023` (two districts carry 0.0 as a
missing-data code and would land in Q-I). Do not drop the unclassified 0.22 % silently. Do not sum
the directed layer and the physical layer in the same statistic — that is the one place where a
genuine double count can enter.

---

## 9. Notebook structure — `notebooks/2b_Socioeconomic_Criticality_CR.ipynb` (44 cells) ✅

```
 1  Purpose, inputs/outputs, the A->B/B->A method note   (markdown header)
 2  Imports, paths, constants, analysis switches         (ATTRIBUTION_RULE, RUN_EXACT, SPLIT_METRICS)
 3  Load saved criticality results                       — 5 012 / 9 764 rows, EPSG:8908 asserted
 4  Load IDS 2023, audit quintiles                       — 98 per class, the 2 IDS_2023 = 0.0 gaps
 5  Localities -> IDS: code join + spatial fallback      — join provenance reported
 6  Rebuild graph, snap, aggregate OD nodes              — 485 nodes, population preserved
 7  Quintile membership vectors per OD node              — 6 mixed nodes, population-weighted
 8  Baseline matrices + gravity demand                   — identical to notebook 2 §5, 0.4 s
 9  6x6 flow assignment (cached parquet)                 — the only slow step in Route A
10  Collapse to shares + attribution-rule sensitivity    — all four rules tabulated
11  Route A metrics: directed layer, then physical       — exact reconciliation asserted
12  Route B percolation (cached parquet, RUN_EXACT)      — reproduces notebook 2's averages
13  Maps: 5-panel PHL and VHL + IDS district context
14  Equity tables: shares, LQ, A vs B, by road class
15  Save gpkg (two layers) + verify round trip
16  Assumptions and limitations                          (markdown, mirrors §8 here)
```

### Headline result (Route B, verified clean run) ✅

| | Q-I | Q-II | Q-III | Q-IV | Q-V |
|---|---|---|---|---|---|
| Population share | 11.3 % | 14.4 % | 20.7 % | 28.7 % | 24.9 % |
| PHL share | 25.6 % | 15.1 % | 20.6 % | 20.1 % | 18.5 % |
| **Location quotient** | **2.27** | 1.05 | 0.99 | 0.70 | 0.74 |
| PKL location quotient | 1.86 | 1.66 | 0.99 | 0.75 | 0.53 |

The lowest IDS quintile bears **2.3× its population share** of passenger-hours lost; the two highest
quintiles bear about 0.7×. Both routes reconcile to the published totals — PHL 44 988 997,
VHL 12 241 203, PKL 579 062 287 — so these are a redistribution of notebook 2's numbers, not new
ones. By road class the gradient is steepest on Terciaria (Q-I 32.1 % of PHL) and flattest on
Primaria (24.2 %), i.e. it is the lower-order network that carries the inequity.
