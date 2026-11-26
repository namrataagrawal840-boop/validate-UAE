---
title: ValidateUAE
emoji: 🌿
colorFrom: purple
colorTo: green
sdk: docker
app_port: 8000
pinned: false
short_description: Validate a business idea for the UAE before you spend on it
---

# ValidateUAE

Test a business idea against the UAE market before you spend money on it.

ValidateUAE turns one decision, **launch, launch with changes, test first, or stop**, into ten small questions. Each question gets the simplest algorithm that fits. The answers are combined into one decision that respects the founder's cash budget and risk tolerance. AI agents (Claude with web search) research the idea and cite their sources. A blinded synthetic UAE market and an agent-based simulation, in which thousands of individual simulated customers hear, decide, recommend and leave while a competitor reacts and shocks hit, stress-test the plan.

> Decision support, not financial advice. Category priors and the synthetic population are illustrative planning values. Replace them with official statistics and real quotes before relying on the results.

## How it decides (the decision funnel)

| Step | Question | Algorithm | Passes on |
|---|---|---|---|
| 1 | What does the market look like? | Descriptive statistics on a blinded synthetic population (20,000 people) | Category buyers, spend, pain |
| 2 | Who is similar? | Gaussian mixture model, number of groups chosen by BIC | Segments, beachhead segment |
| 3 | Is anything unusual in the plan? | Isolation Forest against 3,000 comparable plans | Optimism flags |
| 4 | Will they buy? | Logistic choice model, calibrated by experiments | Probability of buying → market potential |
| 5 | How much will they spend? | Weighted regression (hurdle model: whether, then how much) | Revenue per customer |
| 6 | How long do customers stay, and when do you pay back? | Exponential survival; Kaplan-Meier | Lifetime value, payback timing |
| 7 | How many customers in future? | Agent-based simulation: customer agents on a small-world friend network, word of mouth, a reacting competitor, capacity congestion, Poisson shocks, Markov cycles, UAE seasons; replayed 100 times | Cash, NPV, payback, cash need per run |
| 8 | What are customers talking about? | TF-IDF + k-means topics, matched to the idea | Does real talk match the claimed problem? |
| 9 | Does our action change it? | Bayesian Beta-binomial tests, power analysis, price-elasticity fit | Calibration for stages 4 to 6 |
| 10 | What is the best allocation? | Linear programming (channels); 12 launch plans under the founder's limits | One recommended plan |

