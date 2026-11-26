"""Plain-language explanations, with a UAE example, for the business terms used in the app."""
import streamlit as st

TERMS = {
    "ARPU": ("Average spend per customer per month: what one active customer pays you in a typical month.",
             "A gym member paying AED 350 a month has an ARPU of AED 350. A café regular spending AED 30 three times a week has an ARPU of about AED 390."),
    "Variable cost (%)": ("The share of each sale you spend to make that sale: ingredients, stock, packaging, delivery-app commission, card fees.",
                          "If a AED 50 meal costs AED 15 in food and the delivery app takes AED 12.50, variable cost is 55%."),
    "Fixed costs": ("Costs you pay every month even with zero customers: rent, salaries, visas, licence (spread monthly), software.",
                    "Rent AED 12,000 + two staff AED 14,000 + licence and software AED 2,000 = AED 28,000 fixed a month."),
    "Setup cost": ("One-off money spent before opening: trade licence, fit-out, equipment, deposits, launch marketing.",
                   "Licence AED 25,000 + fit-out AED 120,000 + equipment AED 60,000 = AED 205,000 setup."),
    "CAC": ("Customer acquisition cost: what you spend on marketing and sales to win one paying customer.",
            "AED 3,000 on Instagram ads brings 40 paying customers, so CAC is AED 75."),
    "Churn": ("The share of your customers who stop buying each month.",
              "You start the month with 200 members and 10 cancel: churn is 5% a month."),
    "Capacity": ("The most customers you can serve at once with your space, staff and equipment.",
                 "A studio with 6 classes a day of 12 people, members coming twice a week, can serve about 250 members."),
    "Break-even": ("The point where money coming in covers all monthly costs, so the business stops losing money each month.",
                   "With AED 28,000 fixed costs and AED 140 left from each customer after variable costs, you need 200 customers to break even."),
    "Payback": ("The month when all the money you put in (setup + early losses) has been earned back.",
                "You spend AED 300,000 before profits start; profits of AED 25,000 a month pay that back in 12 months."),
    "Cash runway": ("How many months your budget lasts before you run out of cash, if things go badly.",
                    "AED 500,000 budget, losing AED 40,000 a month: about 12 months of runway."),
    "NPV": ("Net present value: all future profits minus all costs, with later money counted a bit less than money today. Above zero means the plan creates value.",
            "Earning AED 100,000 in three years is worth less than AED 100,000 today, so NPV discounts it."),
    "Chance of running out (budget risk)": ("The share of simulated futures in which you would need more cash than your budget.",
                                           "20% means: in 1 of every 5 simulated futures you would need to find extra money."),
    "TAM / SAM / SOM": ("TAM: all spending in the category. SAM: the part you can reach (place, type of customer). SOM: what you can realistically win.",
                        "All fitness spending in the UAE (TAM) > women's fitness in Sharjah (SAM) > what one studio can win (SOM)."),
    "Mainland / Free zone": ("Mainland licences (from the emirate's economic department) let you trade anywhere in the UAE. Free-zone licences are often cheaper and faster but limit trading outside the zone.",
                             "A café serving walk-in customers in Jumeirah needs a mainland licence; a software company selling online often uses a free zone."),
    "Conversion rate": ("The share of people who take the step you want, for example visitors who sign up or buyers who pay.",
                        "500 people see your page and 25 sign up: 5% conversion."),
    "Repeat purchase rate": ("The share of last month's customers who bought again this month.",
                             "80 of last month's 100 customers ordered again: 80% repeat rate."),
    "Hypothesis": ("A testable statement about your business with a number that would prove it right or wrong.",
                   "\"At least 30% of parents we interview will say finding a good Arabic tutor is a top-3 problem.\""),
    "Beachhead segment": ("The one group of customers you serve first because they need you most and are easiest to reach. You expand once you win them.",
                          "A tutoring app starts with Emirati parents in Abu Dhabi whose children are failing Arabic, before targeting all parents."),
    "Say-do gap": ("People say they would buy far more often than they actually do. The app discounts stated interest before using it.",
                   "Of 100 people who say \"yes, I'd buy\", typically fewer than half actually pay when asked to."),
    "Validation score": ("A 0-100 summary of three parts: market attractiveness, customer appeal (simulated) and financial viability. It is capped at 49 when the plan misses your own money limits.",
                         "Strong market (80) and appeal (70) but payback too slow: the score shows 49, not 75."),
    "Safety standard": ("A plan counts as safe when at least 6 in 10 simulated futures pay back within your time limit. You choose the time; the standard is fixed so plans are comparable.",
                        "Limit 36 months: if 7 in 10 futures pay back by month 36, the plan passes."),
    "Simulated panel": ("Computer-generated customers drawn from UAE population patterns. Useful for spotting objections; never counted as evidence.",
                        "40 simulated office workers react to your offer; 6 say they would buy."),
    "Desk test": ("A check you can do alone, without talking to customers: competitor prices, supplier and rent quotes, search volumes, reviews, licence fees.",
                  "Phoning three landlords in Business Bay for rent quotes is a desk test of your fixed costs."),
    "Sensitivity": ("How much the answer changes when one input changes. Inputs the answer is sensitive to are the ones to check first.",
                    "If halving the buyers within reach drops the payback chance from 60% to 20%, the plan is sensitive to market reach."),
    "Evidence confidence": ("How much of the plan rests on real evidence (sales, behaviour, customer feedback, sources) rather than guesses. AI estimates and simulations add nothing to it.",
                            "A plan built only on typical figures scores 0%; adding a landing-page test and three supplier quotes raises it."),
}


