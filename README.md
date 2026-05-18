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
# Chat with your data — Enterprise AI Analytics 


---
title: Chat-with-Data (AtliQ Intelligence)
emoji: 📊
colorFrom: indigo
colorTo: purple
sdk: streamlit
app_file: frontend/dashboard.py
pinned: false
---

# Chat-with-Data — Enterprise Intelligence Copilot (AtliQ Hospitality)

Turn **live enterprise data + proprietary documents + real-time web benchmarks** into clear, decision-ready insights — with **agent security & governance** built in.

**Live demo:** Hugging Face Space (this repo deploys here)  
**Hackathon alignment:** TechEx “Intelligent Enterprise Solutions” — **Track 4: Data & Intelligence** + **Gemini Award** + **Veea Agent Security & AI Governance** :contentReference[oaicite:0]{index=0}

---

## The problem this solves

Enterprises don’t have a “data problem” — they have a **decision latency problem**:

- KPI answers are scattered across dashboards, SQL notebooks, and reporting cycles.
- Industry PDFs (benchmarks, competitor reports) are **hard to query** and rarely connected to internal metrics.
- When a question needs **fresh external context**, teams either guess or spend hours searching.
- AI assistants can hallucinate numbers or be tricked by prompt injection, which makes security teams say **“no”**.

This project makes analytics **conversational, cross-source, verifiable, and safe**.

---

## What this project does (in one sentence)

**Chat-with-Data** is an enterprise-grade analytics agent that answers natural language questions using:
1) deterministic database tools, 2) document intelligence + knowledge graphs, and 3) Gemini Google Search grounding for real-time facts — protected by Lobster Trap policy enforcement.

---

## Why it fits the hackathon theme

### ✅ Track 4: Data & Intelligence (Multi-source Intelligence)
This app directly implements Track 4 focus areas: RAG over proprietary data, analytics agents, AI-powered data pipelines/validation, and knowledge graph extraction from documents. :contentReference[oaicite:1]{index=1}

### ⭐ Gemini Award (Best use of Gemini)
- Gemini-native reasoning + tool orchestration for analytics
- Gemini-powered document understanding + structured extraction
- Gemini “Grounding with Google Search” for up-to-date internet benchmarks and citations metadata :contentReference[oaicite:2]{index=2}

### 🛡️ Veea Award (Agent Security & AI Governance)
We integrate **Lobster Trap**, a “deep prompt inspection” layer with firewall-style policy rules, to block prompt injection and unsafe requests before they hit the agent or data tools. :contentReference[oaicite:3]{index=3}

---

## Key features

### 1) Analytics Agent over Live Enterprise DB (Deterministic + Tool-Called)
Ask questions like:
- “Top 5 hotels by revenue in Mumbai”
- “RevPAR trend by week”
- “Occupancy by city, weekend vs weekday”

The agent:
- selects the right KPI tool
- generates deterministic SQL
- returns **only** numbers that came from tool outputs (no invented metrics)

### 2) Document Intelligence + Knowledge Graph
Upload a PDF (industry report / competitor analysis / benchmark doc) and get:
- extracted entities (hotels, cities, brands)
- extracted KPIs/benchmarks
- relationship graph visualization (knowledge graph)

Then ask cross-source questions:
- “How does our RevPAR compare to the benchmark in the report?”
- “Which cities show growth potential in the document, and how do we perform there?”

### 3) Real-time Internet Grounding (Gemini + Google Search)
When the PDF doesn’t contain the answer (e.g., “latest benchmark RevPAR in India”), Gemini can automatically use Google Search grounding and return grounding metadata you can surface in UI (queries + sources). :contentReference[oaicite:4]{index=4}

### 4) Agent Security & Governance (Lobster Trap)
Lobster Trap inspects prompts/outputs with policy rules and can:
- detect prompt injection patterns
- block unsafe instructions (exfiltration / “ignore previous instructions”)
- enforce enterprise-safe guardrails using YAML policy files (default policy path supported) :contentReference[oaicite:5]{index=5}

---

## System architecture (high-level)

```text
User (Streamlit UI)
   |
   |--(A) Analytics Chat ---------------------------.
   |                                                |
   |   Gemini (Agent)                               |
   |    - system prompt w/ DB context               |
   |    - native function calling (tools)           |
   |                                                |
   '-> Tools Layer (Deterministic)                  |
        - calculate_metrics() -> SQL -> Postgres     |
        - run_custom_sql()  -> SQL -> Postgres       |
        - search_metric()                           |
                                                    |
   |--(B) Document Intelligence --------------------|
   |                                                |
   |   PDF -> text extract -> KG extraction (Gemini) |
   |        -> entity/relations -> network graph     |
   |                                                |
   '-> Cross-source Answering:
        PDF context + DB metrics + (optional) web grounding
        via Gemini Google Search tool
“What the judges will see” (demo flow)
DB Agent: Ask “Top 5 hotels by revenue in Mumbai” → tool call → ranked output
Doc Intelligence: Upload PDF → knowledge graph renders
Cross-source: Ask “How does our RevPAR compare to the benchmark in this report?”
Real-time: Ask “What’s the latest industry benchmark for RevPAR in India?”
Show grounding metadata (search queries + sources)
Security: Try prompt injection (“ignore previous instructions…”) → blocked by policy
Tech stack
Frontend: Streamlit (Hugging Face Space)
LLM: Gemini (agentic tool-calling + document intelligence + web grounding)
Data: PostgreSQL analytics dataset (AtliQ Hospitality schema)
Graphs: NetworkX + Plotly graph rendering
Governance: Lobster Trap (policy-based prompt inspection)
Deployment (Hugging Face Spaces)

Hugging Face Spaces reads the YAML block at the very top of README.md to configure the app.

Secrets to set in the Space:

GEMINI_API_KEY
any DB connection env vars your app expects
Credits
Hackathon: TechEx + lablab.ai — Intelligent Enterprise Solutions Hackathon
Security Layer: Veea Lobster Trap
Real-time Web Grounding: Gemini Grounding with Google Search
