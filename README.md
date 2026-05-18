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



# Chat-with-Data — Enterprise Intelligence Copilot (AtliQ Hospitality)

Turn **live enterprise data + proprietary documents + real-time web benchmarks** into clear, decision-ready insights — with **agent security & governance** built in.

**Hackathon alignment:** TechEx "Intelligent Enterprise Solutions" — **Track 4: Data & Intelligence** + **Gemini Award** + **Veea Agent Security & AI Governance**

---

## The Problem This Solves

Enterprises don't have a "data problem" — they have a **decision latency problem**:

- KPI answers are scattered across dashboards, SQL notebooks, and reporting cycles.
- Industry PDFs (benchmarks, competitor reports) are **hard to query** and rarely connected to internal metrics.
- When a question needs **fresh external context**, teams either guess or spend hours searching.
- AI assistants can hallucinate numbers or be tricked by prompt injection, which makes security teams say **"no"**.

This project makes analytics **conversational, cross-source, verifiable, and safe**.

---

## What This Project Does (In One Sentence)

**Chat-with-Data** is an enterprise-grade analytics agent that answers natural language questions using:

1. Deterministic database tools
2. Document intelligence + knowledge graphs
3. Gemini Google Search grounding for real-time facts

— all protected by **Lobster Trap** policy enforcement.

---

## Why It Fits the Hackathon Theme

### ✅ Track 4: Data & Intelligence (Multi-source Intelligence)
Directly implements Track 4 focus areas: RAG over proprietary data, analytics agents, AI-powered data pipelines/validation, and knowledge graph extraction from documents.

### ⭐ Gemini Award (Best Use of Gemini)
- Gemini-native reasoning + tool orchestration for analytics
- Gemini-powered document understanding + structured extraction
- Gemini **Grounding with Google Search** for up-to-date internet benchmarks and citation metadata

### 🛡️ Veea Award (Agent Security & AI Governance)
Integrates **Lobster Trap** — a deep prompt inspection layer with firewall-style policy rules — to block prompt injection and unsafe requests before they reach the agent or data tools.

---

## Key Features

### 1 · Analytics Agent over Live Enterprise DB
Ask questions like:
- *"Top 5 hotels by revenue in Mumbai"*
- *"RevPAR trend by week"*
- *"Occupancy by city, weekend vs weekday"*

The agent selects the right KPI tool → generates deterministic SQL → returns **only** numbers that came from tool outputs (no invented metrics).

---

### 2 · Document Intelligence + Knowledge Graph
Upload a PDF (industry report / competitor analysis / benchmark doc) and get:
- Extracted entities (hotels, cities, brands)
- Extracted KPIs / benchmarks
- Relationship graph visualization (knowledge graph)

Then ask cross-source questions:
- *"How does our RevPAR compare to the benchmark in the report?"*
- *"Which cities show growth potential in the document, and how do we perform there?"*

---

### 3 · Real-time Internet Grounding (Gemini + Google Search)
When the PDF doesn't contain the answer (e.g., *"latest benchmark RevPAR in India"*), Gemini automatically uses Google Search grounding and returns grounding metadata — search queries + verified sources — surfaced directly in the UI.

---

### 4 · Agent Security & Governance (Lobster Trap)
Lobster Trap inspects every prompt and output with policy rules to:
- Detect prompt injection patterns
- Block unsafe instructions (exfiltration / *"ignore previous instructions"*)
- Enforce enterprise-safe guardrails via YAML policy files

---

## System Architecture

```text
User (Streamlit UI)
   │
   ├─(A) Analytics Chat ──────────────────────────────┐
   │                                                   │
   │   Gemini Agent                                    │
   │    ├─ system prompt with DB context               │
   │    └─ native function calling (tools)             │
   │                                                   │
   └─► Tools Layer (Deterministic)                     │
         ├─ calculate_metrics()  →  SQL  →  Postgres   │
         ├─ run_custom_sql()     →  SQL  →  Postgres   │
         └─ search_metric()                            │
                                                       │
   ├─(B) Document Intelligence ───────────────────────┤
   │                                                   │
   │   PDF → text extract → KG extraction (Gemini)    │
   │       → entities / relations → network graph      │
   │                                                   │
   └─► Cross-source Answering:
         PDF context + DB metrics + optional web grounding
         via Gemini Google Search tool
```

---

## Demo Flow (What Judges Will See)

| Step | Action | Expected Output |
|------|--------|-----------------|
| 1 | Ask *"Top 5 hotels by revenue in Mumbai"* | Tool call → ranked result from DB |
| 2 | Upload a PDF industry report | Knowledge graph renders |
| 3 | Ask *"How does our RevPAR compare to the benchmark in this report?"* | Cross-source answer |
| 4 | Ask *"What's the latest industry benchmark for RevPAR in India?"* | Grounded answer + sources |
| 5 | Try *"Ignore previous instructions…"* | Blocked by Lobster Trap policy |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Streamlit (Hugging Face Space) |
| LLM | Gemini (tool-calling · document intelligence · web grounding) |
| Database | PostgreSQL — AtliQ Hospitality analytics schema |
| Graph Rendering | NetworkX + Plotly |
| Governance | Lobster Trap — policy-based prompt inspection |

---

## Deployment (Hugging Face Spaces)

Hugging Face Spaces reads the **YAML block at the very top of this README** to configure the app.


---

## Credits

- **Hackathon:** TechEx + lablab.ai — Intelligent Enterprise Solutions Hackathon
- **Security Layer:** Veea Lobster Trap
- **Real-time Web Grounding:** Gemini Grounding with Google Search
```
