# Methodology

This follows a 7-step recipe for turning a decision into an analytic funnel.

## Step 1. The decision
- **Decision:** launch, launch with changes (pivot), test first, or stop.
- **Success metric:** P(cumulative cash ≥ 0 within the horizon) and expected NPV (12% a year discount rate).
- **Limits:** the founder's cash budget (needing more counts as ruin) with a maximum accepted P(ruin), and a minimum P(payback). Hard rules: licence blockers found by the regulation agent, and capacity below the break-even customer count.

## Step 2. Questions and algorithm families
See the table in the README. Each stage lives in `backend/app/funnel/`.

## Step 3. Order
Understand before predicting (1 describe, 2 segment, 3 anomaly), then whether before how much (4 classify, 5 regress), then when (6 survival), then the future (7 agent-based simulation), then evidence (8 text, 9 tests), then allocation (10), then prove and protect (leak analysis, audit, monitoring).

## Step 4. Data checks
Each stage reports whether it has labels, whether its inputs are known at decision time, and whether there are enough positive cases.
- **Stage 4** has no labels until a landing-page or pricing test exists, so it runs as a rule-based choice model with documented starting coefficients. With data it is calibrated, and fewer than 30 positives raises a warning.
- **Stage 8** is skipped with fewer than 6 pieces of text.

## Step 5. How stages connect
Probabilities and amounts are passed on, never yes/no labels.
- Stage 4 P(buy) per simulated person × reach → market potential M.
- Stage 5 → revenue per customer.
- Stage 6 → churn hazard.
- Stage 7 combines everything per future → NPV, payback, cash need.
- The decision uses the distributions: P(payback), P(ruin), E[NPV].

## Key formulas

**Synthetic market** (`synth.py`), per person:
- emirate, age band and income band drawn from population shares
- income: lognormal within its band
- category participation: Bernoulli
- spend today = median × (income / median income)^0.45 × e^(σz)
- pain ~ Beta(a, b) for the category
- online preference ~ Beta, shifted by age
- price sensitivity = 1 / (1 + relative income) + noise

**Choice model:**
- U = b0 + b_value · ln(WTP/price) + b_pain · (pain − 0.5) + b_fit · (2 · fit − 1) + b_comp · position, with P(buy) = 1/(1+e^−U)
- WTP = spend today × (1 + 0.6 · (pain − 0.5))
- Starting values: b0 = −3.6, b_value = 2, b_pain = 2.5, b_fit = 1, b_comp = 1
- Calibration: the intercept is shifted (Brent root-finding) so the mean P(buy) equals the measured conversion. Two or more price points fit b_value by binomial maximum likelihood.

**Spend (hurdle part 2):** spend_i = price × √(spend today / category median), clipped to 0.5–2 and normalised so the average category buyer pays the planned price. A regression weighted by P(buy) reports the drivers and R².

**Agent-based simulation** (`abm.py`)

*Agents.* 1,500 to 5,000 category buyers within reach are drawn from the blinded market. Enough are used that capacity is represented by about 40 agents; each stands for pool ÷ N real people. Each agent keeps its own P(buy) (stage 4), spend (stage 5), willingness to pay, segment and description.

*Friend network.* Watts–Strogatz: a ring sorted by segment, emirate and channel (homophily), with 10 friends each and 10% of links rewired at random.

*Uncertain inputs* are drawn per run from triangular(low, likely, high): the buying multiplier, spend, variable cost, fixed costs, setup, CAC, churn, capacity, p, q and satisfaction.

*Before opening*, half the fixed costs are paid for the type's pre-opening months.

*Each month, for each agent:*
- **Awareness:** unaware agents see marketing with chance p · min(1, (t+1)/6), weighted ×2 for the beachhead segment and ×0.35 for others when the plan focuses. Any agent who has not bought hears from friends with chance 1 − (1 − w)^(happy friends), where w = 2q(0.5 + S).
- **Decision:** buy with P_i × demand factors × 0.75^(friends who left unhappy in the last 3 months). Agents who said no before reconsider at half the probability.
- **Capacity:** buyers beyond capacity are turned away, exactly. Above 90% utilisation, every customer's satisfaction drops by 0.15.
- **Experience:** satisfaction_i ~ S + N(0, 0.15) at purchase. Monthly leaving chance = churn · (1.5 − satisfaction_i) · shock factor. Leavers with satisfaction < 0.4 spread negative word of mouth for 3 months.
- **Competitor (a game-theoretic response):** once your customers exceed 3% of reachable buyers, a local competitor launches a 4-month promotion with 15% chance a month: demand ×0.8, churn ×1.25, satisfaction −0.1.

*Shared across agents, per run:*
- Markov regime: normal 1, boom 1.12, downturn 0.85
- summer and Ramadan factors by business type
- shocks with monthly probability λ ∈ {0, 2%, 4.5%, 8%}: competitor (demand 0.7, churn 1.3, 6 months), downturn (0.75, 8 months), cost jump (fixed costs 1.2, 12 months), rule change (one month of fixed costs, demand 0.9, 3 months), viral (1.8, 2 months)

*Money:* profit = Σ customers · spend · (1 − v) − fixed costs · shock factor − new customers · CAC − one-off shock costs. NPV is discounted at 12% a year.

*Ensemble:* the market is replayed 100 times (25 for each of the 12 launch plans and the stop-rule search), with the same seed across plans so comparisons are fair. Tests check capacity, word of mouth, unhappy customers leaving, the competitor reaction and repeatability.

**Uncertainty follows evidence:** the market-potential range is ×(0.35, 1, 1.6) when uncalibrated, ×(0.55, 1, 1.4) after a pricing test and ×(0.7, 1, 1.3) after a landing-page test.

**Survival:** hazard = churn · (1.5 − S) · (0.75 + 0.5 · price sensitivity). Kaplan-Meier over the runs' payback times, censored at the horizon.

**Isolation Forest:** trained on 3,000 comparable plans in log space with a shared scale factor (bigger businesses cost more and serve more). Each assumption's percentile is reported. Beyond the 5th or 95th percentile in the favourable direction counts as optimistic.

**Linear programme:** maximise customers won subject to the budget and each channel's cap. A second tier per channel costs 60% more.

**Launch options:** 3 prices × {full, lean (fixed 0.7, setup 0.5, capacity 0.6)} × {all, beachhead segment (market × segment share × 1.6, CAC 0.75, churn 0.85)}. Market potential at each price is recomputed by the choice model.

**Evidence strength:** the mean credit of the key inputs: measured 1, benchmarked 0.6, founder 0.3, AI 0.2, derived 0.15, prior 0.1. Each optimistic flag subtracts 0.05. Below 35%, the result is "test first".

**Leak (Step 6):** standardised regression coefficients of NPV on the inputs across runs. share = β² / Σβ².

**Kill criteria:** market potential is scaled and re-simulated to find where P(payback) crosses the minimum, then turned into a sign-up-rate threshold.

**Audit (Step 7):**
- the synthetic market's fingerprint
- a base rate (the same type with priors only)
- claims dependence (the result without any AI or founder numbers)
- a stress test (High shocks)
- revenue concentration
- optimism flags
- calibration over recorded outcomes (Brier score)

## Honesty rules
- Synthetic data is for stress-testing, not evidence. Real data always outweighs it.
- No "launch" without evidence.
- Every number carries its source label. URLs not returned by web search are dropped.
