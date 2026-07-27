# Gravity model with population and economic activity — methodological basis

Scope: the demand matrix used in `2_Main_Network_Criticality_Analysis` (Serbia) and its Costa Rica
adaptation. This note collects the peer-reviewed basis for extending the demand model beyond
population alone, and states what is verified versus what still needs checking.

Related: [2_Main_Network_Criticality_Analysis_CR_plan.md](2_Main_Network_Criticality_Analysis_CR_plan.md) §5.

## 1. Current specification

`src/2_Main_Network_Criticality_Analysis.py:425` implements an **unconstrained gravity model with a
single mass term**:

```
D_ab = P_a · P_b · exp(−β · t̃_ab),    β = dist_decay = 1.0
```

where `t̃` is travel time normalised by the network maximum, the result is rescaled to
`max_trips = 25_000` and ceiling-rounded (`src/2_Main_Network_Criticality_Analysis.py:74`).

Properties worth naming explicitly:

- mass exponents are implicitly fixed at 1;
- there is no economic term;
- the matrix is **symmetric by construction**, although the OD network itself is directed;
- `β = 1` is an assumption, not a calibrated value.

## 2. Two peer-reviewed routes to adding economic activity

### Route A — composite mass (augmented gravity)

Replace each mass with a Cobb–Douglas composite:

```
M_i = P_i^α · Y_i^γ
```

with `Y` = GDP or GVA. This is the standard form in trade and interregional-flow gravity work, where
mass is associated with both GDP and population. Reference points: Anderson, *The Gravity Model*
(NBER w16576) for the theory and its estimation problems; Kabir et al. (2023), *SN Business &
Economics* 3, for a recent survey of the theoretical development.

**Weakness for this application.** `α` and `γ` are meaningless unless estimated against observed
flows, and the Anderson & van Wincoop multilateral-resistance critique says naive OLS on a
log-linearised gravity equation is biased. Adopting Route A without calibration data replaces one
arbitrary assumption with three.

### Route B — production/attraction split (preferred)

The cleaner justification for "population *and* economic activity", because the two enter in
different roles rather than being multiplied together:

```
T_ij = A_i · O_i · B_j · D_j · f(c_ij)

O_i ∝ population_i          (population produces trips)
D_j ∝ economic activity_j   (economic activity attracts trips)
```

Population produces trips; economic activity (employment, GVA, floorspace) attracts them. This is
Wilson's entropy-maximising derivation and the textbook trip-distribution step:

- Wilson, A.G. (1971) A family of spatial interaction models, and associated developments.
  *Environment and Planning A* 3(1): 1–32.
- Ortúzar, J. de D. & Willumsen, L.G. *Modelling Transport*, 4th ed. (2011), ch. 5.
- Fotheringham, A.S. & O'Kelly, M.E. (1989) *Spatial Interaction Models: Formulations and
  Applications*.

Route B also gives a principled reason for **asymmetric masses**, which matters here because the OD
matrix is directed while the current specification forces symmetry.

## 3. What comparable criticality studies actually did

Important context before citing anything:

**The closest global analogue does not use a gravity model at all.** Koks et al. (2023), *ERIS*,
"A global assessment of national road network vulnerability", allocates demand from WorldPop
population shares and travel time, normalises to 100 trips with a floor of 1 trip per OD pair, and
explicitly flags this as a simplification adopted for cross-country comparability. No GDP term, no
calibrated decay parameter. Verified by reading the paper.

Consequence: **population-only demand is defensible and precedented in exactly this methodological
lineage.** Adding economic activity is an improvement to be justified on its own merits, not a
correction of a defect.

Vulnerability-metric side (what is done with the matrix once built):

- Jenelius, E., Petersen, T. & Mattsson, L.-G. (2006) Importance and exposure in road network
  vulnerability analysis. *Transportation Research Part A* 40(7): 537–560.
- Jenelius, E. & Mattsson, L.-G. (2012) Road network vulnerability analysis of area-covering
  disruptions: a grid-based approach with case study. *Transportation Research Part A* 46: 746–760.
- Taylor, M.A.P., Sekhar, S.V.C. & D'Este, G.M. (2006) Application of accessibility based methods for
  vulnerability analysis of strategic road networks. *Networks and Spatial Economics* 6: 267–291.

Taylor et al. is the accessibility-based variant, and is the natural citation if economic activity is
wanted in the **impact metric** rather than in the demand matrix — a lighter-weight alternative to
rebuilding the OD model.

Freight specifically: the doubly-constrained gravity literature for interregional trade estimation is
the current reference, and its calibration convention transfers directly — fix the distance exponent
near 2, iterate until mean ton-km matches a target within ~10%.

## 4. Calibrating β from AADT — the highest-value change

The CR network carries `total_aadt` non-null on all 9,764 edges. This makes the decay parameter
**estimable rather than assumed**: assign gravity flows to the network and fit `β` (and any mass
exponents) by minimising discrepancy against observed counts.

This is OD-matrix-estimation-from-traffic-counts, a well-established family:

- Willumsen, L.G. (1981) Simplified transport models based on traffic counts.
- Cascetta, E. (1984) Estimation of trip matrices from traffic counts and survey data: a generalized
  least squares estimator. *Transportation Research Part B* 18(4–5): 289–299.
