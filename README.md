# ⚡ Power Outage Multi-Agent System

A proof-of-concept **multi-agent system (MAS)** that simulates how an electricity
utility — Ceylon Electricity Board (CEB), Sri Lanka — could triage, diagnose, and
respond to power-outage complaints using a hierarchy of cooperating AI agents.

Built for the **Generative AI module, University of Moratuwa.**

## Overview

Customer complaints flow through three tiers of agents. LLM-backed agents diagnose
faults and craft customer replies, while a central coordinator handles routing,
crew negotiation, and system-wide crisis detection. A FastAPI backend hosts the
shared agent instances; two separate Streamlit apps provide a customer chat portal
and an operations dashboard.

## Architecture

    Customer Portal (Streamlit)        Management Dashboard (Streamlit)
            │                                      │
            └──────────────► FastAPI Backend ◄─────┘
                                  │
              ┌───────────────────┼───────────────────┐
        Tier 1                 Tier 2                Tier 3
   Customer Support  →   Coordinator Agent   →   Technical Fault Agents
        Agent          (router / broker /        (one per area:
                        negotiator)               Colombo-07, Negombo,
                                                  Kandy, Galle, Matara)

- **Tier 1 – Customer Support Agent** — intakes complaints, dispatches to the
  coordinator, and turns technical reports into warm, jargon-free customer messages.
- **Tier 2 – Coordinator Agent** — priority-queue routing, crew-allocation
  negotiation, butterfly-effect stress propagation, and grid-crisis detection.
- **Tier 3 – Technical Fault Agents** — one per geographic zone; produce structured
  JSON fault diagnoses with a confidence score.

## MAS Concepts Demonstrated

| Concept | Implementation |
|---|---|
| **Communication** | Typed `AgentMessage` objects on a shared, observable `MessageBus` |
| **Coordination** | `PriorityQueue` routing — critical faults processed before routine ones |
| **Negotiation** | Crew allocation with reallocation from adjacent areas, then escalation |
| **Butterfly Effect** | Fault stress propagates to geographically adjacent areas |
| **Emergent Properties** | System auto-declares a `GRID_CRISIS` when ≥3 concurrent high-severity faults |
| **Uncertainty** | Agents return a `confidence_score`; low-confidence diagnoses are flagged |
| **Goal-Directed Behaviour** | Per-agent `goal_stats` (ack latency, routing accuracy, avg confidence) |

## Tech Stack

- **Python** — agent logic with threading for concurrent complaint processing
- **FastAPI + Uvicorn** — shared backend exposing REST endpoints
- **Streamlit** — customer portal and management dashboard (separate apps)
- **OpenAI API** (`gpt-4o-mini`) — fault diagnosis and customer-response generation,
  with hardcoded fallbacks so the demo always works offline

## Project Structure

| File | Purpose |
|---|---|
| `data.py` | Grid data: areas, faults, customers, adjacency, crew capacity |
| `agents.py` | Three-tier agent classes + MessageBus |
| `backend.py` | FastAPI backend hosting shared agent instances |
| `customer_app.py` | Streamlit customer chat portal (port 8501) |
| `management_app.py` | Streamlit operations dashboard (port 8502) |
| `architecture.html` | Standalone architecture diagram |
| `requirements.txt` | Python dependencies |

## Setup & Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your OpenAI API key (in a .env file)
echo "OPENAI_API_KEY=sk-..." > .env

# 3. Start the backend
python backend.py                       # http://localhost:8000

# 4. Start the UIs (in separate terminals)
streamlit run customer_app.py    --server.port 8501
streamlit run management_app.py  --server.port 8502
