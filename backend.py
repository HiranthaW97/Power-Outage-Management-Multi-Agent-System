"""
backend.py — CEB MAS FastAPI Backend
Holds the single shared agent instances; both Streamlit UIs call this via HTTP.

Run:  python backend.py
      (or)  uvicorn backend:app --host 0.0.0.0 --port 8000 --reload

Endpoints
─────────
POST /complaints          Submit a new complaint
GET  /complaints          All complaints (with customer_message when resolved)
GET  /messages            All MessageBus messages (Communication)
GET  /activity-log        Agent activity log entries
GET  /status              Grid crisis, area stress, crew availability, agent goals
POST /demo                Fire 3 concurrent demo complaints
GET  /health              Liveness check
"""

import threading
import time

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents import CoordinatorAgent, CustomerSupportAgent, MessageBus

# ─────────────────────────────────────────────────────────────
#  Shared agent instances (one set, shared by both UIs via HTTP)
# ─────────────────────────────────────────────────────────────
bus            = MessageBus()
coordinator    = CoordinatorAgent(bus)
customer_agent = CustomerSupportAgent(coordinator, bus)


# ─────────────────────────────────────────────────────────────
#  Background drain: resolved complaints → customer_message
#  Replaces the Streamlit sync_from_coordinator() that used to
#  live in the UI layer.
# ─────────────────────────────────────────────────────────────
def _drain_loop():
    """
    Background thread: picks up resolved complaints from pending_responses,
    formats a customer-facing message via GPT, and writes it back to the registry.
    Wrapped in try/except so the thread never dies silently on any error.
    """
    while True:
        try:
            with coordinator._lock:
                pending = dict(coordinator.pending_responses)
                coordinator.pending_responses.clear()

            for cid, report in pending.items():
                try:
                    comp = coordinator.get_complaint(cid)
                    if comp:
                        msg = customer_agent.format_response(report, comp["customer_name"])
                        coordinator._update_status(
                            cid,
                            comp.get("status", "RESOLVED"),
                            {"customer_message": msg},
                        )
                except Exception as e:
                    # Per-complaint failure — log and continue with next complaint
                    print(f"[drain] Error formatting response for {cid[:8]}: {e}")
                    # Write a safe fallback so the customer still gets a reply
                    try:
                        coordinator._update_status(
                            cid,
                            "RESOLVED",
                            {"customer_message": (
                                "Dear customer, your complaint has been received and "
                                "our technical team is working to restore power. "
                                "We apologise for the inconvenience."
                            )},
                        )
                    except Exception:
                        pass

        except Exception as e:
            # Outer safety net — prevents the thread from dying on unexpected errors
            print(f"[drain] Unexpected error: {e}")

        time.sleep(0.5)


threading.Thread(target=_drain_loop, daemon=True).start()


# ─────────────────────────────────────────────────────────────
#  FastAPI app
# ─────────────────────────────────────────────────────────────
app = FastAPI(title="CEB MAS Backend", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ComplaintIn(BaseModel):
    customer_name: str
    area:          str
    message:       str


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "complaints": len(coordinator.get_all_complaints())}


@app.post("/complaints")
def submit_complaint(body: ComplaintIn):
    complaint = customer_agent.intake(
        customer_name = body.customer_name,
        area          = body.area,
        message       = body.message,
    )
    return complaint


@app.get("/complaints")
def get_complaints():
    return coordinator.get_all_complaints()


@app.get("/complaints/{complaint_id}")
def get_complaint(complaint_id: str):
    c = coordinator.get_complaint(complaint_id)
    return c if c else {"error": "not found"}


@app.get("/messages")
def get_messages():
    return [
        {
            "msg_id":    m.msg_id,
            "sender":    m.sender,
            "receiver":  m.receiver,
            "msg_type":  m.msg_type,
            "content":   m.content,
            "timestamp": m.timestamp,
            "priority":  m.priority,
        }
        for m in bus.get_all()
    ]


@app.get("/activity-log")
def get_activity_log():
    with coordinator._lock:
        return list(coordinator.activity_log)


@app.get("/status")
def get_status():
    return {
        "grid_crisis":    coordinator.grid_crisis,
        "crisis_areas":   coordinator.crisis_areas,
        "area_stress":    coordinator.area_stress,
        "crew_available": coordinator.crew_available,
        "agent_goals": {
            "customer_support": customer_agent.goal_stats,
            "coordinator":      coordinator.goal_stats,
            "tech_agents": {
                area: agent.goal_stats
                for area, agent in coordinator.AREA_ROUTING.items()
            },
        },
    }


@app.post("/demo")
def fire_demo():
    demo = [
        ("Saman Perera",       "Colombo-07", "Power has been off for 2 hours, no notification from CEB!"),
        ("Nimali Fernando",    "Negombo",    "Entire street has no power since morning, very urgent!"),
        ("Dilani Jayawardena", "Galle",      "No electricity at home, called hotline but no answer."),
    ]
    ids = []
    for name, area, msg in demo:
        c = customer_agent.intake(customer_name=name, area=area, message=msg)
        ids.append(c["id"])
    return {"status": "ok", "count": len(ids), "complaint_ids": ids}


# ─────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  CEB MAS Backend — http://localhost:8000")
    print("  API docs       — http://localhost:8000/docs")
    print("=" * 55)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