- Spiess, H. (1990) A gradient approach for the O-D matrix adjustment problem. *Transportation
  Science*.

This converts `dist_decay = 1.0` from an arbitrary constant into a calibrated, citable number. It is
a larger methodological gain than adding GDP.

**Caveat:** a substantial share of CR AADT is imputed (`aadt_imputed`, from 1b). Calibrate on
observed-only rows and report the subset size.

## 5. Proposed CR specification

Two matrices, not one — the analysis already reports passenger (`phl`/`pkl`) and freight
(`thl`/`tkl`) separately, and they have different masses *and* different decay.

| | Production `O_i` | Attraction `D_j` | Decay |
|---|---|---|---|
| Passenger | `INEC_PROY` population | employment / GVA by canton | steeper β |
| Freight | agricultural + manufacturing output | ports (Limón-Moín, Caldera), free-trade zones, San José | flatter β |

For Costa Rica, **ports and free-trade zones dominate freight attraction in a way population never
captures.** That is the strongest case-specific argument for adding economic activity here, and it is
concrete enough to defend in review.

### Economic-activity data, in order of preference

1. Banco Central de Costa Rica regional accounts; INEC economic directory — national, authoritative.
2. Gridded GDP — Kummu, M., Taka, M. & Guillaume, J.H.A. (2018) Gridded global datasets for GDP and
   Human Development Index over 1990–2015. *Scientific Data* 5: 180004.
3. VIIRS nighttime lights — last resort. Henderson, J.V., Storeygard, A. & Weil, D.N. (2012)
   Measuring economic growth from outer space. *American Economic Review* 102(2): 994–1028.

Documented limitation of option 3: nighttime lights are a poor proxy for economic activity in **rural**
areas of middle-income countries — which is most of the CR network outside the GAM. See Pérez-Sindín
et al. (2021) on Colombia, *Energy Research & Social Science*.

## 6. Sensitivity caveat — test before investing

In the current pipeline demand enters **only as weights in `np.average`**, so absolute scale cancels
out (see plan §5). Switching from `P_a · P_b` to a population×GDP composite therefore changes results
only through the **relative** weighting between OD pairs.

If GDP and population are strongly collinear across CR localities — they largely are — the criticality
rankings may barely move.

**Recommended first step:** compute both demand matrices and take a Spearman rank correlation of the
resulting criticality rankings *before* assembling the economic data properly. If ρ > 0.95, the honest
write-up is "an economic-activity-weighted variant was tested and rankings were insensitive", which is
a stronger paper section than an uncalibrated GDP term.

## 7. Verification status of references

Verified this session (fetched or confirmed via search):

- Koks et al. (2023) *ERIS* — demand specification read directly; population-only, no gravity model.
- Jenelius, Petersen & Mattsson (2006); Jenelius & Mattsson (2012).
- Doubly-constrained gravity for interregional trade estimation.
- Anderson, *The Gravity Model* (NBER w16576).
- Nighttime-lights rural-proxy limitation (Colombia study).
- Oh, J.E., Espinet Alegre, X., Pant, R., Koks, E.E., Russell, T., Schoenmakers, R. & Hall, J.W.
  (2019) *Addressing Climate Change in Transport: Volume 2 — Pathway to Resilient Transport*, World
  Bank. Existence, authorship and the fact that it provides a network criticality/vulnerability
  framework are confirmed.

**Not verified — check before adding to a bibliography:**

- Whether Oh et al. (2019) Vol. 2 actually specifies a **GDP-based gravity OD matrix**. If it does, it
  is the single best citation available, being the same methodological family as the Serbia work.
- Wilson (1971) — volume/page numbers.
- Cascetta (1984), Willumsen (1981), Spiess (1990) — cited from background knowledge.
- Kummu et al. (2018) — cited from background knowledge.

## Sources

- [A global assessment of national road network vulnerability — Koks et al. 2023, ERIS](https://iopscience.iop.org/article/10.1088/2634-4505/acd1aa)
- [Doubly constrained gravity models for interregional trade estimation](https://www.sciencedirect.com/science/article/pii/S1056819023003202)
- [Review of the gravity model: origins and critical analysis of its theoretical development](https://link.springer.com/article/10.1007/s43546-023-00461-0)
- [The Gravity Model — Anderson, NBER w16576](https://www.nber.org/system/files/working_papers/w16576/w16576.pdf)
- [Road network vulnerability analysis of area-covering disruptions — Jenelius & Mattsson 2012](https://www.sciencedirect.com/science/article/abs/pii/S0965856412000213)
- [Large-Scale Road Network Vulnerability Analysis — Jenelius thesis](https://www.diva-portal.org/smash/get/diva2:354583/FULLTEXT01.pdf)
- [Are night-time lights a good proxy of economic activity in rural areas in middle and low-income countries?](https://www.sciencedirect.com/science/article/pii/S235293852100183X)
- [Addressing Climate Change in Transport: Volume 2 — World Bank](https://openknowledge.worldbank.org/entities/publication/3448a40a-f081-540b-b7e4-162fdbfa5d18/full)
- [Spatial Interactions and the Gravity Model — The Geography of Transport Systems](https://transportgeography.org/contents/methods/spatial-interactions-gravity-model/)
