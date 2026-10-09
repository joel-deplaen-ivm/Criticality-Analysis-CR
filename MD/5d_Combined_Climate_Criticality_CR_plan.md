# Plan: `5d_Combined_Climate_Criticality_CR` — combined climate-criticality index for Costa Rica

Source notebook: `notebooks/5d_Combined_Climate_Criticality.ipynb` (Serbia)
Target notebook: `notebooks/5d_Combined_Climate_Criticality_CR.ipynb` — **byte-identical to the
Serbia original today** (both md5 `787783f486ca16f1d7db2d2c283ce05d` ✅, 11 cells, kernel
`criticality_env`).
Upstream: [5a hazard criticality](5a_Main_Network_Hazard_Criticality_CR_plan.md),
[2b socioeconomic](2b_Socioeconomic_Criticality_CR_plan.md),
[5b flood scenarios](5b_Run_Flood_Scenarios_Accessibility_CR_plan.md),
[5c road impacts](5c_Plot_Flood_Scenarios_Accessibility_CR_plan.md)

Status: **built and run.** `notebooks/5d_Combined_Climate_Criticality_CR.ipynb` is **34 cells
(21 code) and executes top to bottom with 0 errors, 0 unexecuted cells and 5 figures** ✅,
replacing the byte-identical Serbia copy. Its own reconciliation cell prints `STATUS: COMPLETE`:
5,012 roads in, 5,012 out, nothing filtered. `utils/` and `src/` are untouched.

Outputs on disk ✅: `gpkg/travel_disruptions/combined_hazard_criticality.gpkg` (5,012 × 58,
EPSG:8908), `excel/Combined_Hazard_Criticality_CR.xlsx` (10 sheets), and five `*_CR.png` figures.

### Headline results ✅

| | |
|---|---|
| Roads scored | 5,012 (14,811 km), none dropped |
| High or Very High criticality | **1,267 (25.3 %)** |
| CC = 0 for a structural reason | **1,847 (36.9 %)** — no journey disrupted, no flood scenario |
| Spearman(CC, CC without A) | **0.934** — A is a tie-breaker, not a third pillar |
| Spearman(H, A) | **0.399** (Serbia 0.025) · Spearman(A, flood depth) **0.916** |
| Spearman(H, T) | **−0.075** (Serbia +0.085) — 5a's inverted-lift finding, carried into the index |
| **Equity headline** | on the top decile by CC, **Q-I districts bear 32.3 % of passenger hours lost against 11.2 % of population — a ratio of 2.87**; Q-V bears 12.7 % against 24.9 %, a ratio of 0.51. Monotone across all five quintiles, and steepening with criticality: Very High CC is 32 % Q-I roads, Very Low is 3 % |

