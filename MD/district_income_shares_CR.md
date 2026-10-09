# Deriving poor / middle / high income shares for Costa Rican districts

Purpose: produce, for each of the ~490 districts, a triplet `(share_poor, share_middle, share_high)`
that can be joined to `input_files/CENTROS_POBLACION/centros_poblados_localidades.shp` via
`CÓDIGO_DTA` and used to stratify the population mass `INEC_PROY` in the gravity/criticality work
(see [gravity_model_adjusted.md](gravity_model_adjusted.md)).

Status: **methods note, nothing implemented.** Statements marked *verify* have not been checked
against the actual files.

---

## 0. Decide the class boundaries before touching any data

"Poor / middle / high" is not a property of the data; it is three thresholds you choose. The choice
changes the answer far more than the estimation method does, so fix it first and state it in the paper.

| Definition | Cut-points | Source of the thresholds | Comment |
|---|---|---|---|
| **INEC official (LP)** | extreme-poverty line, poverty line, above | INEC publishes per-person monthly lines with each July ENAHO, separately for urban and rural | Nationally recognised; but the top group is "everyone not poor" (~75–80 % of people), which is useless as a "high income" class |
| **LAC four-class (World Bank)** | poor / vulnerable / middle / upper, at roughly USD 5.5–13–70 per person per day in 2011 PPP (≈ 6.85–14–81 in 2017 PPP) | Ferreira et al. (2013), *Economic Mobility and the Rise of the Latin American Middle Class* | Comparable across LAC and across time; needs a PPP conversion and a CPI vintage decision |
| **Relative (terciles/quintiles)** | 33rd/67th percentile of national per-capita household income | ENAHO decile tables | Trivially reproducible, always sums to 1/3 nationally, but "poor" then means "bottom third", not deprived |

For a criticality/equity paper my recommendation is **LAC four-class collapsed to three**
(poor + vulnerable = "low income"; middle; upper), with the INEC LP variant reported as a robustness
check. It gives a top group with real content and it survives reviewer scrutiny abroad.

Also decide the unit: **share of *people*** (per-capita household income), not share of households.
The gravity model masses are people.

---

## 1. What IDS 2023 can and cannot do

MIDEPLAN's [Índice de Desarrollo Social 2023](https://www.mideplan.go.cr/indice-desarrollo-social)
is the sixth edition, covers **490 districts in 84 cantons**, is built from administrative registers,
and scores each district 0–100 across five dimensions — **economic, electoral participation, health,
education, security** — with indicators such as potable-water coverage, secondary-education coverage,
homicide rate, internet access, electoral turnout.

Three consequences:

1. **It is not an income measure.** The economic dimension is about labour-market insertion, and it is
   one of five dimensions that get blended into a single score. Two districts with the same IDS can sit
   at very different income levels.
2. **It is ordinal-ish and relative.** The score is designed for *ranking* districts, not for
   cardinal comparison; a 10-point IDS gap does not mean a fixed colón gap.
3. **It carries no distributional information.** It is a single number per district, so it can inform
   the district *mean*, but says nothing about the *spread* inside the district — and the spread is
   exactly what determines the three shares.

So IDS cannot produce the shares on its own. It is an excellent **auxiliary variable**: near-complete
district coverage, register-based, and correlated with income. Every method below uses it that way.

**Practical:** the localities layer already carries `CÓDIGO_DTA` (5-digit), `PROVINCIA`, `CANTÓN`,
`DISTRITO`, so the join is by code, not spatial. Watch the vintage: IDS 2023 has seven more districts
than IDS 2017 because of newly created districts — check that every `CÓDIGO_DTA` in the shapefile
resolves in the IDS table and reconcile splits explicitly (*verify*).

---

## 2. Method A — IDS-anchored lognormal, benchmarked to ENAHO (fast, defensible)

The workhorse if you need numbers in days rather than months.

**Step 1 — within-district income is lognormal.** Assume per-capita household income in district *d*
is `ln Y ~ N(μ_d, σ²)`. Then for a threshold *z*:

