"""Stage 7 - "How many customers in future?" Agent-based market simulation.

Instead of moving one average customer number, thousands of individual simulated
UAE customers ("agents") are simulated, each taken from the blinded synthetic
market with their own willingness to pay, pain, channel preference and income.

Every month, for every agent:
  1. Hearing about you: unaware agents may see your marketing; any agent may hear
     from friends (a small-world friend network). Happy customers recommend you;
     customers who left unhappy warn their friends for 3 months.
  2. Deciding: an agent who hears about you buys with their own choice-model
     probability (stage 4), changed by the economy, the season, active shocks,
     competitor promotions and bad word of mouth. Agents who say no may reconsider
     later if friends recommend you.
  3. Capacity: if you are full, new buyers are turned away; above 90% utilisation
     service quality drops for everyone.
  4. Experience and leaving: each customer has their own satisfaction. Unhappy
     customers leave more often and spread negative word of mouth.
  5. Competitor reaction: once you take more than 3% of the reachable buyers,
     the incumbent may answer with a 4-month promotion (game-theoretic response).

The whole market is replayed many times with different draws of the uncertain
inputs (an ensemble), because one run is just one story. Cash, payback, NPV and
cash need are tracked per run, exactly as the decision needs them.
"""
import numpy as np
from .. import priors as P
from .simulate import tri, SHOCK_KEYS

K_FRIENDS = 10         # friends per agent (Watts-Strogatz ring lattice)
REWIRE = 0.10          # share of friendships rewired to random agents
COMP_SHARE = 0.03      # share of reachable buyers that provokes a local competitor
COMP_PROB = 0.15       # monthly chance the competitor reacts once provoked
COMP_MONTHS = 4


