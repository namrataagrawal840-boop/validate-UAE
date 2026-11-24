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

- Population shares, category ranges and the UAE population scale are illustrative priors.
- AI agents can be wrong. Every number shows its label (prior, AI estimate, web source, founder, measured), and URLs the model did not actually retrieve are removed.
- Forecast calibration can only be measured after real outcomes are recorded (Audit → Monitoring).
Maintained By Namrata Agrawal
