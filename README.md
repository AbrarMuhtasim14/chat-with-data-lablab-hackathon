---
title: Chat With Data
emoji: 🏨
colorFrom: blue
colorTo: purple
sdk: streamlit
sdk_version: 1.39.0
app_file: frontend/dashboard.py
python_version: "3.11"
pinned: false
---

# Chat with Your Data — AtliQ Hospitality

> Enterprise analytics for hospitality, the way it should feel: ask in plain English, get an answer in seconds, backed by the same deterministic SQL the dashboard uses. Multi-page Streamlit app, Gemini-powered chat, knowledge-graph PDF intelligence, anomaly detection, and a real prompt-firewall.

<p align="center">
  <a href="https://huggingface.co/spaces/Abrar144/chat-with-data">
    <img src="https://img.shields.io/badge/🤗_Live_Demo-Hugging_Face_Spaces-yellow?style=for-the-badge" alt="Live Demo">
  </a>
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11">
  <img src="https://img.shields.io/badge/Streamlit-1.39-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/Postgres-Supabase-3FCF8E?style=for-the-badge&logo=supabase&logoColor=white" alt="Supabase">
  <img src="https://img.shields.io/badge/LLM-Gemini_2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini">
  <img src="https://img.shields.io/badge/Security-LobsterTrap-9b59b6?style=for-the-badge" alt="LobsterTrap">
</p>

<p align="center">
  <b>🎯 <a href="https://huggingface.co/spaces/Abrar144/chat-with-data">Try the live app →</a></b>
</p>

---

## What this is

A four-page Streamlit application for hotel chain analytics:

| Page | What it does |
|---|---|
| 🏨 **Dashboard** | Live KPI cards, weekly trends, weekend-vs-weekday, platform/city breakdowns. 13 metrics per property. |
| 💬 **Chat with Data** | Gemini agent answers natural language questions by calling deterministic SQL tools. 24 KPIs out of the box. |
| 🚨 **KPI Monitoring** | Four-layer anomaly detection: thresholds, week-over-week drops, consecutive declines, z-score outliers. Per-property health scores. |
| 📄 **Document Intelligence** | Upload a PDF, Gemini extracts a knowledge graph and benchmarks; ask questions across the doc *and* your live database. |
| 🔒 **Security Diagnostics** | Live status of the LobsterTrap prompt firewall with canary tests. |

All five pages share one **metrics engine** so the dashboard, chat answers, and monitoring page never disagree on a number.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                  STREAMLIT MULTI-PAGE FRONTEND                      │
│  Dashboard │ Chat │ KPI Monitoring │ Document Intel │ Security Diag │
└────────────┬─────────────────────────────────────────┬──────────────┘
             │                                          │
             ▼                                          ▼
   ┌───────────────────┐                    ┌──────────────────────┐
   │  METRICS ENGINE   │                    │   GEMINI AGENT       │
   │ utils/metrics_    │                    │   agents/agents.py   │
   │ engine.py         │                    │                      │
   │                   │                    │  Native function     │
   │ - Parallel fetch  │                    │  calling, 5-step     │
   │ - Cached          │                    │  tool loop           │
   │ - Single source   │                    │                      │
   │   of truth        │                    │  Tools:              │
   └─────────┬─────────┘                    │   • calculate_metrics│
             │                              │   • run_custom_sql   │
             ▼                              │   • search_metric    │
   ┌────────────────────────────────────────┴────────┐             │
   │       DETERMINISTIC SQL BUILDER                 │             │
   │       tools/tools.py                            │             │
   │                                                 │             │
   │   24 metrics → CTE-aware SQL → SQLAlchemy pool  │             │
   │   Both fact tables guarded against direct join  │             │
   └────────────────────┬────────────────────────────┘             │
                        │                                           │
                        ▼                                           │
                 ┌──────────────────┐                               │
                 │  SUPABASE        │                               │
                 │  Postgres        │                               │
                 │  (5 tables)      │                               │
                 └──────────────────┘                               │
                                                                    │
   ┌────────────────────────────────────────────────┐               │
   │  LOBSTER TRAP — PROMPT FIREWALL                │◄──────────────┘
   │  ./lobstertrap (Linux ELF) + configs/policy   │   pre-filter every
   │  Subprocess pre-check on every chat message    │   user prompt
   └────────────────────────────────────────────────┘
