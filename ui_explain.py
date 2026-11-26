"""Plain-words explanations and formulas behind every number (the "Show the math" panels)."""


def aed(v):
    if v is None or v != v or abs(v) == float("inf"):
        return "–"
    a = abs(v)
    s = f"{a / 1e9:.1f}B" if a >= 1e9 else (f"{a / 1e6:.1f}M" if a < 1e8 else f"{round(a / 1e6)}M") if a >= 1e6 else f"{round(a / 1e3)}k" if a >= 1e4 else f"{a:,.0f}"
    return ("−" if v < 0 else "") + "AED " + s


def pct(v, d=0):
    return "–" if v is None else f"{v * 100:.{d}f}%"


def num(v, d=0):
    return "–" if v is None else f"{v:,.{d}f}"


def explain(r):
    S, A, f, u, L = r["stages"], r["assumptions"], r["stages"]["forecast"], r["unit"], r["limits"]
    shock = ["None", "Low", "Medium", "High"][r["settings"]["shocks"]]
    CO = r.get("competition") or {}

    def a(k, fmt=lambda v: num(v, 2)):
        return (A[k]["name"], fmt(A[k]["likely"]), A[k]["label_text"])

    sim_inputs = [("Replays of the market", num(f["runs"]), ""), ("Simulated customers (agents)", num(f["abm"]["agents"]), ""), ("Random shocks", shock, ""),
                  ("Market potential (customers)", num(S["classify"]["potential_used"]), S["classify"]["label"]), ("Spend per customer per month", aed(u["arpu"]), "Derived"),
                  a("var_pct", lambda v: f"{v:.1f}%"), a("fixed", aed), a("setup", aed), a("cac", aed), a("churn", lambda v: f"{v:.1f}%"), a("capacity", num),
                  ("Satisfaction", f"{u['satisfaction']:.2f}", "Derived")]
    V, M, VV, IM, EV = r["validation"], r["market_sizing"], r["value"], r["improve"], S["experiments"]["evidence"]
    D = {
        "decision": ("How the decision is made",
                     f"Every tested launch plan is simulated. A plan passes when at least {pct(L['min_payback'])} of simulated futures (the safety standard) pay back within your {f['horizon']} months, its chance of needing more cash than your budget is at most {pct(L['max_ruin'])}, and its expected value is positive. Among passing plans the one with the highest expected value wins. If the evidence behind the numbers is thin, the answer becomes “test first”, so the tool never says “launch” on guesses alone. Hard limits, such as a licence blocker or capacity below break-even, override everything.",
                     f"pass = P(payback ≤ {f['horizon']} months) ≥ {pct(L['min_payback'])}\n   AND P(cash need > {aed(L['budget'])}) ≤ {pct(L['max_ruin'])}\n   AND E[NPV] > 0\nbest = highest E[NPV] among passing plans\nevidence strength = {pct(r['evidence']['strength'])} (test first if below 35%, unless the top 3 inputs are each desk-checked)",
                     [("Payback chance", pct(f["p_payback"]), ""), ("Chance of exceeding budget", pct(f["p_ruin"]), ""), ("Expected NPV", aed(f["npv_mean"]), ""), ("Evidence strength", pct(r["evidence"]["strength"]), "")]),
        "p_payback": ("Chance of paying back (agent-based simulation)",
                      f"The market is simulated customer by customer and replayed {num(f['runs'])} times with different draws of the uncertain inputs, because one run is only one story. Before opening the business pays half its fixed costs. Then each month every simulated customer may hear about you through marketing or friends, decide to buy, have a good or bad experience, and stay or leave. Shocks, competitor promotions, boom and downturn months and UAE seasons hit along the way. The chance is the share of replays where cumulative cash climbs back above zero within {f['horizon']} months.",
                      "per customer i, month t:\n  hears: marketing chance p × awareness ramp, or friends 1 − (1 − w)^(happy friends), w = 2q(0.5 + S)\n  buys with P_i × demand factors × 0.75^(unhappy friends)\n  leaves with churn × (1.5 − satisfaction_i) × shock factor\n  capacity: buyers beyond capacity are turned away\ncash += Σ customers × spend × (1 − variable cost) − fixed − new × CAC\n" + f"P(payback) = {pct(f['p_payback'])}", sim_inputs),
        "p_ruin": ("Chance of needing more than your budget", "In every replay the lowest point of cumulative cash (including setup and pre-opening costs) is the cash you need. This is the share of replays where that need is bigger than your budget.",
                   f"cash need = −min(cumulative cash)\nP(ruin) = {pct(f['p_ruin'])}\n90th-percentile cash need = {aed(f['cash_need_p90'])}", sim_inputs),
        "npv": ("Expected value (NPV)", "Net present value adds up every month's profit, discounted at 12% a year, minus the setup and pre-opening costs. The expected value is the average across all replays.",
                f"NPV = −setup − pre-opening + Σ profit_t ÷ (1 + r)^t, r = 12% a year\nE[NPV] = {aed(f['npv_mean'])} (bad case {aed(f['npv_p10'])}, good case {aed(f['npv_p90'])})", []),
        "evidence": ("Evidence strength", "Each key input earns credit by where it came from: measured 1.0, benchmarked with a source 0.6, founder input 0.3, AI estimate 0.2, model-derived 0.15, category prior 0.1. Strength is the average, minus 5 points for each optimistic anomaly flag.",
                     "\n".join(f"{k}: {v}" for k, v in r["evidence"]["labels"].items()) + f"\nstrength = {pct(r['evidence']['strength'])}", []),
        "validation": ("Validation score", "Each check is scored 0 to 100 and combined with fixed weights: money 30%, customers 25%, market 20%, competition 15%, ease of use 10%. Checks that could not be assessed are left out and the weights rescaled. The range widens when evidence is thin, when the critic flags weak claims, and when payback is close to a coin toss.",
                       "\n".join(f"{k}: {'–' if r['scores'][k] is None else round(r['scores'][k])} × {w * 100:.0f}%" for k, w in V["weights"].items()) + f"\nscore = {V['score']:.1f}, range {V['low']:.0f} to {V['high']:.0f}", []),
        "sizing": ("TAM, SAM and SOM", "TAM is what category buyers in the area spend in a year today. SAM is the part within reach of one business. SOM bottom-up is what the agent simulation actually captures. When AI research gives a top-down SOM, the two are compared; more than 3× apart means the market size is unproven.",
                   f"TAM = {aed(M['tam_synthetic'])}\nSAM = TAM × catchment = {aed(M['sam'])}\nSOM bottom-up = {num(f['customers_end_p50'])} customers × {aed(u['arpu'])} × 12 = {aed(M['som_bottom_up'])}" + (f"\nSOM top-down (AI) = {aed(M['som_top_down'])}; gap {M['disagreement']:.1f}×" if M.get("som_top_down") else ""), []),
        "value": ("Value gap", "For likely buyers, willingness to pay is compared with your price (weighted by how likely each is to buy). Above 1 means they value it more than it costs.",
                  f"value ratio = {VV['value_ratio']:.2f}\nvalue gap score = 50 + 50 × tanh(ratio − 1) = {VV['value_gap_score']:.0f}", []),
        "describe": ("Stage 1: the blinded synthetic market", "20,000 simulated UAE adults are built only from the business type and population shares. They never see your idea. Each has an emirate, age, income, whether they buy in this category, what they spend today, how unhappy they are with today's options and how much they buy online.",
                     f"spend = median × (income ÷ median income)^0.45 × noise\npain ~ Beta(a, b) for the category\nTAM = {aed(S['describe']['tam_aed'])}", []),
        "segment": ("Stage 2: Gaussian mixture segments", "Buyers are described by income, spend, pain, price sensitivity, online preference and age. Gaussian mixture models with 2 to 6 groups are fitted and the Bayesian information criterion picks the number.",
                    "\n".join(f"k={b['k']}: BIC {b['bic']:,.0f}" for b in S["segment"]["bic"]) + f"\nchosen k = {S['segment']['k']}", []),
        "anomaly": ("Stage 3: Isolation Forest", f"{num(S['anomaly']['reference_size'])} plausible plans for this business type are generated from category ranges. An Isolation Forest learns what normal plans look like and scores yours. Assumptions beyond the 5th/95th percentile in the favourable direction are flagged as optimistic.",
                    f"anomaly score = {S['anomaly']['score']:.3f}\nmore typical than {pct(1 - S['anomaly']['more_normal_share'])} of comparable plans\noptimistic flags = {S['anomaly']['optimistic_count']}", []),
        "classify": ("Stage 4: logistic choice model", "Each simulated buyer gets a chance of buying once aware. It rises when the price is below what they would pay, when pain is high, when the channel suits them and when competition is weak. Experiments calibrate it.",
                     f"P(buy) = 1 ÷ (1 + e^−U)\nU = {S['classify']['coefs']['b0']:.2f} + {S['classify']['coefs']['b_value']:.2f}·ln(WTP ÷ price) + {S['classify']['coefs']['b_pain']:.2f}·(pain − 0.5) + {S['classify']['coefs']['b_fit']:.2f}·fit + {S['classify']['coefs']['b_comp']:.2f}·position\nmarket potential = {num(S['classify']['potential_used'])}", []),
        "regress": ("Stage 5: hurdle regression", "Stage 4 says whether someone buys; stage 5 says how much. Spend scales with today's category spend; a regression weighted by the chance of buying shows the drivers.",
                    f"expected spend = {aed(S['regress']['expected_arpu'])}\nR² = {S['regress']['r2']:.2f}", []),
        "survival": ("Stage 6: survival analysis", "Customer lifetimes follow an exponential model adjusted for satisfaction and price sensitivity. Payback timing across replays uses a Kaplan-Meier curve, which handles replays that never pay back.",
                     "hazard = churn × (1.5 − satisfaction) × (0.75 + 0.5 × price sensitivity)\nmedian lifetime = ln 2 ÷ hazard\nKaplan-Meier: S(t) = Π (1 − d_i ÷ n_i)", []),
        "forecast": ("Stage 7: agent-based simulation", f"{num(f['abm']['agents'])} simulated customers, each standing for about {num(f['abm']['people_per_agent'])} real people, sit on a small-world friend network ({f['abm']['friends_per_agent']} friends each). A local competitor answers with a 4-month promotion once you take more than 3% of reachable buyers. Shocks, Markov economic cycles and summer/Ramadan seasons apply.",
                     f"network: Watts–Strogatz, 10% random links\nregimes: normal ×1, boom ×1.12, downturn ×0.85\nshock level: {shock}\n{pct(f['abm']['wom_share'])} of customers came through friends\ncompetitor reacted in {pct(f['abm']['runs_with_competitor_reaction'])} of replays", sim_inputs),
        "text": ("Stage 8: TF-IDF topics", "Customer reviews and interview notes become word-weight vectors (TF-IDF), grouped into topics with k-means, and each topic is compared with your idea by cosine similarity.", "tf-idf(w, d) = tf × log(N ÷ df)\nmatch = cos(idea, topic centre)", []),
        "experiments": ("Stage 9: Bayesian tests", "Each experiment updates a Beta distribution. A landing-page test calibrates the buying model and measures customer cost; pricing tests fit price sensitivity; interviews update pain; a pilot measures churn and NPS; A/B tests give the chance B beats A.",
                        f"belief = Beta(1 + successes, 1 + failures)\nlanding test for a 50% lift from {pct(S['experiments']['predicted_conversion'], 1)}: {num(S['experiments']['sample_size_landing'])} visitors per version", []),
        "optimise": ("Stage 10: optimisation", "A linear programme spreads the monthly marketing budget across channels to win the most customers (with a dearer second tier per channel). Twelve launch plans are simulated with the same random events and checked against your limits.",
                     f"max Σ customers  s.t.  Σ cost × customers ≤ {aed(S['optimise']['channel_mix']['budget'])}\nblended CAC = {aed(S['optimise']['channel_mix']['blended_cac'])}", []),
        "leak": ("Where the funnel leaks", "Across all replays, NPV is regressed on the standardised inputs. Squared coefficients show the share of uncertainty each input explains; better evidence for the top one helps most.", f"share_k = β_k² ÷ Σβ²\nR² = {r['leak']['r2']:.2f}", []),
        "kill": ("Stop rules", "Market potential is scaled up and down and re-simulated to find where the payback chance crosses your minimum; that becomes a landing-page sign-up rate below which you should stop.",
                 f"threshold = {pct(r['kill']['rate'], 1)}" if r["kill"]["rate"] else "No crossing found.", []),
        "improve": ("How changes are tested", "Each change edits the model inputs and replays the market with the same random events as the current plan. Price changes re-run the buying model. The three best are combined in pairs; a combination is kept only if it beats both parents (one generation of a genetic algorithm).",
                    f"current plan: P(payback) {pct(IM['base']['p_payback'])}, E[NPV] {aed(IM['base']['npv_mean'])}", []),
        "vw": ("Van Westendorp price range", "Each respondent names four prices. Where the curves cross gives the optimal price (too cheap = too expensive), the indifference price (cheap = expensive) and the acceptable range.",
               (f"optimal {aed(EV['vw']['opp'])}, indifference {aed(EV['vw']['ipp'])}\nrange {aed(EV['vw']['pmc'])} to {aed(EV['vw']['pme'])}") if EV.get("vw") else "No survey yet.", []),
        "competition": ("How competitors are scored", "Each competitor's description is compared with your idea using TF-IDF cosine similarity, mixed with how many of your features it also offers. "
                        "Threat adds how close its price is to yours and how strong it is (rating). Direct rivals count fully, indirect 60%, substitutes 35%. "
                        "Named competitors raise rivalry and lower differentiation; those shift the buying model and make the simulated competitor react more often.",
                        "similarity = 0.7 x min(1, cosine / 0.35) + 0.3 x feature overlap\nprice closeness = exp(-|ln(their price / your price)| / 0.5)\n"
                        "threat = type weight x (0.5 similarity + 0.3 price closeness + 0.2 rating/5) x 100\n"
                        "rivalry = 1 + 4 x (1 - exp(-sum(threat/100) / 1.2))   (averaged with the AI's score if any)\n"
                        "competitor reaction chance per month = 15% x rivalry / 3",
                        [("Rivalry used", num(CO.get("rivalry"), 2), "1 weak to 5 strong"), ("Differentiation", num(CO.get("differentiation"), 0), "0-100"),
                         ("Competition score", num(r["scores"]["competition"], 0), "0.6 x (100 - 25 x (forces avg - 1)) + 0.4 x differentiation")]),
    }
    return D