def friend_network(n, order, seed):
    """Small-world network. Agents are placed on a ring sorted by segment and
    emirate, so most friends are similar people (homophily); 10% of links are
    rewired at random, which creates the short paths word of mouth travels on."""
    rng = np.random.default_rng([seed, 99])
    pos = np.empty(n, dtype=int); pos[order] = np.arange(n)
    ring = order
    offs = [o for d in range(1, K_FRIENDS // 2 + 1) for o in (d, -d)]
    nb = np.stack([ring[(pos + o) % n] for o in offs], 1)
    rew = rng.random(nb.shape) < REWIRE
    nb[rew] = rng.integers(0, n, rew.sum())
    return nb


def simulate_abm(inp, pop, *, runs=100, seed=2027, horizon=36, shocks=2, cycles=True, seasonality=True, season="online",
                 budget=None, open_months=0, ramp_months=6, keep_paths=True, focus_segment=None, journeys=True):
    rng = np.random.default_rng([seed, 1])
    R, T = int(runs), int(horizon)
    N = len(pop["p_buy"]); nb = pop["nbrs"]; scale = pop["scale"]
    d = {k: tri(rng, inp[k], R) for k in ["market", "arpu", "var_pct", "fixed", "setup", "cac", "churn", "capacity", "p", "q", "satisfaction"]}
    d["satisfaction"] = np.clip(d["satisfaction"], .02, .98)
    mult = d["market"] / max(pop["market_base"], 1e-9)          # uncertainty in how likely agents are to buy
    arpu_mult = d["arpu"] / max(pop["arpu_base"], 1e-9)
    pbuy = np.clip(pop["p_buy"][None, :] * mult[:, None], 0, .95)
    cap_agents = np.maximum(d["capacity"] / scale, 1)
    vp = np.clip(d["var_pct"], 0, 95) / 100
    churn = d["churn"] / 100; S = d["satisfaction"]
    w_wom = np.clip(2 * d["q"] * (0.5 + S), 0, .9)              # chance one happy friend makes you aware this month
    mk_weight = np.ones(N)
    if focus_segment is not None:
        mk_weight = np.where(pop["seg"] == focus_segment, 2.0, 0.35)  # marketing aimed at the beachhead segment
    summer, ramadan = P.SEASON.get(season, P.SEASON["online"])
    lam = P.SHOCK_RATE[int(shocks)]
    w = np.array([P.SHOCKS[k]["weight"] for k in SHOCK_KEYS]); w = w / w.sum()
    dm_k = np.array([P.SHOCKS[k]["dm"] for k in SHOCK_KEYS]); cm_k = np.array([P.SHOCKS[k]["cm"] for k in SHOCK_KEYS])
    fm_k = np.array([P.SHOCKS[k]["fm"] for k in SHOCK_KEYS]); dur_k = np.array([P.SHOCKS[k]["months"] for k in SHOCK_KEYS])
    one_k = np.array([P.SHOCKS[k]["one_off"] for k in SHOCK_KEYS])
    cum = np.array(P.REGIMES["P"]).cumsum(1); rmult = np.array(P.REGIMES["mult"])
    r_month = (1 + P.ANNUAL_DISCOUNT_RATE) ** (1 / 12) - 1
    potential = pbuy.sum(1)

    state = np.zeros((R, N), dtype=np.int8)         # 0 unaware, 1 said no, 2 customer, 3 left
    sat = np.zeros((R, N)); unhappy_until = np.full((R, N), -1, dtype=np.int16)
    cash = -d["setup"].copy(); npv = cash.copy(); low = cash.copy()
    for _ in range(int(open_months)):
        cash = cash - .5 * d["fixed"]; npv = npv - .5 * d["fixed"]; low = np.minimum(low, cash)
    regime = np.zeros(R, dtype=int); rem = np.zeros((R, len(SHOCK_KEYS))); comp_left = np.zeros(R); comp_count = np.zeros(R)
    payback = np.full(R, np.inf); op_be = np.full(R, np.inf); shock_count = np.zeros(len(SHOCK_KEYS), dtype=int)
    paths = {k: np.zeros((R, T)) for k in ["cash", "customers", "revenue", "profit", "unaware", "said_no", "left"]}
    src = dict(marketing=np.zeros(R), word_of_mouth=np.zeros(R), turned_away=np.zeros(R), unhappy_left=np.zeros(R), left=np.zeros(R))
    hist0 = np.zeros((T, N), dtype=np.int8) if journeys else None
    how0 = np.zeros(N, dtype=np.int8); when0 = np.full(N, -1); left_unhappy0 = np.zeros(N, dtype=bool)

    U = lambda: rng.random((R, N), dtype=np.float32)
    pw_tab = (1 - (1 - w_wom[:, None]) ** np.arange(K_FRIENDS + 1)[None, :]).astype(np.float32)
    neg_tab = (.75 ** np.arange(K_FRIENDS + 1)).astype(np.float32)
    rows = np.arange(R)[:, None]
    pbuy = pbuy.astype(np.float32)
    for t in range(T):
        aware_ramp = min(1.0, (t + 1) / ramp_months) if ramp_months else 1.0
        # ---- the economy and random events (per run) ----
        if cycles:
            regime = (rng.random(R)[:, None] > cum[regime]).sum(1).clip(0, 2)
        hit = rng.random(R) < lam; kind = rng.choice(len(SHOCK_KEYS), R, p=w); oneoff = np.zeros(R)
        if hit.any():
            i = np.where(hit)[0]; rem[i, kind[i]] = np.maximum(rem[i, kind[i]], dur_k[kind[i]]); oneoff[i] = one_k[kind[i]]
            np.add.at(shock_count, kind[i], 1)
        act = rem > 0
        dm = np.prod(np.where(act, dm_k, 1.0), 1); cm = np.prod(np.where(act, cm_k, 1.0), 1); fm = np.prod(np.where(act, fm_k, 1.0), 1)
        rem = np.maximum(rem - 1, 0)
        if cycles: dm = dm * rmult[regime]
        if seasonality:
            cal, yr = t % 12, P.START_YEAR + t // 12
            if 5 <= cal <= 7: dm = dm * summer
            if P.RAMADAN_MONTH.get(yr) == cal: dm = dm * ramadan
        # ---- competitor reaction ----
        cust = state == 2; n_cust = cust.sum(1)
        provoked = (n_cust / np.maximum(potential, 1e-9) > COMP_SHARE) & (comp_left <= 0) & (rng.random(R) < COMP_PROB)
        comp_left = np.where(provoked, COMP_MONTHS, comp_left); comp_count += provoked
        comp_on = comp_left > 0; comp_left = np.maximum(comp_left - 1, 0)
        dm = dm * np.where(comp_on, .8, 1.0); cm = cm * np.where(comp_on, 1.25, 1.0)
        # ---- experience and leaving ----
        util = n_cust / cap_agents
        congestion = np.where(util > .9, .15, 0.0)
        sat_eff = sat - congestion[:, None] - np.where(comp_on, .1, 0)[:, None]
        p_leave = np.clip(churn[:, None] * (1.5 - sat_eff) * cm[:, None], 0, 1)
        leaving = cust & (U() < p_leave)
        unhappy = leaving & (sat_eff < .4)
        state[leaving] = 3; unhappy_until[unhappy] = t + 3
        src["left"] += leaving.sum(1); src["unhappy_left"] += unhappy.sum(1)
        cust = state == 2; n_cust = cust.sum(1)
        # ---- hearing about you ----
        good = cust & (sat > .6); bad = unhappy_until >= t
        n_pos = np.zeros((R, N), dtype=np.int8); n_neg = np.zeros((R, N), dtype=np.int8)
        for j in range(nb.shape[1]):  # count happy and unhappy friends, one friend slot at a time
            n_pos += good[:, nb[:, j]]; n_neg += bad[:, nb[:, j]]
        heard_wom = U() < pw_tab[rows, n_pos]
        heard_mk = U() < np.clip(d["p"][:, None] * aware_ramp * mk_weight[None, :], 0, 1)
        unaware = state == 0; said_no = state == 1
        cand = (unaware & (heard_mk | heard_wom)) | (said_no & heard_wom)
        # ---- deciding ----
        p_now = pbuy * dm[:, None].astype(np.float32) * neg_tab[n_neg] * np.where(said_no, np.float32(.5), np.float32(1))
        buys = cand & (U() < np.clip(p_now, 0, .95))
        state[cand & ~buys] = 1
        # ---- capacity ----
        room = np.maximum(cap_agents - n_cust, 0); n_buy = buys.sum(1)
        accept_p = np.where(n_buy > 0, np.minimum(1, room / np.maximum(n_buy, 1)), 1)
        accepted = buys & (U() < accept_p[:, None])
        excess = accepted.sum(1) - np.floor(room).astype(int)
        for r_ in np.where(excess > 0)[0]:  # never exceed capacity: turn away the surplus at random
            drop = rng.choice(np.flatnonzero(accepted[r_]), int(excess[r_]), replace=False); accepted[r_, drop] = False
        turned = buys & ~accepted; state[turned] = 1; src["turned_away"] += turned.sum(1)
        state[accepted] = 2
        sat = np.where(accepted, np.clip(S[:, None] + rng.standard_normal((R, N), dtype=np.float32) * .15, 0, 1), sat)
        via_wom = accepted & heard_wom
        src["word_of_mouth"] += via_wom.sum(1); src["marketing"] += (accepted & ~heard_wom).sum(1)
        # ---- money ----
        cust = state == 2; n_new = accepted.sum(1)
        revenue = (cust * pop["arpu"][None, :]).sum(1) * arpu_mult * scale
        profit = revenue * (1 - vp) - d["fixed"] * fm - n_new * scale * d["cac"] - oneoff * d["fixed"]
        cash = cash + profit; npv = npv + profit / (1 + r_month) ** (t + 1); low = np.minimum(low, cash)
        payback = np.where(np.isinf(payback) & (cash >= 0), t + 1, payback)
        op_be = np.where(np.isinf(op_be) & (profit > 0) & (t > 0), t + 1, op_be)
        paths["cash"][:, t] = cash; paths["customers"][:, t] = cust.sum(1) * scale; paths["revenue"][:, t] = revenue; paths["profit"][:, t] = profit
        paths["unaware"][:, t] = (state == 0).sum(1) * scale; paths["said_no"][:, t] = (state == 1).sum(1) * scale; paths["left"][:, t] = (state == 3).sum(1) * scale
        if journeys:
            hist0[t] = state[0]
            newly = accepted[0] & (when0 < 0); when0[newly] = t; how0[newly] = np.where(via_wom[0][newly], 2, 1)
            left_unhappy0 |= unhappy[0]

    peak_need = -np.minimum(low, 0)
    out = dict(runs=R, horizon=T, inputs=d, npv=npv, payback=payback, op_breakeven=op_be, peak_need=peak_need, final_cash=cash,
               final_customers=paths["customers"][:, -1], shock_count=dict(zip(SHOCK_KEYS, shock_count.tolist())),
               p_payback=float(np.mean(np.isfinite(payback))))
    out["ruin"] = (peak_need > budget) if budget else np.zeros(R, dtype=bool)
    out["p_ruin"] = float(np.mean(out["ruin"]))
    out["paths"] = paths if keep_paths else None
    tot = src["marketing"] + src["word_of_mouth"]
    out["abm"] = dict(agents=int(N), people_per_agent=float(scale), friends_per_agent=K_FRIENDS,
                      wom_share=float(np.median(src["word_of_mouth"] / np.maximum(tot, 1))),
                      turned_away=float(np.median(src["turned_away"]) * scale),
                      unhappy_left_share=float(np.median(src["unhappy_left"] / np.maximum(src["left"], 1))),
                      competitor_reactions=float(np.mean(comp_count)), runs_with_competitor_reaction=float(np.mean(comp_count > 0)),
                      acquired=float(np.median(tot) * scale))
    if journeys:
        out["abm"]["journeys"] = journeys_text(pop, hist0, how0, when0, left_unhappy0, rng)
    return out


def _month(t):
    return f"{['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][t % 12]} {P.START_YEAR + t // 12}"


def journeys_text(pop, hist, how, when, left_unhappy, rng):
    """Six example customer stories from one simulated run."""
    T = hist.shape[0]; final = hist[-1]
    stayed = np.where((final == 2) & (when >= 0))[0]
    left_bad = np.where((final == 3) & left_unhappy)[0]
    left_ok = np.where((final == 3) & ~left_unhappy & (when >= 0))[0]
    said_no = np.where(final == 1)[0]
    picks = []
    stayed = stayed[np.argsort(when[stayed])][: max(2, len(stayed) // 3)]  # prefer early, loyal customers
    for group, n in ((stayed, 2), (left_bad, 1), (left_ok, 1), (said_no, 2)):
        if len(group): picks += list(rng.choice(group, min(n, len(group)), replace=False))
    out = []
    for i in picks:
        h = hist[:, i]; who = pop["desc"][i]; steps = []
        if when[i] >= 0:
            steps.append(f"heard about you {'from a friend' if how[i] == 2 else 'through your marketing'} and bought in {_month(when[i])} (about AED {pop['arpu'][i]:,.0f} a month)")
            lt = np.where(h == 3)[0]
            if len(lt): steps.append(f"left in {_month(lt[0])}" + (" after a bad experience, and warned friends" if left_unhappy[i] else ""))
            else: steps.append("is still a customer at the end")
            kind = "left unhappy" if left_unhappy[i] else "left" if len(lt) else "stayed"
        else:
            first = np.where(h == 1)[0]
            steps.append(f"heard about you in {_month(first[0])} but did not buy" if len(first) else "never heard about you")
            steps.append(f"willing to pay about AED {pop['wtp'][i]:,.0f} a month against your price")
            kind = "said no"
        out.append(dict(who=who, kind=kind, story="; ".join(steps) + "."))
    return out