```

### Why this design

| Decision | Rationale |
|---|---|
| **Deterministic SQL builder** | LLMs write buggy SQL. We compile metrics from configs in Python — zero syntax errors for the 24 known KPIs. |
| **Two-path query strategy** | Standard KPIs go through the builder (100% reliable). Only ad-hoc rankings and correlations fall back to LLM-generated SQL. |
| **No direct join across fact tables** | `fact_bookings` (one row per booking) and `fact_aggregated_bookings` (one row per property × date × room) have different granularities. Direct joins multiply rows. CTEs handle cross-table metrics like RevPAR. |
| **Single shared metrics engine** | Dashboard, chat agent, and monitoring all import the same functions. The number you see in a KPI card is the same number the agent quotes. |
| **Native Gemini function calling** | Structured JSON tool calls beat ReAct text parsing on reliability and latency. |
| **Parallel metric fetches** | `ThreadPoolExecutor` runs the 6+ KPI queries in parallel via SQLAlchemy connection pool — first paint is ~1s instead of ~6s. |
| **Pre-filter security layer** | LobsterTrap inspects every user prompt before Gemini sees it. Prompt injection, PII probes, and malware requests are blocked at the gate. |

---

## Live demo

🤗 **[https://huggingface.co/spaces/Abrar144/chat-with-data](https://huggingface.co/spaces/Abrar144/chat-with-data)**

The Space is configured for free-tier CPU. Cold start takes ~30 seconds after extended idle.

---

## Project structure

```
chat-with-data-lablab-hackathon/
│
├── frontend/
│   ├── dashboard.py                       # entry: executive dashboard
│   └── pages/
│       ├── 02_Chat_with_Data.py           # Gemini-powered chat
│       ├── 03_KPI_Monitoring.py           # anomaly detection + health scores
│       ├── 04_Document_Intelligence.py    # PDF → knowledge graph + RAG
│       └── 05_Security_Diagnostics.py     # LobsterTrap canary tests
│
├── agents/
│   └── agents.py                          # Gemini function-calling pipeline
│                                          # + LobsterTrap subprocess wrapper
│                                          # + JSON verdict parser
│
├── tools/
│   └── tools.py                           # 24-metric SQL builder
│                                          # SQLAlchemy engine, CTE assembler
│
├── utils/
│   ├── config.py                          # env-first secret loader, schema map,
│   │                                      # metric library, business rules
│   ├── metrics_engine.py                  # shared API (parallelized fetches)
│   ├── document_processor.py              # PDF text + Gemini knowledge graph
│   └── gemini_client.py                   # OpenAI→Gemini tool schema converter
│
├── etl/
│   └── etl_pipeline.py                    # CSV → Raw DB → Clean DB
│                                          # day_type recompute (Fri+Sat = Weekend)
│                                          # post-ETL verification suite
│
├── prompts/
│   └── cot_prompts.py                     # chain-of-thought templates
│
├── configs/
│   └── default_policy.yaml                # LobsterTrap rules (ingress + egress)
│
├── lobstertrap                            # Linux prompt-firewall binary (Git LFS)
│
├── .streamlit/
│   └── config.toml                        # theme + headless server config
│
├── requirements.txt                       # slim deploy spec (~15 packages)
├── requirements.full.txt                  # full pip freeze backup
├── README.md
└── .gitattributes                         # routes lobstertrap through LFS
```

---

## Quick start

### Prerequisites

- Python **3.11**
- A **Supabase** Postgres instance (or any Postgres with the schema below)
- A **Gemini** API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### Local install

```bash
git clone https://github.com/AbrarMuhtasim14/chat-with-data-lablab-hackathon.git
cd chat-with-data-lablab-hackathon
git lfs pull                              # fetch the lobstertrap binary
python -m venv .venv
.venv\Scripts\activate                    # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Configure secrets

Create `.env` in the project root:

```ini
CLEAN_SUPABASE_DB_URI=postgresql://postgres.PROJECT_REF:PASSWORD@aws-1-REGION.pooler.supabase.com:6543/postgres
GEMINI_API_KEY=AIzaSy...
```

Use the **Supabase transaction pooler** URI (port `6543`), not direct (`5432`). The pooler keeps connection counts sane under load.

### Load data (first run only)