The equity result is the payoff of [5a's D4 deferral](5a_Main_Network_Hazard_Criticality_CR_plan.md)
and has no Serbia counterpart. It is partly mechanical — Q-I holds fewer people, so per-capita
exposure runs high by construction — which is exactly why the population denominator is printed
beside every share.

**5d is now the last unadapted notebook in the CR pipeline.** 5c_CR was built and run on
2026-09-15 (18 cells, 0 errors, kernel `criticality2` ✅) and **delivers the A sub-index input that
this plan's first revision said was missing.** The revision below folds that in; §0.3, D6 and I2
are resolved, and §3.4 carries a correction.

Numbers marked ✅ were measured against the files on disk in `criticality2`, or read from a
notebook's own stored outputs, on 2026-09-15. Everything else is a proposal or an estimate and is
labelled as such.

### Verified upstream state ✅

| Notebook | State | Evidence |
|---|---|---|
| `5a_..._CR` | built, run | `main_network_hazard_criticality.gpkg`, layers `physical` (5,012 × 45) and `directed` (9,764 × 81) |
| `5b_..._CR` | built, run | 29 cells, 14 code, **0 errors, 0 unexecuted**, 5 figures on disk; own reconciliation cell prints `STATUS: COMPLETE`, 65 scenarios, 780 rows, 378 of 378 exposed roads partitioned |
| `5c_..._CR` | built, run | 18 cells, 12 code, **0 errors, 0 unexecuted**; `road_impacts.parquet` = 1,512 rows, `flood_scenario_impacts.gpkg` layer `road_impacts` |
| `5d_..._CR` | **byte-identical Serbia copy** | md5 `787783f486ca16f1d7db2d2c283ce05d`, identical to the Serbia notebook; stored outputs are a **Serbia** run (Windows paths `c:\Users\yma794\…\Criticality-Analysis-Roads-Serbia`, kernel `criticality_env`) |

The last row is the useful one: because 5d_CR still carries Serbia's own executed outputs, the
Serbia baseline for every quantity below can be read off without running anything. §2.5 uses it.

---

## 0. The three things that decide this notebook

Read these first; §1–§7 are the detail.

**0.1 The notebook cannot import its own first cell.** `utils/criticality_functions.py` imports
`xarray` and `damagescanner` at module level (lines 24–25), and neither is installed in
`criticality2` — `from utils.criticality_functions import score_climate_criticality` raises
`ModuleNotFoundError: No module named 'xarray'` ✅. `arcpy` and `rasterstats` are also absent ✅.
So cell 1 of the current CR copy fails before any data is read. This is the same wall 5a hit
([5a plan §4.0b, point 5](5a_Main_Network_Hazard_Criticality_CR_plan.md)).

**0.2 Five of the seven H metrics and five of the seven A metrics have no CR source.** This is
5a's issue I14, now the whole problem rather than a footnote. Measured against the CR files
(§2.1, §2.3): of the seven hazard metrics CR can supply **two**, of the seven accessibility metrics
**two**. `climate_hazards_only=True` — the notebook's default — selects a three-metric subset of
which CR has **one** (§3.1). Serbia's notebook does not fail on a missing metric; it fills it with
zeros and prints a warning (I4), so the shortfall is silent.

**0.3 The local-accessibility input now exists, in a different shape and a different place.**
*(Resolved since the first revision of this plan — it previously said the layer did not exist.)*
5c_CR delivers `parquet/flood_scenarios/road_impacts.parquet` — **1,512 rows = 378 roads × 2 origin
sets × 2 sectors**, long format, with `travel_time_impact` (hours), `impact_min`, `impact_class`
(Serbia's breaks) and `impact_class_cr` ✅. That replaces Serbia's **seven wide-format files under
`parquet/local_accessibility/`**, so every accessibility path in the Serbia notebook is wrong twice
over: wrong directory, and one long table instead of seven wide ones. 5c records this as its own
I3 and explicitly leaves the repointing to 5d.

Two conventions 5c set that 5d must honour rather than undo:

- **Measured-zero is kept, not dropped** (5c D5). 52 of the 378 roads have
  `travel_time_impact = 0.0` with `n_affected_origins = 0` under `loc`/hospitals ✅ — measured and
  genuinely zero. Serbia's `add_impact_column` reindexes and leaves unjoined roads as **NaN**, which
  `score_climate_criticality` then `fillna(0)`s, so a road measured at zero and a road never
  evaluated become indistinguishable. 5c went out of its way to keep them apart; 5d must not
  re-conflate them.
- **The origin set is a column, not a file** (5c D4), and the buffer axis was reported then dropped
  (`nobuf`). So 5d **selects** rather than reads, and that selection is a decision — see D3.

**Consequence.** 5d_CR is a **rewrite**, not an edit — the same conclusion 5a, 5b and 5c reached,
and for the same reasons. The Serbia notebook is 11 cells that are almost entirely calls into
`utils/criticality_functions.py`; every one of those functions is bound to Serbian column names.
Editing the 11 cells changes nothing useful while the functions underneath stay Serbian.

**What is different from the earlier revisions of this plan.** The upstream inputs are all present
and verified, and the six blocking method choices are answered (§5). Two of the answers simplify the
notebook considerably: taking 5a's `hazard_score` as H (D1 + D4) removes the entire per-metric
scoring stage for hazards, and with it `climate_hazards_only`, `H_all`/`H_climate`/`H_extended` and
the Excel "Extended" track. One answer adds an obligation rather than removing work: D7 accepts the
H/A circularity, so the notebook has to *explain* it with the three measured correlations rather
than design around it.

**The finding that arrived with the prototype** (§3.8) is that the A sub-index — the reason 5b and
5c exist — moves the final ranking by about 7 % of rank variance (Spearman(CC, CC-without-A) =
0.934 ✅). Everything downstream of that should be presented as an H×T ranking with A as a
tie-breaker, not as three co-equal pillars.

---

## 1. Assumptions baked into the Serbia original

Numbered A1–A18, following the convention of the 5a and 5b plans. Each has to be ported, replaced
or dropped.

### 1.1 Structure and identity

| # | Assumption | Where | Holds for CR? |
|---|---|---|---|
| A1 | `oznaka_deo` is the road-section identity, and the network must be **deduplicated down to it inside 5d**, before scoring | `clean_data`, `deduplicate_by_section` | **No.** CR's identity is `physical_edge_id`, and the collapse is already done upstream: `main_network_hazard_criticality.gpkg` layer `physical` is **5,012 rows with 0 duplicate keys** ✅. Re-running the dedup would double-aggregate, exactly as [5a A4](5a_Main_Network_Hazard_Criticality_CR_plan.md) records. Drop both functions. |
| A2 | Inputs are assembled by **spatial join** (`sjoin` + `groupby(level=0).first()` on the longest overlap), because the source tables share no key | `load_and_preprocess_criticality_data`, `add_impact_column` | **No — and this is a gain.** Every CR input is keyed on `physical_edge_id` and the key sets match exactly ✅ (5a, 2b and 5b all verified 1:1). Replace all nine sjoins with attribute merges. A heuristic disappears. |
| A3 | Rows shorter than 50 m that share an `oznaka_deo` are **dropped** as artefacts | `clean_data` | **Not applicable as written**, and needs a CR answer: **186 of 5,012 physical roads are under 50 m** ✅, minimum length 0.0000 km. None is a duplicate, so Serbia's rule would drop none of them — but a zero-length road is still a real data question that 5d should surface rather than inherit. See I6. |
| A4 | Output CRS is **EPSG:6316**, and results are mirrored to **parquet + File GDB + Excel + `.lyrx`** | `save_criticality_vector`, `save_climate_criticality_geospatial`, `save_lyrx_layer` | **No.** CR convention is a single GeoPackage in **EPSG:8908** under `intermediate_results/gpkg/<stage>/`. `arcpy` is not installed ✅, so the `.lyrx` path is dead regardless. `openpyxl` **is** present ✅, so the workbook is a live option (D8). |
| A5 | The notebook is **independent of the config file** and hardcodes its paths | cell 2 | **Ports unchanged** — it is already the CR convention (`CLAUDE.md`). |

### 1.2 The hazard sub-index (H)

| # | Assumption | Holds for CR? |
|---|---|---|
| A6 | Seven hazards exist and are commensurable: `flood_depth`, `future_rainfall_change`, `future_flood_change`, `max_pavement_temp`, `wildfire_susceptibility`, `landslide_exposure`, `snow_drift` | **No. CR has two of the seven** (§2.1). Snow, wildfire, pavement heat and both future-change layers have no CR source — the same finding as [5a A11–A16](5a_Main_Network_Hazard_Criticality_CR_plan.md), inherited here. |
| A7 | The climate subset — `future_rainfall_change`, `max_pavement_temp`, `landslide_exposure` — is the **default** for H (`climate_hazards_only=True`) | **Unusable.** CR has **one** of those three, and it is LHASA susceptibility — a static modelled propensity with no climate-change signal in it at all. H would be a single ordinal 0–5 column. §3.1, D1. |
| A8 | `landslide_exposure` is a **binary** flag derived from an observed-inventory date field (`datum_evid` non-null) | **No, twice over.** CR's landslide layer is *susceptibility*, not an inventory ([5a A12](5a_Main_Network_Hazard_Criticality_CR_plan.md)), and [5a D3](5a_Main_Network_Hazard_Criticality_CR_plan.md) settled that it enters **graded 0–5**, never binary. `prepare_metrics` would silently produce all-zeros on CR data: the column `landslide_date` does not exist. |
| A9 | `wildfire_susc` is collapsed to 0/1 by `.clip(0, 1)` | No CR raster; drop. The collapse is a poor pattern not to be copied ([5a A14](5a_Main_Network_Hazard_Criticality_CR_plan.md)). |
| A10 | `future_flood_change = 100 - future_flood_return_period`, i.e. a **change relative to a 100-year baseline** | **No CR source.** CR's `flood_aep` is a *present-day* exceedance probability, not a projected change — substituting it would relabel a baseline as a climate signal. D2. |
| A11 | Negative future changes are **clipped to zero** ("drier is not a risk driver") | Moot once A10 is dropped; but the reasoning is worth keeping on record — CR has no future-change axis to clip. |

### 1.3 Travel disruption (T) and local accessibility (A)

| # | Assumption | Holds for CR? |
|---|---|---|
| A12 | T = `phl + thl + pkl + tkl` convex scores | **Ports unchanged** — all four are present at physical level ✅. One consequence must travel with it: **1,989 of 5,012 roads have `phl = 0`** ✅, i.e. removing them changes no journey. T is exactly zero on 39.7 % of the network. |
| A13 | A is built from **seven sectors** — hospital, fire, police, factory, port, border, railway | **No.** CR has **two** (hospitals, EBAIS) and no source for the other five ([5b D4](5b_Run_Flood_Scenarios_Accessibility_CR_plan.md)). The EBAIS sector is additionally near-degenerate — 52 % of population sits at exactly 0 min from its nearest EBAIS ✅ ([5b §3.2](5b_Run_Flood_Scenarios_Accessibility_CR_plan.md)). |
| A14 | The A metrics are per-road **delays**, seven wide files under `parquet/local_accessibility/` | **Exists, in a different shape and place** — one long table under `parquet/flood_scenarios/` (§0.3). Repointing is mechanical; 5c's two conventions (keep measured zeros, origin set as a column) are not. |
| A15 | Every road has a meaningful A value | **No, and this is the sharpest structural finding.** Measured on 5c's real layer: A > 0 on **326 of 5,012 roads (6.5 %), 45 distinct values** under `loc`/hospitals ✅. A is a near-empty, near-constant column. §3.3. |
| A16 | H and A are **independent** inputs to a multiplicative index | **True in Serbia's default; the CR transposition breaks it.** *(Correction: the first revision of this plan said it was false in Serbia too. It is not.)* Serbia's default `climate_hazards_only=True` sets H = rainfall + pavement heat + landslide — **flood is not in it** — so H and A are genuinely near-independent there, and Serbia's own stored run measures **corr(H, A) = 0.025** ✅. CR has neither a rainfall-projection nor a heat layer, so **flood must enter H**, and A is non-zero only on flood-exposed roads. Measured on CR: **Spearman(A, flood_value) = 0.916** over all 5,012 roads ✅. The circularity is *created by the transposition*, not inherited. §3.4, D7. |

### 1.4 Scoring

| # | Assumption | Holds for CR? |
|---|---|---|
| A17 | Each metric is min-max normalised, then **quintile-ranked over its non-zero values only**, then convex-mapped `{1: 0.5, 2: 1, 3: 2, 4: 5, 5: 10}` | Mechanically portable, **substantively much worse in CR**, because the CR metrics differ enormously in how much of the network they are ranked over: landslide 99.8 %, Rx1month 98.9 %, PHL 60.3 %, flood depth 7.6 %, accessibility 6.5 % ✅. A "very high" flood quintile is the top fifth of 383 roads; a "very high" landslide quintile is the top fifth of 5,002. They are summed as if equal. §3.2, D4. |
| A18 | CC is **multiplicative**: `H × (T + A)`, optionally on min-max normalised sub-indices | Portable, but on CR data **1,843 of 5,012 roads (36.8 %) get CC = 0 through the `T + A` factor alone** ✅ — they are hazard-exposed but disrupt nothing. That is defensible ("criticality" genuinely is zero) but it has to be stated, because it means a third of the network lands in one class. §3.5. |

---

## 2. What CR actually has

### 2.1 Hazard metrics — the H inventory

Measured on `gpkg/travel_disruptions/main_network_hazard_criticality.gpkg`, layer `physical`
(5,012 roads, 14,811 km) ✅.

| Serbia metric | CR source | Coverage ✅ |
|---|---|---|
| `flood_depth` | `flood_value` (RP100 max depth, m) | 383 nonzero (7.6 %), 285 distinct, max **30.71 m** |
| `future_rainfall_change` | **none** — no CR projections | — |
| `future_flood_change` | **none** — `flood_aep` is baseline, not change (A10) | — |
| `max_pavement_temp` | **none** — no CR temperature raster | — |
| `wildfire_susceptibility` | **none** — no CR wildfire raster | — |
| `landslide_exposure` | `landslide_value` (LHASA 0–5, **graded** per 5a D3) | 5,002 nonzero (99.8 %), 5 distinct |
| `snow_drift` | **none** — no snow | — |
| — | `precip_rx1month_value` (20-yr return level, mm) | 4,955 nonzero (98.9 %), 2,756 distinct |
| — | `flood_aep` / `flood_min_rp` (exceedance probability) | 398 nonzero (7.9 %), **only 7 distinct values** |
| — | `n_water_crossings`, `has_temporary_structure` | 1,036 nonzero (20.7 %), 14 distinct |
| — | `hazard_score` (5a's own graded combination) | 5,003 nonzero, 78 distinct |
| — | `precip_anomaly_value` | present, but **5a §3.3 forbids its use as a hazard** — observed 2025 vs 2000–24, not a recurrence probability |

Also available and not in Serbia's list: `flood_band` (0–7), `landslide_band`, `rain_band`,
`flood_share_gt0p25`, `flood_depth_implausible`, `max_at_crossing`, `flood_correction_applied`.

### 2.2 Travel-disruption metrics — the T inventory

All four Serbia metrics present, 1:1 on `physical_edge_id` ✅: `phl`, `thl`, `pkl`, `tkl` — each
nonzero on **3,023 of 5,012** roads (60.3 %), ~2,510 distinct values each. `vhl`, `vkl`,
`pct_isolated` (130 roads nonzero ✅), `pct_delayed`, `average_time_disruption` also available.

### 2.3 Accessibility metrics — the A inventory

| Serbia metric | CR source |
|---|---|
| `hospital_delay` | **built** — 5c `road_impacts`, `sector == "hospitals"` ✅ |
| `fire_delay`, `police_delay`, `factory_delay`, `port_delay`, `border_delay`, `railway_delay` | **none** ✅ ([5b D4](5b_Run_Flood_Scenarios_Accessibility_CR_plan.md)) |
| — | `ebais_delay` — 5c `road_impacts`, `sector == "ebais"`, carrying the co-location caveat |

Measured on `road_impacts.parquet`, all four arms, 378 roads each ✅:

| origin_set | sector | roads with impact > 0 | measured zeros | distinct values | median | max |
|---|---|---|---|---|---|---|
| `loc` | hospitals | **326** | 52 | **45** | 2.19 h | 6.49 h |
| `loc` | ebais | 138 | 240 | 17 | 0.00 h | 6.97 h |
| `wp` | hospitals | **377** | 1 | **65** | 1.75 h | 6.15 h |
| `wp` | ebais | 359 | 19 | 58 | 4.63 h | 6.95 h |

**The origin set changes A's support by more than the sector does** — 326 vs 377 roads for
hospitals, 138 vs 359 for EBAIS. 5c flagged this as the largest sensitivity in its notebook and
made it a column rather than a choice; 5d is where the choice becomes unavoidable (D3).

Still on disk and still **not** usable as A: `parquet/local_accessibility/hospital_accessibility_results.parquet`
(62,053 WorldPop cells × baseline `travel_time_hosp`) and the EBAIS twin ✅ — baseline accessibility
per population cell, with no road attribution.

### 2.4 The Serbia baseline, read from 5d_CR's own stored outputs ✅

Because the CR copy is byte-identical and still carries Serbia's executed run, every headline can be
compared without running anything. This is the most useful single table in this document: it shows
which CR problems are new and which are inherited.

| Quantity | Serbia (stored run) ✅ | CR (projected from the inputs) ✅ |
|---|---|---|
| Sections scored | 1,746 (from 3,154 rows, after dedup) | **5,012**, no dedup needed |
| Rows lost to a null section id | **801 of 3,154 (25.4 %)** | **0** — `physical_edge_id` is complete |
| H composition | 3 climate metrics, all populated | **1 of those 3 available** (§3.1) |
| A composition | 7 sectors | **2** (hospitals, EBAIS) |
| **A = "No criticality"** | **1,014 of 1,746 (58.1 %)** | **4,686 of 5,012 (93.5 %)** |
| **CC = "No criticality"** | **73 of 1,746 (4.2 %)** | **1,843 of 5,012 (36.8 %)** |
| corr(H, A) | **0.025** | **0.916** on Spearman(A, flood) (§3.4) |
| corr(H, T) / corr(T, A) | 0.085 / −0.072 | not yet computed |
| H / T / A observed max | 22 / 40 / 57 | ceilings 30 / 40 / **20** (§3.7) |
| CC class shares | 19.4 / 18.9 / 19.1 / 19.2 / 19.2 % — near-uniform | near-uniform by construction (I11) |
| `.lyrx` output | **not generated** — "arcpy could not be imported" printed 4× | same, and `arcpy` is absent here too ✅ |

Three readings. **(a)** Serbia's A was already sparse at 58 % zero — CR's 93.5 % is the same defect
an order of magnitude worse, not a new one. **(b)** Serbia's near-zero sub-index correlations are
what make a multiplicative index meaningful; CR's 0.916 is what breaks it. **(c)** Serbia never
produced the `.lyrx` layers either, so dropping that path costs nothing real.

### 2.5 Where Serbia's A actually comes from — traced ✅

Worth recording, because the name `_ACCESSIBILITY_METRICS` suggests the baseline accessibility
notebooks (3a–3e) and it is **not** those. Serbia's A is the flood-scenario accessibility loss:

1. **`src/5b_Run_Flood_Scenarios_Accessibility.py`** — per HydroBASINS lev09 basin, delete the
   flood-exposed edges, recompute OD from population points to that sector's sinks, store per-origin
   `Delta = new_tt - old_tt` (hours). Pickled per sector to
   `accessibility_analysis/<sector>_criticality_results/save_new_results_SRB_basins.pkl` — five runs
   (healthcare, police, fire, factory, allagri).
2. **`notebooks/5c`** — `calculate_service_criticality` (hospital, police, fire, factory) and
   `calculate_agri_criticality(delta_prefix="delta_nearest")` (road, port, rail) assign each basin's
   **mean positive Delta** to every edge removed in that basin, keep `exposed` edges with
   `>= 0.167 h`, bin `impact_class`, and `save_impact_layers` writes the seven `*_impacts.parquet`.
3. **`notebooks/5d`** — `add_impact_column` attaches each as `<sector>_delay`; the seven become A.

**This is the root of §3.4.** A was *always* flood-conditional, in both countries. Serbia's default
simply never put flood in H, so the dependence never showed up in its correlation matrix.

**Three findings that bear on the CR metric's semantics:**

**(a) Serbia treats unreachability three different ways across the seven metrics** ✅:

| Metrics | An unreachable origin becomes |
|---|---|
| factory | **12 h**, substituted before averaging over sinks (`get_average_access_time:50`) |
| hospital, police, fire | `inf`, then **replaced by 1 h** (`calculate_service_criticality:1673`) |
| road, port, rail | `inf`, then **dropped** from the mean (`calculate_agri_criticality:1845`) |

Three conventions summed into one sub-index, with no note anywhere that they differ.

**(b) The 1 h substitution inverts the severity ordering** ✅. `get_distance_to_nearest_facility`
leaves unreachable origins at `inf`, so `Delta = inf`; `inf > 0` passes the filter and
`.replace([np.inf, -np.inf], 1)` turns it into **1 hour**. An origin cut off entirely therefore
contributes *less* to the basin mean than one that merely lost two hours.

**CR's 5c chose the opposite convention** — isolated origins are charged the 7 h penalty, which is
why 31.8 % of affected rows sit at the ceiling (I5b). So **Serbia's A is deflated by isolation and
CR's is inflated by it.** They are not the same quantity. CR's is the more defensible of the two,
and the D7 explanation must say this rather than implying continuity with Serbia.

**(c) `add_impact_column` is a spatial join, not a key join** ✅ —
`base_gdf.sjoin(edges, predicate="intersects")` then `groupby(index).mean()`, so each road takes the
mean impact of every impact-layer edge intersecting it. It has to be spatial: the impact layers are
keyed on `osm_id` and carry `highway`, while 5d's frame is keyed on `oznaka_deo`. CR needs none of
it — `physical_edge_id` joins 1:1 (A2).

### 2.6 The socioeconomic layer — new, with no Serbia counterpart

`gpkg/travel_disruptions/socioeconomic_criticality.gpkg`, layer `physical_by_quintile`, 5,012 rows
× 95 columns, key set identical to the hazard-criticality layer ✅. Carries `share_q1…q5`,
`phl_q1…q5`, `vhl_q*`, `pkl_q*`, `delay_min_q*`, `dominant_quintile` (1,989 `none`, then q4 812,
q1 596, q5 578, q2 527, q3 510 ✅) and `attribution_rule`.

[5a D4](5a_Main_Network_Hazard_Criticality_CR_plan.md) **moved the IDS quintile crossing out of 5a
and into 5d.** This is therefore a required new section of 5d_CR, with nothing in the Serbia
notebook to port from. §4.6.

---

## 3. Measured problems with a literal transposition

These are the reasons 5d needs decisions rather than a column rename.

### 3.1 `climate_hazards_only=True` cannot be honoured ✅

The notebook's default builds H from `future_rainfall_change + max_pavement_temp +
landslide_exposure`. CR has **one** of those three, and LHASA susceptibility carries no
climate-change signal — it is a static geomorphological propensity. Under the Serbia default, CR's
H would be a single ordinal 0–5 column quintile-ranked over 5,002 roads, and the notebook would
still print "climate criticality".

The setting is not merely unavailable; keeping the name while changing the content would be the
worst outcome. **D1 must resolve what "climate" means in the CR index, or drop the word.**

### 3.2 Quintile scoring over non-zero values makes sparse and dense metrics incommensurable ✅

`_quintile_score` ranks only the non-zero entries, so the *population* each metric is ranked over
differs by more than an order of magnitude:

| Metric | Roads entering the ranking | Share of 5,012 | Distinct non-zero values |
|---|---|---|---|
| `landslide_value` | 5,002 | 99.8 % | **5** |
| `precip_rx1month_value` | 4,955 | 98.9 % | 2,756 |
| `phl` / `thl` / `pkl` / `tkl` | 3,023 | 60.3 % | ~2,510 |
| `n_water_crossings` | 1,036 | 20.7 % | 14 |
| `flood_aep` | 398 | 7.9 % | **7** |
| `flood_value` | 383 | 7.6 % | 285 |
| `A` (hospitals, reconstructed) | 326 | 6.5 % | **44** |

Two distinct failures fall out of this, and they compound:

1. **The convex score means different things per metric.** A road scoring 10 on flood is in the top
   fifth of 383 roads (1.5 % of the network); a road scoring 10 on landslide is in the top fifth of
   5,002 (20 %). They are then added together as equal contributions.
2. **Metrics with few distinct values cannot be quintiled at all.** `landslide_value` has 5 values
   and `flood_aep` has 7 ✅ — `rank(pct=True)` on heavy ties puts whole tied blocks in one bin, so
   the quintile cuts are determined by tie structure, not by the distribution.

This is [5a A17–A18](5a_Main_Network_Hazard_Criticality_CR_plan.md) reappearing one step
downstream: 5a replaced the equal-weight hazard count with a graded `hazard_score` for exactly this
reason, and 5d would re-introduce the problem unless D4 addresses it.

### 3.3 The A sub-index is nearly empty and nearly constant ✅

Measured on 5c's delivered layer (§2.3), `loc`/hospitals: A > 0 on **326 of 5,012 roads (6.5 %)**
carrying **45 distinct values** ✅.

Four things follow. **(a)** 93.5 % of roads get A = 0, and that zero means three different things —
*never in a scenario* (4,634 roads), *in a scenario, measured, genuinely zero* (52 roads ✅), and
*not flood-exposed so structurally ineligible*. 5c kept the second apart from the first (D5); 5d
must not merge them back. **(b)** Because the delay is a *basin* mean, every road in a basin shares
one value: 326 roads carry 45 numbers. A is a basin attribute wearing a road's clothes — 5c says so
in its own header. **(c)** The EBAIS arm is close to unusable under `loc` — 17 values over 138
roads, magnitudes pressed against the 7 h isolation penalty (max 6.97 h ✅), so it measures the
penalty constant more than it measures travel time. **(d)** 5c states that **31.8 % of affected
origin-rows are isolated and charged the 7 h penalty**, so the metric's median (138.6 min under
`loc`/hospitals) is substantially a function of `ISOLATION_PENALTY_FACTOR`, not of road geometry.
Whatever 5d does with A, that sentence has to appear beside it.

### 3.4 The CR transposition makes H and A circular — Serbia's default does not ✅

*This section corrects the first revision of this plan, which asserted the circularity was present
in Serbia too and merely undocumented. It is not: Serbia's default excludes flood from H.*

A is non-zero only on roads that appear in a flood scenario, and a road appears only if
`flood_depth_rp100 > 0.25 m`. All 378 scenario roads are flood-exposed by construction ✅.

- **Serbia escapes this by accident of its data richness.** `_HAZARD_CLIMATE_METRICS` is
  `["future_rainfall_change", "max_pavement_temp", "landslide_exposure"]` — **no flood**. Under the
  notebook's default `climate_hazards_only=True`, H and A share no input, and Serbia's own run
  measures **corr(H, A) = 0.025** ✅. The circularity is latent there, and would only surface with
  `climate_hazards_only=False`, which Serbia does not use for its headline.
- **CR cannot escape it**, because flood is one of only two real CR hazards (§2.1). Put flood in H
  and the A term becomes conditional on H's own flood component. Measured:
  **Spearman(A, flood_value) = 0.916** across all 5,012 roads ✅.

So `CC = H × (T + A)` in CR is not "hazard × general consequence" but **"hazard × (national
disruption + flood-conditional local consequence)"** — and the flood part of H is multiplying a term
that exists only where flood does. D7 decides whether to accept, decouple, or drop A.

The honest framing if D7 accepts it: A is not a second, independent consequence channel. It is a
*flood-specific* consequence channel, and CC is closer to a flood-weighted index than its name
suggests.

### 3.5 A third of the network is driven to zero by the `T + A` factor ✅

1,843 of 5,012 roads (36.8 %) have `phl = 0` **and** no A value — removing them changes no journey
and they were in no scenario. Multiplicatively, CC = 0 for all of them regardless of hazard
exposure, and `_classify` puts them in one bucket, "No criticality". Only **3,169 roads (63.2 %)**
have any non-zero CC support at all ✅.

A further 146 roads have A > 0 but T = 0 ✅ — flood-scenario roads that disrupt no national travel.

This is arguably correct behaviour, not a bug. But a class map in which 37 % of roads share one
colour for a structural reason needs that reason in its caption.

### 3.6 With two sectors instead of seven, `normalize_subindices` stops being cosmetic ✅

Each metric's convex score tops out at 10, so a sub-index's ceiling is 10 × its metric count:

| | Serbia | CR |
|---|---|---|
| H ceiling | 30 (3 climate metrics), **22 observed** ✅ | 30 (flood + landslide + rain) |
| T ceiling | 40 (4 metrics), **40 observed** ✅ | 40 — unchanged |
| A ceiling | 70 (7 sectors), **57 observed** ✅ | **20** (2 sectors), or **10** if D3 takes hospitals only |

In the **raw** variant, `CC = H × (T + A)`, A can contribute at most a quarter of T's weight in CR
against roughly one and a half times T's in Serbia — so dropping from seven sectors to two silently
demotes local accessibility from the dominant consequence term to a rounding correction.

In the **normalised** variant, `norm(H) × (norm(T) + norm(A))`, A is rescaled to [0, 1] and given
parity with T. But min-max normalising a column that is zero on 93.5 % of roads (§3.3) stretches 45
distinct values across the full range, so **326 roads inherit the same weight that 1,746 roads carry
in Serbia**.

Neither variant is neutral, and they fail in opposite directions. D5 was listed as a cosmetic
"run both" in the first revision of this plan; on these numbers it is a substantive choice about how
much weight two health sectors should carry, and it must be argued rather than defaulted.

### 3.7 The 4a/5a numbers that must travel into 5d

These are inherited caveats, already recorded upstream, that become *properties of the index* here:

- **Flood depth is length-biased** — `max` reduction means the median flood-exposed edge is wet on
  only 13.9 % of its length ✅ ([5a §3.1](5a_Main_Network_Hazard_Criticality_CR_plan.md)), and the
  30.71 m maximum is a river cross-section. That value enters H's top quintile.
- **`flood_min_rp` is highly skewed** — 86 % of ever-flooded edges first flood at RP10 ✅
  ([5a I18](5a_Main_Network_Hazard_Criticality_CR_plan.md)), which is why `flood_aep` has 7 distinct
  values and cannot be quintiled.
- **Exposure is not impact** ([5a A21](5a_Main_Network_Hazard_Criticality_CR_plan.md)). No fragility
  curve, no closure probability. CC is a **hazard-screened criticality score**, not a risk estimate.
- **The 0.25 m threshold is inherited from Serbia, not derived** ([5a I6](5a_Main_Network_Hazard_Criticality_CR_plan.md)).

---

### 3.8 Prototype under the settled decisions — three findings ✅

Scored once, outside the notebook, with the §5 decisions applied: H = `hazard_score`,
T = convex quintiles of log1p(`phl`,`thl`,`pkl`,`tkl`), A = convex quintiles of log1p(hospital,
EBAIS), `CC = norm(H) × (norm(T) + norm(A))`. Measured on all 5,012 roads ✅.

**(1) `norm(H)` is an identity.** `hazard_score` already spans exactly [0, 1] (min 0.000, max
1.000 ✅), so min-max normalising it changes nothing. D1+D4 therefore remove a whole scoring stage
rather than replacing it, and H needs no support caveat because it never enters a quintile.

**(2) The A sub-index barely moves the index it was built for.** Dropping A entirely and scoring
`CC = norm(H) × norm(T)`:

| Arm | Spearman(CC, CC without A) | Top-100 overlap |
|---|---|---|
| `loc` | **0.934** | 79 / 100 |
| `wp` | **0.895** | 69 / 100 |

Two notebooks (5b, 5c) and four configuration arms exist to produce A, and it accounts for roughly
7 % of the rank variance in the final index under `loc`. That is not an argument for deleting it —
it is the only health-access channel in the whole pipeline, and the 21 roads it moves in and out of
the top 100 may be the interesting ones — but it must not be presented as a co-equal third pillar
of CC. It is a tie-breaker on a mostly H×T ranking.

**(3) The origin-set choice (D3b) is nearly immaterial to CC, and it is `wp` that makes the
circularity near-total.**

| | `loc` | `wp` |
|---|---|---|
| Hospitals: roads > 0 / distinct values | 326 / 44 | **377 / 64** |
| EBAIS: roads > 0 / distinct values | 138 / 16 | **359 / 57** |
| A zeros | 93.5 % | 92.5 % |
| **Spearman(A, `flood_value`)** | 0.916 | **0.991** |
| Spearman(H, A) | 0.399 | 0.433 |

and between the two arms: **Spearman(CC_loc, CC_wp) = 0.972**, top-500 overlap 432/500, **5.9 % of
roads change CC class** ✅.

So the axis 5c called its largest sensitivity, and which §2.3 of this plan called "a real trade",
survives into CC as a 3 % rank perturbation. The reason is finding (2): A is too weak a term for
its own internal spread to matter. Worth stating plainly, because it retires a question that looked
blocking.

Note the direction of the circularity: `wp` gives A more support (377 of 378 roads non-zero) and
thereby makes A almost exactly the indicator function of flood exposure — **0.991** ✅. The arm that
looks better on coverage is the arm that is worse on independence.

**Class distribution under the settled decisions, `loc` arm** ✅: No criticality 1,847 (36.9 %),
then 633 / 632 / 633 / 634 / 633 across Very Low → Very High — near-uniform by construction (I11),
and matching §3.5's predicted 1,843 to within the 9 roads that have `hazard_score = 0`.

## 4. The plan

### 4.1 Shape

A rewrite in the idiom of 4a / 5a / 5b: markdown header cell listing exact inputs, outputs, steps
and caveats (per `CLAUDE.md`); hardcoded paths near the top; `BASE_DIR = Path.cwd().parent`; CR
logic in the notebook (or `src/network_preparation_cr.py` if reused), **never** in `utils/`.

```
 1  markdown header: inputs, outputs, steps, the A21 framing sentence, and an
    explicit statement of which Serbia metrics have no CR source (§2.1, §2.3)
 2  imports + paths + constants (WORKING_EPSG=8908, metric lists, CONVEX_MAP)
 3  load the four CR inputs; assert 1:1 on physical_edge_id; assert EPSG:8908
 4  read 5c's road_impacts, select one origin_set (D3b), pivot wide on sector;
    keep n_affected_origins + a_evaluated so measured-zero stays distinct
 5  assemble the metric frame by attribute merge -- no sjoin (A2)
 6  print the metric-support table of §3.2 BEFORE scoring, so sparsity is
    visible at the point the scoring assumption is made
 7  score: normalise -> rank -> convex -> H / T / A -> CC -> classify
 8  sensitivity: CC under each D1/D4/D5 variant, side by side (§4.5)
 9  maps: 3-panel H/T/A + combined CC (EPSG:8908, Web Mercator basemap only)
10  IDS quintile crossing -- the 5a D4 deferral (§4.6)
11  statistics, by CLASE rather than kategorija
12  write gpkg (+ workbook if D8 says so)
13  reconciliation: rows in / rows out / roads with CC = 0 and why
```

No `deduplicate_by_section`, no `clean_data`, no `.lyrx`, no File GDB (A1, A3, A4).

### 4.2 Inputs

| File | Layer / key | Gives |
|---|---|---|
| `gpkg/travel_disruptions/main_network_hazard_criticality.gpkg` | `physical`, `physical_edge_id` | H metrics **and** T metrics — 5a already joined them ✅ |
| `gpkg/travel_disruptions/socioeconomic_criticality.gpkg` | `physical_by_quintile`, `physical_edge_id` | the IDS attribution for §4.6 |
| `parquet/flood_scenarios/road_impacts.parquet` | `physical_edge_id` + `origin_set` + `sector` | **the A metrics, ready-made by 5c** — 1,512 rows, long format ✅ |

Three files, three attribute merges, no spatial join anywhere. One read of 5a's `physical` layer
supplies both H and T because 5a already did that join; Serbia needs two files and an sjoin for the
same thing. `origins_affected.parquet` and `scenario_edges.parquet` are **no longer needed by 5d** —
5c consumed them.

Pivot `road_impacts` to wide on `sector` after filtering to one `origin_set` (D3), and **left-join
onto all 5,012 roads, then fill with 0.0 — not NaN** (§0.3): the 52 measured zeros and the 4,634
never-evaluated roads both end at 0.0 in the score, but they must be distinguishable in the saved
layer, so carry `n_affected_origins` and an explicit `a_evaluated` boolean through to the output.

### 4.3 Metric lists to define in the notebook

Settled per §5:

```python
HAZARD_METRICS      = ["flood_value", "landslide_value", "precip_rx1month_value"]
HAZARD_FLOOD_ONLY   = ["flood_value"]                    # the D1 "climate" candidate
TRAVEL_METRICS      = ["phl", "thl", "pkl", "tkl"]       # unchanged from Serbia
ACCESS_METRICS      = ["hospital_delay", "ebais_delay"]   # D3a: both sectors
LOG_TRANSFORM       = ACCESS_METRICS + TRAVEL_METRICS      # H bypasses scoring entirely (D1/D4)
ORIGIN_SET          = "loc"    # D3b; "wp" is the reported variant
```

**H is not in these lists.** Under D1 + D4, H = `hazard_score` straight from 5a — already the mean
of three band-normalised ordinals, already spanning [0, 1] ✅. No log transform, no min-max, no
quintile, no convex map. The three band columns come along as reported context only.

So `CONVEX_MAP` now applies to **six** metrics (4 travel + 2 access), against Serbia's eighteen.
Every one of the six must be named in the header cell with its unit and its **support**, and the
header must say plainly that H was scored by a different mechanism from T and A — that asymmetry is
the direct consequence of D4 and it is not self-evident from the output.

### 4.4 Consuming 5c's A layer

*(This section previously described building the A layer from scratch. 5c does that now; D6 is
resolved.)* 5d **reads** `road_impacts.parquet` and does not re-derive anything. What it still owes:

- **Select one `origin_set`** (D3) and say which, in the header, in the column name or a stamped
  column, and in every caption. 5c deliberately refused to choose.
- **Do not re-apply Serbia's `>= 0.167 h` (10 min) cut.** 5c moved that filter to plot time
  precisely so the scoring input is unfiltered; re-imposing it would drop 52 measured zeros plus
  every sub-10-minute road back into the NaN hole 5c dug them out of.
- **Do not use `impact_class` / `impact_class_cr` as scoring inputs.** They are presentation bins;
  5c carries two of them because Serbia's breaks put 73 % of CR roads in one class ✅.
- **Carry `metric_definition` through to the output.** 5c stamps every row with the sentence
  describing what `travel_time_impact` contains; that sentence is the only defence against the
  metric being read as an ordinary travel time (§3.3d).

### 4.5 Sensitivity — what is still worth varying

Serbia exposed `climate_hazards_only` and `normalize_subindices` as switches. **D1 deletes the
first and D5 fixes the second**, so the Serbia sensitivity pair is gone. What remains worth
reporting, on §3.8's evidence:

| Variant | Why | Measured already ✅ |
|---|---|---|
| **A dropped** — `CC = norm(H) × norm(T)` | the single most informative comparison in the notebook: it shows how much the health-access channel actually contributes | Spearman 0.934, top-100 overlap 79/100 |
| **`wp` instead of `loc`** (D3b) | the axis 5c called its largest sensitivity; shows it does not survive into CC | Spearman 0.972, 5.9 % of roads change class |
| **raw instead of normalised** (D5) | shows what the 2-sector ceiling does when A is not rescaled (§3.6) | not yet run |

Report Spearman rank correlation and top-100 / top-500 overlap for each, as §3.8 does. The first
two are already measured, so the notebook is confirming numbers rather than discovering them —
say so rather than presenting them as fresh findings.

**Not worth varying:** H's composition. D1 fixed it to `hazard_score`, and 5a already published the
per-layer selectivity behind each band, so re-litigating it in 5d would duplicate 5a §4.5.

### 4.6 The IDS quintile crossing (the 5a D4 deferral)

New section, no Serbia counterpart. Join `socioeconomic_criticality.gpkg` on `physical_edge_id`
(key sets verified identical ✅) and cross the CC classes with the quintile attribution:

- CC class × `dominant_quintile`, with the **1,989 `none` roads shown, not dropped** ✅;
- for the top CC decile, the `share_q1…q5` profile — whose journeys are on the most critical roads;
- `phl_q*` summed over hazard-exposed roads, i.e. hours lost by quintile on roads that also sit in a
  hazard footprint — the equity headline 5a deferred to here.

Two rules inherited from 2b: **every quintile share is printed against its population share**
(quintiles are equal-count in districts, not in people — Q-I is 11.3 % of population, Q-V 24.9 % ✅),
and IDS is a **development ranking, not an income measure**
([district_income_shares_CR.md](district_income_shares_CR.md)).

### 4.7 Figures → `figures/`

| Serbia | CR |
|---|---|
| `criticality_analysis_3panel.png` (H/T/A) | kept — but the A panel needs a caption saying it is non-zero on 6.5 % of roads ✅ |
| `climate_criticality_mean.png` | kept, renamed if D1 drops the word "climate" |
| — | **new**: metric-support chart (§3.2) — what each convex score was ranked over |
| — | **new**: variant-comparison figure (§4.5) |
| — | **new**: CC × IDS quintile (§4.6) |

EPSG:8908 throughout; Web Mercator only for basemap tiles.

### 4.8 Outputs

`intermediate_results/gpkg/travel_disruptions/combined_climate_criticality.gpkg`, EPSG:8908, one
layer, **all 5,012 physical roads retained** — no filtering, per [5a A20](5a_Main_Network_Hazard_Criticality_CR_plan.md).

No File GDB, no `.lyrx` (`arcpy` absent ✅), no parquet mirror. The Excel workbook is D8.

### 4.9 The framing sentence

Same as 5a §4.10 and 5b §4.8, and it belongs in the header cell: **this is not risk.** CC is a
hazard-screened criticality score. There is no fragility curve, no closure probability, no expected
annual loss.

Per **D1 the word "climate" is dropped**: the index is **combined hazard criticality**, because
every CR hazard in it is present-day (RP-based flood frequency, static landslide susceptibility, an
observed rainfall return level) and CR has no climate-projection data at all
([5a A16](5a_Main_Network_Hazard_Criticality_CR_plan.md)). The filename keeps its `5d_Combined_Climate_Criticality_CR`
stem for pipeline continuity; the title, header and every figure caption say *hazard*.

Per **D7** the header must also carry the circularity, in plain words: **A is not an independent
third channel.** It is non-zero only on roads a flood scenario removed, so it is a flood-conditional
consequence term sitting beside a hazard index that already contains flood. The three numbers to
print: Spearman(A, flood) = 0.916, Spearman(H, A) = 0.399, and Serbia's corr(H, A) = 0.025 for
contrast ✅. And per §3.8, CC is an H×T ranking that A adjusts at the margin — Spearman(CC,
CC-without-A) = 0.934 ✅ — not a three-pillar composite.

---

## 5. Decisions — settled 2026-09-15

These are the transposition choices. Per `CLAUDE.md` they are research decisions, not implementation
details — each changes what the index measures, not just how it is coded.

**All six blocking decisions are now answered.** D1, D3a, D4, D5 and D7 were chosen by the user on
2026-09-15; D6 was resolved by 5c being built; D3b is recorded below as an assumed default (✔A) on
the strength of §3.8, which measured it to be nearly immaterial. D2, D8 and D9 keep the defaults
this plan proposed. **Nothing blocks the build.**

Following the 5b/5c convention: **✔R** = the user chose it; **✔A** = I picked the default, recorded
here and at the line in the notebook where it takes effect.

| # | Decision | Status |
|---|---|---|
| **D1** | **H is the overall hazard score over flood + landslide + rainfall, built from 5a's per-layer bands.** In practice that is 5a's existing `hazard_score` column used directly: `(flood_band/7 + landslide_band/5 + rain_band/3) / 3`, which is *exactly* this definition and which 5a's own output cell already labels "carried forward for 5d". **The word "climate" is dropped** — the index is *combined hazard criticality*, and the notebook is renamed in its title and header (the filename stays for pipeline continuity). **Consequences:** no per-metric quintile scoring for H at all; `climate_hazards_only` disappears as a switch rather than being reinterpreted; `H_all` / `H_climate` / `H_extended` and the whole "Overview Extended" Excel track go with it (D8). And because `hazard_score` already spans [0, 1] ✅, `norm(H)` is an identity (§3.8 finding 1). | ✔R |
| **D2** | **`flood_aep` does not substitute for `future_flood_change`.** The slot stays empty; `flood_aep` and `flood_min_rp` are carried as reported columns, never as a projected change (A10). Moot in practice now that D1 takes `hazard_score`, whose flood term is `flood_band` — itself derived from `flood_min_rp`. | ✔A |
| **D3a** | **A carries both sectors — hospitals and EBAIS.** Ceiling 20 (2 × 10). **Consequence to carry:** under the `loc` arm EBAIS is non-zero on only 138 roads with 16 distinct values ✅ and is pressed against the 7 h isolation penalty, so it contributes little and what it does contribute is substantially the penalty constant (I5b). Every EBAIS number keeps the co-location caveat from [5b §3.2](5b_Run_Flood_Scenarios_Accessibility_CR_plan.md). | ✔R |
| **D3b** | **`loc` (the 493 localities) feeds A**, with `wp` reported as a variant. **Why assumed rather than asked:** §3.8 measured the choice to be nearly immaterial to the final index — Spearman(CC_loc, CC_wp) = **0.972**, top-500 overlap 432/500, 5.9 % of roads change class ✅ — while `loc` is the only arm carrying `CÓDIGO_DTA`, which §4.6's IDS quintile crossing *requires* ([5b I5](5b_Run_Flood_Scenarios_Accessibility_CR_plan.md)), and it is the reporting default of notebooks 2, 2b, 5b and 5c. `loc` also has the **less** extreme circularity (0.916 vs `wp`'s 0.991 ✅). **Reversible in one constant** (`ORIGIN_SET`). Say the word and it flips. | ✔A |
| **D4** | **5a's per-layer bands, not re-quintiling** — same answer as D1, and for the hazard metrics the two are the same decision. `flood_band` (0–7 by exceedance frequency), `landslide_band` (LHASA 0–5 ordinal), `rain_band` (0–3) each normalised by their own maximum and averaged. **This retires §3.2 for H entirely**: no hazard metric is ever ranked over its non-zero subset, so the 7.6 %-vs-99.8 % support problem cannot arise there. **It does not retire §3.2 for T and A**, which have no 5a bands and keep Serbia's quintile + convex treatment — defensible for T (60.3 % support, ~2,510 distinct values), the weakest link for A (6.5 %, 45 values). That asymmetry must be stated in the header. | ✔R |
| **D5** | **Normalised: `CC = norm(H) × (norm(T) + norm(A))`.** A is min-max normalised to [0, 1] and so carries parity with T despite having two metrics against T's four. **Consequence:** 326 non-zero roads are stretched across the full range, so A's few values carry the weight 1,746 roads carry in Serbia (§3.6). Mitigated, not removed, by §3.8 finding 2 — A moves the index little either way. `norm(H)` is an identity under D1, so the normalisation acts only on T and A. | ✔R |
| **D6** | **Resolved by 5c_CR**, built and run 2026-09-15 — `road_impacts.parquet`, 1,512 rows ✅. 5d reads it and derives nothing (§4.4). | ✔ |
| **D7** | **The H/A circularity is accepted and explained, not engineered away.** No hazard-independent SPOF pass; 5d stays a pure consumer. **What must be explained, in the header cell and beside every A figure:** A is non-zero only on roads that a flood scenario removed, so it is not an independent third consequence channel but a **flood-conditional** one. Measured: Spearman(A, `flood_value`) = **0.916**, Spearman(H, A) = **0.399** ✅, against Serbia's corr(H, A) = 0.025 ✅ — the dependence is introduced by the CR transposition, because CR must put flood in H where Serbia's default did not (§3.4). So CC is closer to a flood-weighted H × T ranking than its name suggests, and §3.8 finding 2 quantifies how little A adds on top: Spearman(CC, CC-without-A) = 0.934 ✅. State all three numbers; do not present H, T and A as co-equal pillars. **And state §2.5(b):** Serbia's A *deflates* isolation (unreachable origins scored as 1 h) while CR's *inflates* it (charged the 7 h penalty), so the two countries' A are not the same quantity and CR's must not be presented as continuous with Serbia's. | ✔R |
| **D8** | **Keep the Excel workbook**, with CR column lists replacing `_EXCEL_ID_COLS` / `_DESC_*`. The "Extended" sheets go away with D1 (there is no second hazard track any more). The Metric Descriptions sheet is where the D7 explanation, the A21 framing and §3.2's support asymmetry must be unavoidable. No GDB, no `.lyrx` (`arcpy` absent ✅, and Serbia never produced them either — I15). | ✔A |
| **D9** | **`CONVEX_MAP` kept** at `{1: 0.5, 2: 1, 3: 2, 4: 5, 5: 10}` for T and A. Now applies to **six** metrics instead of Serbia's eighteen, since H bypasses it. The notebook states the convexity choice in one sentence and **does not repeat Serbia's docstring error** (it says Q1 = 0 where the code gives 0.5). | ✔A |

🚧 nothing blocks the build · ✔R user's choice · ✔A assumed default, reversible

---

## 6. Issues

### 6.1 Blocking

| # | Issue |
|---|---|
| ~~**I1**~~ | ~~`utils/criticality_functions.py` cannot be imported in `criticality2`~~ — **Resolved by rewriting in the notebook**, as 5a, 5b and 5c did. 5d_CR imports nothing from `utils/`; the ~120 lines of scoring, plotting and export it needs are in the notebook. `utils/` and `src/` are untouched ✅. |
| ~~**I2**~~ | ~~The A layer does not exist~~ — **Resolved.** 5c_CR built and ran it on 2026-09-15: `road_impacts.parquet`, 1,512 rows ✅. What replaces the issue is smaller and mechanical: **5d's accessibility paths point at seven wide files in `parquet/local_accessibility/` that will never exist**, and must be repointed to one long file in `parquet/flood_scenarios/` (§0.3, 5c I3). |
| ~~**I3**~~ | ~~D1, D3a, D3b, D4, D5 and D7 are unanswered~~ — **Resolved 2026-09-15** (§5) and implemented. |
| ~~**I4**~~ | ~~`prepare_metrics` would fail silently on CR data~~ — **Resolved by not using it.** The CR notebook never calls Serbia's zero-filling path; every metric is named explicitly and asserted present, so a missing input raises instead of producing a plausible index built from zeros. |
| **I4** | **`prepare_metrics` would fail silently on CR data.** It renames `max_depth`, `dužina_sn`, `datum_evid` — none exists in CR — and derives `landslide_exposure` from a missing column. `score_climate_criticality` then hits its `if col not in gdf.columns` branch and **creates the metric as zeros with a printed warning**, so the notebook would run to completion and produce a plausible-looking index built from five all-zero hazard columns. This is the single most dangerous failure mode in the transposition: it does not raise. |

### 6.1b Deviations from this plan made during implementation

| Where | Deviation | Why |
|---|---|---|
| §4.8 | Output GeoPackage named **`combined_hazard_criticality.gpkg`**, not `combined_climate_criticality.gpkg` as this plan said. | D1 renames the index; the plan's own §4.8 had not been updated to match. The notebook *filename* still carries the `Climate` stem for pipeline continuity, as D1 specifies. |
| D8 | Workbook written to **`intermediate_results/excel/`**, not a `results/` directory. | CR has no `results/` dir, and creating one outside `intermediate_results/` would sit **untracked but not gitignored**, risking a committed 1.9 MB binary. Under `intermediate_results/` it is ignored like every other data artefact. This is the one use of an `excel/` folder on the CR side; `CLAUDE.md` rules out the Serbia *mirroring scheme*, not a single final deliverable. |
| §4.3 | **`log1p` and the per-metric min-max were dropped**, not ported. | Both are monotone increasing and quintile rank is invariant under monotone transforms, so neither can change any convex score. The notebook **proves this** with an assertion over all six T/A metrics rather than asserting it in prose ✅. A whole scoring stage that Serbia carries turns out to be inert. |
| §4.1 cell 11 | Statistics reported by **`CLASE`**; Serbia's high-tier/low-tier split and its Mann-Whitney U test are **not** ported. | `CLASE` is a functional class (Primaria … Local), not an administrative tier like Serbia's IA/IB/IM/IIA/IIB, so "high tier vs low tier" has no CR meaning. Inventing one to keep the test would be worse than dropping it. |
| D8 | Workbook has **10 sheets**, not the 6 the plan listed — added `Criticality x Quintile`, `Scoring Variants`, `Metric Support`, `Caveats`. | The three diagnostic tables and the caveat list are the things most likely to be lost when the index leaves this repository, so they belong in the deliverable rather than only in notebook stdout. |
| §4.5 | The variant table is **three rows, not a full factorial**, and two of the three were already measured in §3.8. | Stated as confirmation rather than discovery, per §4.5. |

### 6.2 Non-blocking, must be recorded

| # | Issue |
|---|---|
| I5 | **A is a basin attribute, not a road attribute** ✅ (§3.3b) — 326 roads carry 45 values. Inherited from Serbia's `calculate_service_criticality`; 5c states it in its own header. Only D7(c) fixes it. |
| I5b | **A is 32 % isolation penalty by construction.** 5c reports that 31.8 % of affected origin-rows are charged the 7 h penalty, so `travel_time_impact` partly measures `ISOLATION_PENALTY_FACTOR = 2.0` rather than travel time ✅. That constant is a notebook-2 modelling choice, so **changing it would change CC** — a dependency neither Serbia nor the CR plans have tracked before. |
| I5c | **Serbia's `impact_class` breaks put 73 % of CR roads in one class** ✅, which is why 5c added `impact_class_cr`. If 5d reports any accessibility class it must say which break set, and must not score either (§4.4). |
| I6 | **186 physical roads are under 50 m, minimum length 0.0000 km** ✅ (A3). Serbia's cleaning rule would drop none of them because none is a duplicate key, but a zero-length road in a length-weighted index deserves an explicit decision rather than inheritance. |
| I7 | **`flood_value` max is 30.71 m** ✅ and enters H's top quintile. [5a I2](5a_Main_Network_Hazard_Criticality_CR_plan.md) left the sanity ceiling undefined; 5d is where an implausible depth becomes a criticality rank. `flood_depth_implausible` exists in the layer — use it at least as a reported flag. |
| I8 | **`precip_rx1month` substitutes for Rx1day** ([5a I9](5a_Main_Network_Hazard_Criticality_CR_plan.md)) and enters H unchanged. |
| I9 | **`precip_anomaly_value` must stay out of H** ([5a §3.3](5a_Main_Network_Hazard_Criticality_CR_plan.md)) — it is observed 2025 vs 2000–24, not a recurrence probability. It is in the input layer and it would be easy to add by accident. |
| I10 | **LHASA susceptibility cannot be validated for CR** ([5a I7](5a_Main_Network_Hazard_Criticality_CR_plan.md)), and it is the metric with the widest support in H (99.8 % ✅). |
| I11 | **`_classify` re-ranks into quintiles, so the class labels are relative by construction.** "Very High" always holds ~20 % of non-zero roads whatever the absolute values — the classes cannot be compared across runs, across variants, or against Serbia. Serbia never says this; CR must. |
| I12 | **37 % of roads land in "No criticality" for a structural reason** ✅ (§3.5). Needs a caption, not a fix. |
| I13 | **The CR notebooks are untracked in git**, and 5d's Serbia-copy baseline is now **gone from the working tree** — the rewrite overwrote it. It is still recoverable from `notebooks/5d_Combined_Climate_Criticality.ipynb` (the Serbia original, byte-identical to what 5d_CR was). Committing the CR notebooks remains worth doing — `4a`, `2b`, `5a`–`5d` all still show as `??` ✅. 5d is the one case where committing first has real value: its current content **is** the Serbia original, so committing it now makes the transposition a readable diff. After the rewrite that baseline is gone. Also delete `notebooks/4a_Hazard_maps_CR.ipynb.bak`, a backup file sitting in the working tree ✅. |
| I14 | **`CLAUDE.md` is stale on the run order** — it lists `1b → 2 → 2b → 3d → 4a` and does not mention 5a–5d, though 5a, 5b and 5c are all built and run ✅. Worth updating when 5d lands. (Also still says 4a runs on `criticality_env`; [5a I12](5a_Main_Network_Hazard_Criticality_CR_plan.md) records that the kernelspec says otherwise.) |
| I15 | **Serbia's own run never produced the `.lyrx` layers** — its stored output prints "arcpy could not be imported" four times ✅. So the ArcGIS half of Serbia's 5d output has never existed in either country, and dropping it (A4) removes nothing that was working. |
| I16 | **Two figure names would collide in the shared `figures/` directory.** Serbia's 5d writes `criticality_analysis_3panel.png` and `climate_criticality_mean.png` with no country suffix, and `figures/` is shared. 5c hit the same problem and worked around it (5c D8). Give every CR figure a distinct name. |

---

## 7. Out of scope

- Re-running 4a, 5a, 5b, 5c, or the SPOF percolation from notebook 2. 5d is a pure consumer —
  **except** under D7(c), which would have 5d compute a hospital-access SPOF of its own. That is the
  one option in this plan that breaks the consumer-only rule every other CR notebook has kept, and
  it is called out as such in D7 rather than smuggled in here.
- Any fragility, damage, or expected-annual-loss modelling (§4.9).
- Editing `utils/criticality_functions.py`, `utils/arcgis.py`, the Serbia
  `5d_Combined_Climate_Criticality.ipynb`, or `src/config/network_config.py`. CR logic goes in the
  notebook or in `src/network_preparation_cr.py`, per `CLAUDE.md`.
- Sourcing the missing hazard data (wildfire, temperature, seismic, climate projections). Tracked in
  [5a §4.0c](5a_Main_Network_Hazard_Criticality_CR_plan.md) as the registry's extension point.
- Extending the network beyond 1b's main-network scope, which is what the EBAIS co-location problem
  ([5b I2](5b_Run_Flood_Scenarios_Accessibility_CR_plan.md)) would require.