```
share_below(z | d) = Φ( (ln z − μ_d) / σ )
share_poor_d   = Φ((ln z₁ − μ_d)/σ)
share_middle_d = Φ((ln z₂ − μ_d)/σ) − share_poor_d
share_high_d   = 1 − Φ((ln z₂ − μ_d)/σ)
```

The three shares sum to 1 by construction — a real advantage over estimating them separately.

**Step 2 — get μ_d from IDS.** Do *not* map IDS ranks straight onto income ranks. Instead estimate the
link where an independent income figure exists, then transfer it:

```
ln(income_pc_c) = a + b · IDS_c + e_c     (fitted over cantons c, population-weighted)
μ_d = a + b · IDS_d − σ²/2
```

Candidate left-hand sides at canton level: the **Atlas de Desarrollo Humano Cantonal** material-wellbeing
income estimate (§4), or ENAHO direct estimates for the handful of cantons with adequate sample.
Report R² — it tells you honestly how much income signal IDS carries. Consider using the five IDS
*dimension* sub-indices as separate regressors rather than the composite; the economic and education
sub-indices should dominate, and letting them do so is strictly better than the equal-ish blend.

**Step 3 — pick σ from a variance decomposition, not by guessing.** Within a region *r*, total
log-income variance splits into between-district and within-district parts:

```
σ²_within = σ²_region − Var_w(μ_d)      (w = population weights over districts in r)
```

`σ²_region` comes from ENAHO microdata for the region; `Var_w(μ_d)` from step 2. This prevents the
classic error of applying the *regional* dispersion inside every district, which inflates both tails.
If ENAHO gives you a Gini instead of a variance, `σ = 2·Φ⁻¹((G+1)/2)` for a lognormal.

**Step 4 — benchmark to ENAHO.** ENAHO is representative for the **six planning regions × urban/rural**,
and that is the finest level at which its income distribution is trustworthy. Add a per-region scalar
shift `δ_r` to every `μ_d` in the region and solve so that

```
Σ_d pop_d · share_poor_d(μ_d + δ_r)  =  pop_r · poverty_rate_r^ENAHO
```

One-dimensional root find per region. Then check what the *other* two classes come out at — if the
middle/high split is off after matching the poverty rate, σ is wrong, not δ.

**Assumptions to state:** lognormality (fails in the top 1 %, irrelevant here); σ constant within a
region; the IDS→income link is stable across the IDS range; no within-district heterogeneity is
represented beyond σ.

---

## 3. Method B — proper small-area estimation (strongest, slower)