```bash
python etl/etl_pipeline.py
```

The ETL is idempotent — drops and recreates tables, then loads from `data/*.csv`, then runs a 7-check verification suite on `dim_date` (day_type spot-checks, week_no integrity, row counts).

### Launch

```bash
streamlit run frontend/dashboard.py
```

Open `http://localhost:8501`.

### Deploy to Hugging Face Spaces

The repo is already configured. The YAML front matter in `README.md` tells Spaces:

- `sdk: streamlit`
- `sdk_version: 1.39.0`
- `app_file: frontend/dashboard.py`
- `python_version: "3.11"`

Push to a Spaces git remote and add `CLEAN_SUPABASE_DB_URI` and `GEMINI_API_KEY` as secrets in the Space settings.

---

## Data model

### Tables and grains

| Table | Grain | Purpose |
|---|---|---|
| `dim_date` | one row per date | Calendar with `week_no` (TEXT), `mmm_yy`, `day_type` |
| `dim_hotels` | one row per `property_id` | Hotel master: name, category, city |
| `dim_rooms` | one row per `room_id` | Room class: Standard / Elite / Premium / Presidential |
| `fact_bookings` | one row per `booking_id` | Revenue, status, platform, ratings — **use for revenue, ADR, status** |
| `fact_aggregated_bookings` | one row per (property × date × room) | Capacity and successful bookings — **use for occupancy** |

### Critical business rules

- **Weekend** = Friday and Saturday (stakeholder definition, non-standard).
- **Revenue** always uses `revenue_realized` (net after cancellation adjustments). `revenue_generated` is gross.
- **Cancellations** retain 40% of `revenue_generated` for the hotel; no-shows retain 100%.
- **Ratings** of `0` mean "not rated" — averages must filter `WHERE ratings_given > 0`.
- **`week_no` is TEXT** — always quote as `'31'` not `31`.
- **Never direct-join** `fact_bookings` with `fact_aggregated_bookings`. CTEs only.

### Coverage

13 properties × 4 cities (Delhi, Mumbai, Hyderabad, Bangalore) × 92 days (May–July 2022) × 7 booking platforms.

---

## Metric catalog

24 metrics in three tiers, all defined in `utils/config.py` and compiled to SQL in `tools/tools.py`:

<details>
<summary><b>Base metrics</b> (6)</summary>

| Metric | Formula |
|---|---|
| `revenue` | `SUM(revenue_realized)` |
| `total_bookings` | `COUNT(booking_id)` |
| `total_capacity` | `SUM(capacity)` |
| `total_successful_bookings` | `SUM(successful_bookings)` |
| `average_rating` | `AVG(ratings_given) WHERE ratings_given > 0` |
| `no_of_days` | `COUNT(DISTINCT date)` |

</details>

<details>
<summary><b>Derived KPIs</b> (10)</summary>

| Metric | Description |
|---|---|
| `occupancy_pct` | Successful bookings ÷ capacity × 100 |
| `adr` | Revenue ÷ total bookings (Average Daily Rate) |
| `revpar` | Revenue ÷ capacity (cross-table CTE) |
| `realisation_pct` | Bookings that actually checked in |
| `cancellation_pct` | Bookings cancelled |
| `no_show_rate_pct` | Bookings where guests never showed |
| `dbrn` | Daily Booked Room Nights |
| `dsrn` | Daily Sellable Room Nights |
| `durn` | Daily Utilised Room Nights |
| `booking_pct_by_platform` / `_by_room_class` | Distribution share |

</details>

<details>
<summary><b>Week-over-Week metrics</b> (6)</summary>

`wow_revenue`, `wow_occupancy`, `wow_adr`, `wow_revpar`, `wow_realisation`, `wow_dsrn`

Each computes `((current_week / previous_week) - 1) × 100` using window functions on the `dim_date` join. The cross-table ones (`wow_revpar`) chain two CTEs.

</details>

---

## How the chat agent works

