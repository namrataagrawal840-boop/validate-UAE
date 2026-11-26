import os
"""Category-level starting knowledge for the UAE.

Everything in this file is a *prior*: a starting belief used before any
idea-specific evidence exists. The numbers are illustrative planning ranges,
not sourced statistics. Replace them with official data (FCSC, Dubai Statistics
Center, Bayanat, broker reports) before relying on the results. Every value
shown in the app carries the label "Category prior" so users can tell.
"""

# Illustrative population structure. Replace with official statistics.
UAE_POPULATION = 12_060_000  # usual residents, FCSC 2025 (public_data.POPULATION["All UAE"]); converts simulated people to real counts
EMIRATES = [("Dubai", .37), ("Abu Dhabi", .30), ("Sharjah", .17), ("Ajman", .06),
            ("Ras Al Khaimah", .05), ("Fujairah", .03), ("Umm Al Quwain", .02)]
AGE_BANDS = [("18-24", .14, 21), ("25-34", .33, 30), ("35-44", .28, 40), ("45-54", .15, 50), ("55+", .10, 60)]
# Monthly household income, AED: lognormal (median, sigma) by band share
INCOME_BANDS = [("Lower", .35, 6_000), ("Middle", .40, 15_000), ("Upper", .20, 35_000), ("High", .05, 80_000)]

# Shock catalogue: monthly demand multiplier (dm), churn multiplier (cm),
# fixed-cost multiplier (fm), duration in months, relative frequency, one-off cost in months of fixed costs
SHOCKS = {
    "competitor": dict(label="A competitor opens nearby or online", dm=.70, cm=1.3, fm=1.0, months=6, weight=.30, one_off=0),
    "downturn":   dict(label="Local downturn / spending drop", dm=.75, cm=1.1, fm=1.0, months=8, weight=.15, one_off=0),
    "cost":       dict(label="Rent renewal or supplier price jump", dm=1.0, cm=1.0, fm=1.2, months=12, weight=.25, one_off=0),
    "regulation": dict(label="Licence or rule change", dm=.90, cm=1.0, fm=1.0, months=3, weight=.15, one_off=1),
    "viral":      dict(label="Viral moment / press coverage", dm=1.8, cm=.9, fm=1.0, months=2, weight=.15, one_off=0),
    "tourism":    dict(label="Tourism dip (fewer visitors, events cancelled)", dm=.85, cm=1.0, fm=1.0, months=3, weight=.10, one_off=0),
}
SHOCK_RATE = {0: 0.0, 1: 0.02, 2: 0.045, 3: 0.08}  # chance of a new shock each month
REGIMES = {"names": ["normal", "boom", "downturn"], "mult": [1.0, 1.12, .85],
           "P": [[.94, .03, .03], [.10, .88, .02], [.08, .02, .90]]}
RAMADAN_MONTH = {2027: 1, 2028: 1, 2029: 0, 2030: 0}  # approximate month index (0 = January)
START_YEAR = 2027
ANNUAL_DISCOUNT_RATE = 0.12  # planning assumption for NPV

SEASON = {"food": (0.90, 1.10), "physical": (0.85, 0.85), "online": (0.95, 1.00),
          "education": (0.70, 0.90), "fitness": (0.85, 0.80)}  # (summer, Ramadan) demand factors