The textbook answer, and there is Costa Rican precedent: Arias-Salazar (2023), *Small Area Estimates of
Poverty Incidence in Costa Rica under a SPREE Approach*, [J. Official Statistics 39(3)](https://journals.sagepub.com/doi/abs/10.2478/jos-2023-0021),
produces poverty incidence for the **81 cantons** in postcensal years by combining ENAHO with the census.

Two flavours:

- **Area-level (Fay–Herriot).** Take ENAHO direct estimates `θ̂_i` with their sampling variances at the
  finest level where they are computable (region×zone, or canton for the big ones), model
  `θ_i = x_i'β + u_i` with `x` = IDS score and sub-indices + Censo 2022 district covariates, and predict
  for districts with no survey sample. Because the target is a **composition** of three shares, work in
  additive-log-ratio space (`ln(s_poor/s_mid)`, `ln(s_high/s_mid)`) and back-transform — this keeps the
  shares positive and summing to one, and gives you a coherent covariance between them.
- **Unit-level (ELL / Molina–Rao).** Fit the income model on ENAHO households using only covariates that
  exist identically in Censo 2022, then simulate incomes for every census household and aggregate to
  district. Needs census microdata access (INEC, possibly via REDATAM or a research agreement) — this
  is the step that decides whether B is feasible for you.

**The one thing to check first:** Censo 2022 does **not** collect income (*verify* — CR censuses
historically have not). That is precisely why poverty mapping is a survey-census *linkage* problem,
and why the covariate set (housing materials, crowding, appliances, internet, education, employment
status, dependency ratio) is what carries the signal.

Deliverable quality: district estimates with MSE/CIs. That is publishable; Method A's are not, without
the sensitivity analysis.

---

## 4. Method C — the electricity trick (PNUD/UCR precedent)

The [Atlas de Desarrollo Humano Cantonal 2022](https://www.undp.org/sites/g/files/zskgke326/files/2023-06/informe_atlas_de_desarrollo_humano_cantonal.pdf)
(PNUD + Escuela de Estadística UCR + SINIRUBE) estimates canton per-capita household income by taking
**ENAHO regional per-capita income and using residential electricity consumption per capita as the
within-region discriminator**. That is exactly the structure of Method A step 2, with a much more
directly economic anchor than IDS.

Replicating it at *district* level needs residential kWh per subscriber by district from ICE, CNFL,
ESPH, JASEC and the rural cooperatives, or via ARESEP. Whether that exists at district granularity is
the open question (*verify*). If it does, this is the best single anchor available and I would use it
in place of, or alongside, IDS in the regression. Even at canton level it is directly usable as the
dependent variable in Method A step 2.

Caveat worth naming: electricity consumption saturates at the top (air-conditioning is the main
discriminator in the upper half) and is confounded by climate zone — add a temperature or elevation
control, which you already have from `4c_Temperature.ipynb`.

---

## 5. Method D — administrative registers (best for the *poor* share only)

**SINIRUBE** (Sistema Nacional de Información y Registro Único de Beneficiarios del Estado) holds
socioeconomic records for well over a million households, each classified by poverty level from the
FIS instrument, with address down to district. IMAS/SINIRUBE publish and share district-level counts.

- **Strength:** actual counts of households classified as poor/extremely poor, at district level, no
  modelling.
- **Weakness:** it is a *registry of applicants*, not a sample. Coverage is near-complete among the poor
  and near-zero among the non-poor, so it gives you a good numerator and a bad denominator, and it says
  nothing at all about the middle/high split. Treat `registered_poor_d / pop_d` as a **lower bound and a
  covariate**, not as `share_poor_d`. It is an excellent regressor in Method B and an excellent
  validation series for Method A.

---

## 6. Method E — gridded wealth surfaces (adds within-district structure)

Everything above produces one number per district and therefore cannot distinguish the informal
settlement from the gated community two kilometres away. Gridded products can, and they line up with
what this project already uses (`cri_pd_2020_1km_UNadj_ASCII_XYZ.csv`, WorldPop 1 km).

| Product | Resolution | Notes |
|---|---|---|
| [Meta Data for Good **Relative Wealth Index**](https://data.humdata.org/dataset/relative-wealth-index) | ~2.4 km | CSV of lat/lon/rwi/error; Costa Rica included among the 93 countries. Asset-based and *relative within country* — ordinal, not colones |
| CIESIN **Global Gridded Relative Deprivation Index** (GRDI v1) | ~1 km | Composite of nightlights, built-up, child mortality, SHDI |
| Kummu et al. gridded GDP per capita / subnational HDI | 5 arcmin | Downscaled from subnational accounts; smooth, low real spatial content |
| VIIRS nighttime lights | ~500 m | Cheap proxy, saturates in San José, poor in dense vegetation |
| Global Data Lab subnational HDI/IWI | region | Too coarse to add anything over ENAHO regions |

**Turning RWI into shares** — pure rank mapping:

1. Population-weight each RWI cell by the WorldPop grid.
2. Compute each cell's percentile in the national population-weighted RWI distribution.
3. Map percentiles to classes using the **national** class shares from ENAHO (if 26 % of people are
   poor nationally, the bottom 26 % of population-weighted RWI is "poor").
4. Aggregate cells to districts by population weight → the three district shares.

This assumes national RWI rank = national income rank, which is the weak point (asset wealth is
smoother and more persistent than income; rural landowners rank high on assets, low on cash income).
But it is the only method here that gives you **sub-district** variation, which matters if you later
want income-stratified accessibility at the locality rather than district level.

---

## 7. Recommended stack

1. **Fix the class definition** (§0). LAC three-class, per person, ENAHO 2023 as the benchmark year to
   match IDS 2023's vintage.
2. **Method A** as the production estimate: IDS (+ Atlas canton income, §4) → μ_d, variance
   decomposition → σ, benchmark to ENAHO region×zone.
3. **Method E (RWI)** as an independent second estimate and as the source of within-district spread if
   you need locality-level strata.
4. **Method D (SINIRUBE)** as external validation of `share_poor` and, if the counts are obtainable, as
   a covariate.
5. **Method B** only if a reviewer demands defensible uncertainty, or if census microdata access turns
   out to be easy — then it replaces A entirely.

**Validation plan.** Aggregate district estimates to cantons and compare against (i) ENAHO direct
canton estimates where the CV allows, (ii) the SPREE canton series of Arias-Salazar (2023), (iii)
SINIRUBE poor counts. Report Spearman rank correlation between the three independent estimates
(A, E, D) — agreement in *ranking* is the claim you can actually defend, and it is enough for a
criticality analysis.

**Sensitivity to report.** σ scaled 0.8–1.2×; class thresholds under both LP and LAC definitions;
IDS composite vs IDS dimension sub-indices as regressors. If the qualitative equity conclusion flips
under any of these, say so.

---

## 8. Pitfalls specific to this application

- **Ecological fallacy.** A district share applied to every locality inside it asserts that all
  localities in the district have the same income mix. Say it explicitly; RWI (§6) is the fix.
- **MAUP.** Districts range from a few hundred to >100 000 people. Population-weight everything, always,
  and never report an unweighted mean across districts.
- **Residence vs activity.** The gravity model moves trips between places; income shares describe
  *residents*. For a production-attraction split (Route B in
  [gravity_model_adjusted.md](gravity_model_adjusted.md)) income belongs on the **production** side
  only. Commuting means the people on a link near a business district are not the residents of that
  district.
- **District vintage.** 490 IDS 2023 districts vs whatever the shapefile encodes; reconcile by
  `CÓDIGO_DTA` and handle post-2017 splits before joining (*verify*).
- **Non-monotonicity at the top.** High-IDS districts (Escazú, Santa Ana, San Rafael de Montes de Oca)
  contain both the highest incomes in the country and long-standing informal settlements. A
  single-parameter lognormal centred on a high μ will under-count the poor there. Check these districts
  against SINIRUBE counts specifically.

---

## 9. Data checklist

| Item | Where | Access |
|---|---|---|
| IDS 2023 by district, with dimensions | [MIDEPLAN](https://www.mideplan.go.cr/indice-desarrollo-social) — Excel files by district/canton/region | Public download |
| ENAHO 2023 microdata (income, poverty, region, zone) | [INEC microdata catalogue](https://sistemas.inec.cr/nada5.4/index.php/catalog) | Public, registration |
| ENAHO poverty & income by region | [INEC ENAHO 2023 report](https://admin.inec.cr/sites/default/files/2023-10/reenaho2023.pdf) | Public |
| ENIGH (income & expenditure, for class thresholds) | [INEC catalogue](https://sistemas.inec.cr/nada5.4/index.php/catalog/380) | Public |
| Censo 2022 district tables / microdata | INEC | Tables public; microdata may need a request |
| Atlas de Desarrollo Humano Cantonal 2022 | [PNUD](https://www.undp.org/sites/g/files/zskgke326/files/2023-06/informe_atlas_de_desarrollo_humano_cantonal.pdf) | Public PDF + annexes |
| SINIRUBE district poverty counts | IMAS/SINIRUBE | Likely by request |
| Meta Relative Wealth Index | [HDX](https://data.humdata.org/dataset/relative-wealth-index) | Public CSV |
| Residential electricity by district | ICE / CNFL / ARESEP | *Verify existence at district level* |

**Output contract** (proposed) — `intermediate_results/parquet/socioeconomic/district_income_shares.parquet`:

```
cod_dta | provincia | canton | distrito | pop | share_low | share_mid | share_high |
mu_d | sigma_r | method | ci_low_share_low | ci_high_share_low | source_vintage
```

joined to the localities layer on `CÓDIGO_DTA`, so that `INEC_PROY` can be split into three masses
per locality.