```
User: "What is the RevPAR for luxury hotels in Mumbai?"
  │
  ▼
┌─────────────────────────────────┐
│ 1. LobsterTrap pre-check        │  → ALLOWED (risk_score: 0)
└─────────────┬───────────────────┘
              ▼
┌─────────────────────────────────┐
│ 2. Load DB context              │  weeks, cities, latest_full_week
└─────────────┬───────────────────┘
              ▼
┌─────────────────────────────────┐
│ 3. Gemini call #1 with tools    │
│    System prompt includes:      │
│    - schema map                 │
│    - metric catalog             │
│    - business rules             │
│    - few-shot examples          │
└─────────────┬───────────────────┘
              ▼
   Gemini emits structured tool call:
   calculate_metrics({
     metrics: ["revpar"],
     filters: {city: "Mumbai", category: "Luxury"}
   })
              │
              ▼
┌─────────────────────────────────┐
│ 4. SQL builder compiles CTE:    │
│    WITH rev AS (...),           │
│         cap AS (...)            │
│    SELECT rev/cap AS revpar     │
└─────────────┬───────────────────┘
              ▼
┌─────────────────────────────────┐
│ 5. SQLAlchemy executes; result  │
│    sent back as function reply  │
└─────────────┬───────────────────┘
              ▼
┌─────────────────────────────────┐
│ 6. Gemini formats answer:       │
│    "RevPAR for luxury hotels    │
│     in Mumbai: ₹10,234..."      │
└─────────────────────────────────┘
```

Up to **5 tool-call iterations** per question. Most questions resolve in 1.

---

## Anomaly detection (KPI Monitoring page)

Four layers, all running in parallel via `ThreadPoolExecutor`:

```
Layer 1: THRESHOLD ALERTS
   Each KPI checked against configurable warning/critical levels.
   Example: Occupancy < 45% → 🔴 Critical

Layer 2: WEEK-OVER-WEEK DROPS
   Significant negative WoW % flagged.
   Example: Revenue −12% WoW → 🔴 Critical

Layer 3: CONSECUTIVE DECLINES
   3+ weeks of monotone-down trends.
   Example: ADR declined 4 weeks straight → 🔴 Critical

Layer 4: STATISTICAL OUTLIERS (z-score)
   Per-property deviation from portfolio mean.
   Example: Hotel X occupancy z = −2.3 → 🔴 Critical
```

### Property health score

```
score = 0.25 × occupancy_pct
      + 0.25 × revpar_normalized
      + 0.20 × average_rating_normalized
      + 0.15 × adr_normalized
      + 0.15 × realisation_pct

≥ 80   🟢 Healthy
60–79  🟡 Concern
< 60   🔴 Critical
```

---

## Document intelligence

Upload any PDF (industry report, market analysis, competitor benchmark). The page:

1. Extracts text via `pdfplumber` → `PyPDF2` fallback.
2. Sends the first 10k characters to Gemini with a structured-output prompt.
3. Gemini returns JSON: `{entities, kpis, benchmarks, insights, relationships}`.
4. NetworkX builds a graph; Plotly renders an interactive force-directed layout.
5. Benchmarks from the doc are matched (by metric name) against your live DB metrics — automatic gap analysis.
6. The chat box at the bottom answers cross-source questions ("How does our RevPAR compare to the industry benchmark?") using both the doc and the database, with optional Google Search grounding.

---

## Security: LobsterTrap prompt firewall

Every chat message goes through a subprocess call to `./lobstertrap inspect` **before** Gemini sees it.

### What it blocks

Per `configs/default_policy.yaml`, in priority order:

| Priority | Rule | Catches |
|--:|---|---|
| 100 | `block_prompt_injection` | "Ignore previous instructions", system-prompt extraction |
| 98 | `block_harm_violence` | Weapons, violence, dangerous substances |
| 96 | `block_malware_request` | Ransomware, exploits, offensive tooling |
| 94 | `block_phishing_fraud` | Phishing pages, scam emails |
| 92 | `block_data_exfiltration` | Encoded dumps, "email this DB to attacker.com" |
| 90 | `block_obfuscation_evasion` | Base64 / leet-speak / unicode dodges |
| 86 | `review_role_impersonation` | "You are admin", "act as DAN" → human review |
| 85 | `block_sensitive_paths` | `/etc/passwd`, `~/.ssh`, `.env` references |
| 82 | `block_pii_request` | "Give me all customer credit cards" |
| 80 | `block_dangerous_commands` | `rm -rf /`, `curl \| sh` (with risk threshold) |
| 70 | `review_high_risk` | Anything else scoring ≥ 0.6 |

### How it's wired

The Python wrapper in `agents/agents.py`:

