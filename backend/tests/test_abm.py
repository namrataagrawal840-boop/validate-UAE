import numpy as np
from app.funnel.abm import simulate_abm, friend_network, K_FRIENDS

N = 2000
SEG = np.repeat(np.arange(4), N // 4)


def pop(p=.15):
    order = np.lexsort((np.arange(N), SEG))
    return dict(p_buy=np.full(N, p), arpu=np.full(N, 150.), seg=SEG, wtp=np.full(N, 160.), desc=["Test agent"] * N, scale=10.,
                nbrs=friend_network(N, order, 1), market_base=1., arpu_base=150.)


INP = dict(market=(1, 1, 1), arpu=(150,) * 3, var_pct=(40,) * 3, fixed=(20000,) * 3, setup=(50000,) * 3, cac=(50,) * 3, churn=(8,) * 3,
           capacity=(3000,) * 3, p=(.01,) * 3, q=(.05,) * 3, satisfaction=(.6,) * 3)


def test_network_is_small_world_with_homophily():
    nb = pop()["nbrs"]
    assert nb.shape == (N, K_FRIENDS)
    same = (SEG[nb] == SEG[:, None]).mean()
    assert same > .8  # most friends are similar people, a few random links remain


def test_capacity_is_never_exceeded():
    s = simulate_abm({**INP, "capacity": (500,) * 3, "p": (.05,) * 3}, pop(.5), runs=20, shocks=3)
    assert s["paths"]["customers"].max() <= 500 + 10  # one agent = 10 people


def test_word_of_mouth_brings_customers():
    off = simulate_abm({**INP, "q": (0,) * 3}, pop(), runs=30, shocks=0, cycles=False, seasonality=False)
    on = simulate_abm({**INP, "q": (.15,) * 3}, pop(), runs=30, shocks=0, cycles=False, seasonality=False)
    assert on["abm"]["wom_share"] > 0 and off["abm"]["wom_share"] == 0
    assert on["paths"]["customers"][:, -1].mean() > off["paths"]["customers"][:, -1].mean()


def test_unhappy_customers_leave_more():
    happy = simulate_abm({**INP, "satisfaction": (.9,) * 3}, pop(), runs=30, shocks=0)
    sad = simulate_abm({**INP, "satisfaction": (.2,) * 3}, pop(), runs=30, shocks=0)
    assert sad["abm"]["unhappy_left_share"] > happy["abm"]["unhappy_left_share"]
    assert sad["paths"]["customers"][:, -1].mean() < happy["paths"]["customers"][:, -1].mean()


def test_more_buyers_more_customers_and_repeatable():
    a = simulate_abm(INP, pop(.05), runs=30, seed=3); b = simulate_abm(INP, pop(.05), runs=30, seed=3); c = simulate_abm(INP, pop(.3), runs=30, seed=3)
    assert np.array_equal(a["npv"], b["npv"])
    assert c["paths"]["customers"][:, -1].mean() > a["paths"]["customers"][:, -1].mean()


def test_journeys_are_told():
    s = simulate_abm(INP, pop(), runs=5)
    assert s["abm"]["journeys"] and all(j["story"] for j in s["abm"]["journeys"])


def test_competitor_reacts_to_a_big_share():
    s = simulate_abm({**INP, "p": (.1,) * 3}, pop(.6), runs=30)
    assert s["abm"]["runs_with_competitor_reaction"] > .5