Around the funnel, the full business validation:
- **Validation score**: a weighted multi-criteria score (market, customers, competition, money, ease of use) with a confidence range that widens when evidence is thin
- **Idea at a glance**: a neutral brief, a Lean Canvas, the key assumptions and an AI judge rubric (problem severity, solution fit, differentiation, UAE feasibility, timing)
- **Market size check**: TAM, SAM and SOM, top-down (AI research) against bottom-up (agent simulation), flagged when they differ by more than 3×
- **Customer value**: jobs to be done, a Value Proposition Canvas, Kano features, the value gap, willingness to pay against your price, and ease of use (journey, Nielsen heuristics, SUS)
- **Improve my idea**: concrete changes (price, lean launch, beachhead segment, onboarding, membership, partners, and the critic's pivot ideas). Each is re-simulated and ranked, the best are recombined (one genetic-algorithm generation), and any change can be applied to the plan.
- **Real-world tests**: landing page, pricing at two prices, Van Westendorp survey, interviews, a pilot with NPS, A/B tests, a usability test with SUS, and real monthly sales with a Holt forecast. Every result updates the model.
- **Experiment kit**: landing page text, two ads for an A/B test, an interview script and survey questions
- **Self-consistency**: a second independent AI estimate of costs; ranges are widened when the two disagree
- **Copy summary** and **Save as PDF**

The decision then combines the stages: a plan passes when P(payback) ≥ the founder's minimum, P(cash need > budget) ≤ the founder's limit, and expected NPV > 0. Weak evidence turns any "launch" into "test first". Hard limits (licence blockers, capacity below break-even) override everything. A variance-based sensitivity analysis shows where the funnel leaks, kill criteria say when to stop, and an audit re-runs the analysis without the founder's claims, against an average business and under heavy shocks.

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for every formula and design choice.

### Why an agent-based simulation
An aggregate model moves one average customer number up and down. An agent-based model simulates each customer, so effects that matter in real markets appear by themselves:
- word of mouth spreading through friend networks
- unhappy customers warning their friends
- a full shop turning buyers away
- a competitor answering when you take share

It also produces concrete customer stories you can read. The market is replayed 100 times with different draws of the uncertain inputs, because a single run is only one possible story.

### Why the synthetic data cannot flatter the idea
The simulated market is generated only from the business type, the population structure and a random seed. It never reads the idea text, the founder's numbers or the AI's numbers. A test (`test_synthetic_market_ignores_the_idea`) proves this, and the Audit page shows the market's fingerprint. Uncertainty widens when nothing is measured, and the tool never says "launch" on priors alone.

## Get an Anthropic API key (for the AI agents)

The site works without a key (it uses category priors), but the AI research agents need one.

1. Go to **https://console.anthropic.com** and create an account.
2. Open **Billing** and add a small amount of credit. Check current prices at https://www.anthropic.com/pricing. Each analysis makes about 8 model calls, including web searches.
3. Open **API keys** → **Create key**, name it `validate-uae`, and copy it. It is shown only once.
4. Never paste the key into the code or commit it. Put it in your hosting provider's secret settings (below) or in a local `.env` file, which is git-ignored.

## Competition analysis

The **Competition** tab shows who already does the same or a very similar thing. Competitors come from three places: ones you type in (on the start form or the tab), real UAE businesses the competition agent finds on the web with links (needs an API key), and typical competitor types for the category when neither is available. Each competitor gets a TF-IDF similarity to your idea, a price-closeness score and a threat score (0-100). The tab also shows a positioning map (price vs similarity), a feature comparison with your edge and the table stakes you are missing, a price benchmark and the five forces. Named competitors raise rivalry and lower differentiation, which feed the buying model and make the simulated competitor react more often.

## The workspace (Streamlit app)

Sign in, then work through a project in this order:

| Section | What it does |
|---|---|
| **My projects** | Saved projects with their decision (Launch, Test first, Pivot, Stop), validation score and evidence confidence |
| **New project** | Four guided steps (idea, market and customer, money, existing evidence) with a progress bar, skippable optional questions and plain explanations of every business term |
| **Decision** | The recommendation and its reasons, validation score with its confidence range, strongest evidence, weakest assumptions, financial risks, missing evidence and the next five actions |
| **Evidence ledger** | Every claim with its source link or uploaded file, date, geography, evidence type, sample size, verification, confidence and limitations |
| **Validation lab** | Hypotheses with thresholds, generated plans, interview questionnaires, surveys, landing-page copy, recorded results and uploads, and expected vs actual |
| **Financials** | Three scenarios from the simulation (bad, typical, good), break-even, cash runway, a sensitivity tornado and money-related evidence gaps |
| **Market and customers** | Market insights and pain points, each labelled as your evidence, a web source, an AI estimate or a model estimate |
| **Competition**, **Improve my idea**, **What-if lab**, **Funnel**, **Audit**, **Assumptions and sources** | The ten-stage engine, unchanged |
| **Monitoring** | Real monthly revenue, expenses, customers, conversion, repeat purchases and CAC against the forecast frozen at launch |

**Market size (TAM, SAM, SOM).** Built step by step from published figures: residents of the emirate (Dubai Data and Statistics Establishment, SCAD, Sharjah Census 2025, FCSC), the adult and gender split, and the share who use this kind of service (for example gym membership, food-delivery apps, online shopping, private tutoring), valued at published spend per user. SAM applies the reach of one business, and SOM comes from the market simulation. Every step is tagged official, published, assumption, simulated or your figure, links to its source, and can be replaced. The figures live in `backend/app/public_data.py`.

**Social listening.** Collects real public posts about the problem, the category and competitors: YouTube comments (free `YOUTUBE_API_KEY`), Reddit (only with an approved Reddit app, `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`), AI web search across Reddit, Instagram, TikTok, Google reviews, X and forums (`ANTHROPIC_API_KEY`), or pasted comments and CSV exports from any platform. It scores sentiment (VADER plus rules for complaints and requests), finds themes (TF-IDF + k-means), counts complaint types and demand signals, adds a secondary-research record to the evidence ledger, and can rebuild the customer panel so simulated customers raise the complaints real people raise, each linking to a real example.

To get a free YouTube key: go to console.cloud.google.com, create a project, open **APIs & Services → Library**, enable **YouTube Data API v3**, then **Credentials → Create credentials → API key**, and add `YOUTUBE_API_KEY = "..."` to Streamlit's Secrets.

**Simple and Full views.** New projects open in Simple view: five pages (Idea, Market, Customers, Money, Decision), each starting with a one-sentence answer in plain words and linking to the full analysis. Full view has every section. The switch is at the top of the sidebar.

**Search demand.** How many people in the UAE search Google for related phrases each month, with buying-intent share, seasonality, trend and cost per click. Phrases are suggested from the idea (English and Arabic) and editable. Sources: DataForSEO for exact Google Ads volumes (`DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`; about $0.09 per lookup, $1 free credit), a free Google Keyword Planner export (ranges kept as ranges), and Google Trends via SerpApi (`SERPAPI_KEY`, free plan) or a downloaded Trends CSV for seasonality. It estimates what search could bring each month (each assumption labelled), compares ad cost per customer with your plan, and adds a secondary-research record to the evidence ledger.

**Customer panel (simulated).** With little or no research, run a panel of 20 to 150 simulated UAE customers drawn from the synthetic market. Each has an age, emirate, income, household, habits, problem severity and budget. They give feedback, answer a Van Westendorp price survey and debate the idea in a focus group, where opinions move by the Friedkin–Johnsen model. The panel then summarises the answers: who would buy, the main objections, what to change, which customers respond best and which questions to ask real customers. With an API key, Claude writes each person's opinions and you can chat with them. The idea comes from multi-agent simulators such as MiroFish, but the code is our own. The panel is labelled as simulated everywhere and never counts as evidence; its "Turn into hypotheses" button sends what it found to the Validation lab to be checked with real people.

**How evidence is treated.** Each ledger record is weighted by type (observed transactions 1.0, observed behaviour 0.85, direct feedback 0.6, secondary research 0.4, AI estimates 0, synthetic simulations 0), verification, confidence, geography, sample size and age. AI output and the simulation are shown for transparency but never raise confidence and are never presented as customer behaviour. A recommendation to launch needs at least 35% evidence confidence. Hypothesis status changes only when a result is recorded.

## Put it online with Streamlit (easiest, free)

1. **Create a free database** so accounts and projects survive restarts (Streamlit Cloud wipes local files when the app restarts). Go to [neon.tech](https://neon.tech), sign up, create a project and copy the connection string (it starts with `postgresql://`).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **Create app** → **Deploy a public app from GitHub**.
4. Repository: `namrataagrawal840-boop/validate-UAE`, branch: `main`, main file path: `streamlit_app.py`.
5. Optional: choose a custom address under **App URL**, for example `validate-uae`.
6. Open **Advanced settings**, pick Python 3.12 and paste into **Secrets**:
   ```toml
   DATABASE_URL = "postgresql://user:password@host/dbname?sslmode=require"
   SECRET_KEY = "any long random text"
   ANTHROPIC_API_KEY = "sk-ant-..."   # optional: AI web research
   ALLOW_SIGNUP = "true"              # set "false" once everyone has an account
   ```
7. Click **Deploy**. The first build takes a few minutes.

Without `DATABASE_URL` the app still works, using a local SQLite file, but accounts and projects disappear whenever Streamlit Cloud restarts the app. Every push to `main` redeploys automatically. Run it locally with `pip install -r requirements.txt` and `streamlit run streamlit_app.py`.

**Security.** Passwords are stored as salted PBKDF2-SHA256 hashes, and an account locks for 10 minutes after 5 failed attempts. Every database query for project data checks the owner, so one user can never open another user's project. Secrets come only from Streamlit secrets or environment variables. Uploaded files are limited to 5 MB and stored in the database. The FastAPI server behind the website requires a signed login token on every project endpoint.

## Put it online with a public link (Hugging Face Spaces, free)

Hugging Face Spaces runs this Docker app for free on 2 CPUs, enough for the agent-based simulation. This repository is set up so that **every push to GitHub updates the website automatically**.

**One-time setup (about 10 minutes):**

1. **Create a free account** at https://huggingface.co/join.
2. **Create the Space.** Go to https://huggingface.co/new-space:
   - Space name: `validate-uae`
   - SDK: **Docker** → **Blank**
   - Hardware: **CPU basic (free)**
   - Visibility: **Public** (anyone with the link can open it)

   Click **Create Space**.
3. **Add your Anthropic API key to the Space.** In the Space, go to **Settings → Variables and secrets → New secret**, with name `ANTHROPIC_API_KEY` and your key as the value. Without a key the site still works, using category priors.
4. **Create a Hugging Face access token.** Go to https://huggingface.co/settings/tokens → **Create new token** → type **Write** → copy it.
5. **Connect GitHub to the Space.** In this GitHub repository, go to **Settings → Secrets and variables → Actions**:
   - **New repository secret:** name `HF_TOKEN`, value = the token from step 4
   - **Variables tab → New repository variable:** name `HF_SPACE`, value = `your-hf-username/validate-uae`
6. **Deploy.** Go to the **Actions** tab → **Deploy to Hugging Face Space** → **Run workflow**. Hugging Face builds the app in about 5 to 10 minutes.

Your public link is `https://huggingface.co/spaces/your-hf-username/validate-uae`. There is also a direct, full-screen address: `https://your-hf-username-validate-uae.hf.space`.

After this, every push to `main` redeploys automatically. A free Space sleeps after a while without visitors; the first visit then takes a minute to wake it up, so open it a few minutes before a demo.

### Alternative: Render
On https://render.com, choose **New → Blueprint**, pick this repository and paste `ANTHROPIC_API_KEY`. Render's free plan has very little CPU, so `render.yaml` sets `SIM_MODE=fast` (fewer simulated agents and replays, same method). Expect slower analyses than on Hugging Face.

## Run it on your computer

```bash
# Backend (Python 3.11+)
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...      # optional
uvicorn app.main:app --reload --port 8000

# Frontend, in a second terminal (Node 20+)
cd frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev   # open http://localhost:3000
```

Or build everything into one container: `docker build -t validate-uae . && docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... validate-uae`, then open http://localhost:8000.

## Tests

```bash
cd backend && python -m pytest -q
```

44 tests cover the following:
- the synthetic market's independence from the idea, and its match to the population shares
- the agent simulation (capacity, word of mouth, unhappy customers leaving, competitor reaction, repeatability, customer stories)
- the aggregate cash model (repeatability, a hand-calculated break-even, shocks adding risk)
- Kaplan-Meier, the Isolation Forest, the BIC choice, the choice-model calibration, the linear programme, price elasticity, A/B tests and TF-IDF
- Bayesian updates from experiments, the budget hard limit
- Van Westendorp, SUS, NPS, the Holt forecast, the validation score, the variant ranking, recombination and apply, and self-consistency
- dropping URLs the AI did not actually find
- the full API flow

## Project structure

```
backend/app/
  priors.py          category priors for the UAE (illustrative, replace with official data)
  synth.py           blinded synthetic market + comparable plans
  funnel/            the ten stages: market_stages, checks, abm (agent-based simulation), simulate (helpers), decide,
                     validation (score, sizing, value, variants, Van Westendorp, SUS, NPS, Holt, experiment kit)
  compute.py         runs the funnel and the audit; deterministic
  agents.py          Claude agents with web search, cleaning and URL checks
  main.py            FastAPI: jobs, experiments, what-if, outcomes, calibration
backend/tests/       pytest suite
frontend/            Next.js site (static export served by the backend)
docs/METHODOLOGY.md  formulas and design choices
```

## Known limits

- The evidence ledger, validation lab, financial scenarios, decision dashboard and monitoring are in the Streamlit app. The Next.js website has login and per-user projects but still shows the original report tabs.
- There is no password reset or email verification (no email service is connected). An admin can delete a user row in the database.
- PostgreSQL support uses the same SQLAlchemy code as SQLite, but the automated tests run on SQLite.
- Uploaded files are not virus-scanned; only common document and image types up to 5 MB are accepted.

- Population shares, category ranges and the UAE population scale are illustrative priors.
- AI agents can be wrong. Every number shows its label (prior, AI estimate, web source, founder, measured), and URLs the model did not actually retrieve are removed.
- Forecast calibration can only be measured after real outcomes are recorded (Audit → Monitoring).
Maintained By Namrata Agrawal