# Business-type priors. Ranges are (low, likely, high).
# participation: share of adults who buy in this category at all.
# cat_spend: what a participating customer spends per month in the category today (AED).
# pain: Beta(a, b) for how unhappy people are with today's options (0..1).
# digital: how much the category is bought online (0..1).
TYPES = {
    "cafe": dict(label="Café or restaurant", season="food", participation=.70, cat_spend=(60, 140, 300), pain=(2.2, 3.0), digital=.35,
                 price=(70, 120, 180), var_pct=(28, 35, 45), fixed=(40_000, 55_000, 80_000), setup=(250_000, 350_000, 500_000),
                 cac=(25, 45, 90), churn=(8, 12, 18), capacity=(700, 1100, 1800), p=0.02, q=0.05, steps=3, open_months=4,
                 channels=[("Instagram and TikTok ads", 1.0, 120), ("Google Maps and search", .8, 80), ("Delivery apps", .7, 150),
                           ("Referral offers", .5, 40), ("Office and residential partnerships", .6, 60), ("Flyers and local events", 1.4, 50)]),
    "kitchen": dict(label="Cloud kitchen or food delivery", season="food", participation=.60, cat_spend=(80, 180, 380), pain=(2.4, 2.8), digital=.85,
                    price=(90, 150, 220), var_pct=(40, 48, 58), fixed=(25_000, 35_000, 50_000), setup=(90_000, 150_000, 250_000),
                    cac=(30, 55, 100), churn=(12, 18, 25), capacity=(450, 750, 1300), p=0.01, q=0.05, steps=3, open_months=3,
                    channels=[("Delivery apps (promoted listings)", .7, 250), ("Instagram and TikTok ads", 1.0, 120), ("Google search", .9, 60),
                              ("Referral offers", .5, 50), ("Corporate lunch partnerships", .6, 80), ("Influencer tastings", 1.3, 60)]),
    "retail": dict(label="Retail shop", season="physical", participation=.80, cat_spend=(80, 200, 450), pain=(2.0, 3.2), digital=.45,
                   price=(100, 200, 350), var_pct=(45, 55, 65), fixed=(30_000, 45_000, 70_000), setup=(150_000, 250_000, 400_000),
                   cac=(35, 65, 130), churn=(7, 10, 15), capacity=(500, 900, 1600), p=0.015, q=0.04, steps=3, open_months=3,
                   channels=[("Instagram ads", 1.0, 120), ("Google search and Maps", .8, 80), ("Marketplaces", .9, 150),
                             ("Mall events and pop-ups", 1.3, 60), ("Referral offers", .5, 40), ("Loyalty partnerships", .7, 50)]),
    "ecommerce": dict(label="Online store (e-commerce)", season="online", participation=.75, cat_spend=(70, 180, 400), pain=(2.0, 3.0), digital=.90,
                      price=(90, 180, 300), var_pct=(40, 50, 60), fixed=(20_000, 30_000, 50_000), setup=(30_000, 60_000, 120_000),
                      cac=(50, 90, 160), churn=(6, 9, 14), capacity=(400, 700, 1500), p=0.002, q=0.04, steps=4, open_months=2,
                      channels=[("Meta and TikTok ads", 1.0, 300), ("Google Shopping and search", .9, 200), ("Marketplaces", .8, 300),
                                ("Influencers", 1.2, 120), ("Email and referrals", .5, 80), ("Affiliate partners", .8, 100)]),
    "app": dict(label="App or software (subscription)", season="online", participation=.40, cat_spend=(20, 60, 150), pain=(2.2, 2.8), digital=.95,
                price=(25, 60, 120), var_pct=(8, 15, 25), fixed=(20_000, 35_000, 60_000), setup=(40_000, 80_000, 160_000),
                cac=(80, 150, 300), churn=(3, 5, 9), capacity=(800, 1500, 4000), p=0.002, q=0.05, steps=5, open_months=4,
                channels=[("Search ads", 1.0, 150), ("Social ads", 1.1, 200), ("Content and SEO", .6, 80),
                          ("Partnerships and resellers", .7, 100), ("Referral programme", .5, 60), ("App store optimisation", .8, 120)]),
    "services": dict(label="Professional or home services", season="physical", participation=.35, cat_spend=(200, 600, 1500), pain=(2.6, 2.6), digital=.55,
                     price=(300, 600, 1200), var_pct=(30, 40, 50), fixed=(15_000, 25_000, 40_000), setup=(20_000, 40_000, 80_000),
                     cac=(200, 400, 800), churn=(4, 6, 10), capacity=(60, 110, 200), p=0.01, q=0.05, steps=4, open_months=1,
                     channels=[("Google search ads", 1.0, 30), ("Booking platforms", .8, 40), ("Community groups and WhatsApp", .5, 20),
                               ("Building and community partnerships", .6, 25), ("Referral offers", .4, 20), ("Social ads", 1.2, 30)]),
    "education": dict(label="Education or tutoring", season="education", participation=.30, cat_spend=(200, 500, 1200), pain=(2.5, 2.7), digital=.60,
                      price=(250, 450, 800), var_pct=(35, 45, 55), fixed=(15_000, 25_000, 40_000), setup=(25_000, 50_000, 90_000),
                      cac=(100, 200, 400), churn=(5, 8, 12), capacity=(80, 140, 240), p=0.006, q=0.05, steps=4, open_months=2,
                      channels=[("Parent groups and WhatsApp", .5, 30), ("Google search ads", 1.0, 40), ("School partnerships", .6, 40),
                                ("Social ads", 1.1, 40), ("Referral offers", .4, 30), ("Education fairs", 1.3, 20)]),
    "fitness": dict(label="Fitness or wellness", season="fitness", participation=.40, cat_spend=(150, 350, 700), pain=(2.3, 2.9), digital=.40,
                    price=(200, 350, 550), var_pct=(10, 15, 25), fixed=(50_000, 70_000, 100_000), setup=(400_000, 600_000, 900_000),
                    cac=(80, 150, 300), churn=(4, 7, 11), capacity=(250, 400, 700), p=0.012, q=0.045, steps=3, open_months=5,
                    channels=[("Instagram ads", 1.0, 80), ("Free trial classes", .7, 60), ("Corporate wellness partnerships", .6, 50),
                              ("Google Maps and search", .8, 40), ("Referral offers", .4, 40), ("Community events", 1.2, 30)]),
}

ASSUMPTION_KEYS = ["price", "var_pct", "fixed", "setup", "cac", "churn", "capacity", "p", "q"]
NAMES = {"price": "Spend per customer per month", "var_pct": "Variable cost (% of revenue)", "fixed": "Fixed costs per month",
         "setup": "Setup cost (one-off)", "cac": "Cost to win one customer", "churn": "Monthly churn (%)",
         "capacity": "Most active customers you can serve", "p": "Bass p (pull from marketing)", "q": "Bass q (word of mouth)",
         "satisfaction": "Customer satisfaction (0-1)", "market": "Market potential (customers)", "arpu": "Revenue per customer"}
# Which direction of each assumption makes the plan look better (used to flag optimism)
OPTIMISTIC_DIRECTION = {"price": +1, "var_pct": -1, "fixed": -1, "setup": -1, "cac": -1, "churn": -1, "capacity": +1}

CHOICE_MODEL = dict(  # starting coefficients of the adoption model (no labels yet)
    b0=-3.6,        # baseline: most aware people do not switch (about 3% at a neutral offer)
    b_value=2.0,    # log(willingness to pay / price)
    b_pain=2.5,     # pain centred at 0.5
    b_fit=1.0,      # channel fit centred at 0.5
    b_comp=1.0,     # competitive position (-1..1)
)

# Small servers (for example Render's free plan) can set SIM_MODE=fast: fewer agents and replays, same method.
SIM_FAST = os.getenv("SIM_MODE", "").lower() == "fast"
RUNS_MAIN = 60 if SIM_FAST else 100
RUNS_OPTION = 15 if SIM_FAST else 25
MAX_AGENTS = 3000 if SIM_FAST else 5000