1. Resolves the binary path and policy path.
2. Auto-`chmod +x` on the binary in case Git lost the executable bit (cross-platform safety).
3. Runs `subprocess.run([binary, "inspect", "--policy", policy, prompt], timeout=5)`.
4. Parses the JSON output:
   - `verdict` ∈ {`DENY`, `BLOCK`, `HUMAN_REVIEW`} → blocked
   - `risk_score` ≥ 0.6 → blocked
   - `[LOBSTER TRAP] Blocked` in `deny_message` → blocked
   - Otherwise → allowed
5. Falls back gracefully if the binary is missing, non-executable, or times out.

### Verifying it's working

The **Security Diagnostics** page runs three canaries — benign analytics, prompt injection, PII probe — and shows the binary's full JSON output. If you can read the policy verdict and risk score there, the firewall is alive.

---

## Performance

| Where | Latency | Notes |
|---|---|---|
| Dashboard first paint | ~1–2 s | 6 KPI queries in parallel via SQLAlchemy pool |
| Dashboard cached re-render | < 100 ms | `@st.cache_data(ttl=60)` keyed on filter tuple |
| KPI Monitoring first paint | ~1.5 s | 4 fetches × 6 trends in parallel (max_workers=4) |
| Chat single tool-call | 3–8 s | Bound by Gemini API + Supabase round-trip |
| Document KG extraction | 4–10 s | Bound by Gemini, depends on PDF size |
| LobsterTrap pre-check | 50–150 ms | Subprocess spawn + JSON parse |

### Pool configuration

```python
create_engine(
    uri,
    pool_pre_ping=True,
    pool_size=8,
    max_overflow=8,
    pool_recycle=300,
)
```

`pool_pre_ping` heals stale Supabase connections after the pooler closes them. `pool_recycle=300` proactively replaces connections older than 5 minutes.

---

## Tech stack

| Layer | Technology |
|---|---|
| **Frontend** | Streamlit 1.39 (multi-page) |
| **Charts** | Plotly Express + Plotly Graph Objects |
| **Database** | Supabase (managed Postgres), transaction pooler |
| **DB driver** | psycopg2-binary + SQLAlchemy 2.x engine |
| **LLM** | Gemini 2.5 Flash (function calling + Google Search grounding) |
| **PDF** | pdfplumber → PyPDF2 fallback |
| **Knowledge graph** | NetworkX + spring layout |
| **Security** | LobsterTrap CLI (Linux ELF) + YAML policy |
| **Concurrency** | `concurrent.futures.ThreadPoolExecutor` |
| **Deployment** | Hugging Face Spaces (Streamlit SDK), Streamlit Community Cloud |
| **VCS** | Git + Git LFS for the security binary |

---

## Local development tips

- **Where errors hide**: Streamlit swallows tracebacks for cached functions. If a chart goes blank, click the `⋮` menu → "Rerun" with the cache cleared.
- **DB connection issues**: most "tenant/user not found" errors mean the password in your URI is missing or has unencoded special characters. URL-encode `@` → `%40`, `#` → `%23`.
- **Module not found in Streamlit Cloud / Spaces**: pages add the project root to `sys.path` at the top of each file. If you add a new page, copy that snippet.
- **Testing the security layer locally on Windows**: the LobsterTrap binary is Linux-only. The wrapper falls back to "allow everything" on Windows. Use the diagnostics page on the deployed Space to verify it.

---

## Roadmap

- [ ] Conversation memory for multi-turn chat (currently stateless per question)
- [ ] LobsterTrap **egress** filtering — inspect Gemini's response before showing it
- [ ] LLM fallback chain (try Gemini → Claude → GPT-4 on quota errors)
- [ ] Per-session rate limiting in Streamlit
- [ ] CSV / Excel export of any chart or query result
- [ ] Scheduled daily anomaly digest by email
- [ ] Role-based access control (read-only vs analyst)

---

## Acknowledgements

Built for the **lablab.ai** hackathon. Dataset modeled on the AtliQ Hospitality case study; figures are illustrative.

LobsterTrap is included as a compiled binary; the policy in `configs/default_policy.yaml` is shipped as the default ruleset.

---

## License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  <i>Numbers should never lie to you. The same SQL powers the dashboard, the chat, and the alerts.</i>
</p>