def term(key):
    """Short text for a widget's help= tooltip."""
    t, ex = TERMS[key]
    return f"{t}\n\nExample: {ex}"


def expander(keys, title="What do these terms mean?"):
    with st.expander(title):
        for k in keys:
            t, ex = TERMS[k]
            st.markdown(f"**{k}**: {t}  \n<span class='muted'>Example: {ex}</span>", unsafe_allow_html=True)


def page():
    st.header("Glossary")
    st.markdown('<p class="muted">Every business term used in ValidateUAE, in plain words with a UAE example.</p>', unsafe_allow_html=True)
    q = st.text_input("Search", placeholder="e.g. churn")
    for k, (t, ex) in TERMS.items():
        if q and q.lower() not in (k + t).lower(): continue
        with st.container(border=True):
            st.markdown(f"**{k}**  \n{t}  \n<span class='muted'>Example: {ex}</span>", unsafe_allow_html=True)


ALIASES = {"TAM": "TAM / SAM / SOM", "SAM": "TAM / SAM / SOM", "SOM": "TAM / SAM / SOM", "NPV": "NPV", "CAC": "CAC", "ARPU": "ARPU", "churn": "Churn",
           "payback": "Payback", "break-even": "Break-even", "break even": "Break-even", "evidence confidence": "Evidence confidence",
           "beachhead segment": "Beachhead segment", "validation score": "Validation score", "safety standard": "Safety standard",
           "simulated panel": "Simulated panel", "desk test": "Desk test", "fixed costs": "Fixed costs", "setup cost": "Setup cost",
           "budget risk": "Chance of running out (budget risk)", "conversion": "Conversion rate", "hypothesis": "Hypothesis", "sensitivity": "Sensitivity"}


def gloss(text_html, limit=None):
    """Underline known terms in already-escaped HTML and show their plain definition on hover (first use of each)."""
    import html as _h, re
    out = text_html; done = set()
    for word, key in sorted(ALIASES.items(), key=lambda kv: -len(kv[0])):
        if key in done or key not in TERMS: continue
        pat = re.compile(r"(?<![\w>/\"=-])(" + re.escape(word) + r")(?![\w<])", re.I if word.islower() else 0)
        m = pat.search(out)
        if not m: continue
        # never inside a tag or an existing abbr
        before = out[:m.start()]
        if before.count("<") > before.count(">") or before.rfind("<abbr") > before.rfind("</abbr>"): continue
        tip = _h.escape(TERMS[key][0], quote=True)
        out = out[:m.start()] + f'<abbr class="gl" title="{tip}">{m.group(1)}</abbr>' + out[m.end():]
        done.add(key)
    return out
