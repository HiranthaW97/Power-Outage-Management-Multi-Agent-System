"""
agents.py — Multi-Agent System for CEB Power Outage Complaints

MAS Concepts demonstrated
─────────────────────────
Essential
  Communication        — AgentMessage + MessageBus (structured, observable inter-agent protocol)
  Coordination         — PriorityQueue routing (critical faults processed before routine ones)
  Negotiation          — Crew allocation bargaining with reallocation from adjacent areas

Good to have
  Butterfly Effect     — Fault stress propagates to geographically adjacent areas
  Emergent Properties  — System-level GRID_CRISIS declared when ≥3 concurrent high-severity faults
  Uncertainty          — LLM returns confidence_score; low-confidence diagnoses flagged
  Achieving Goals      — Per-agent goal_stats tracked and exposed to the management UI
"""

import json
import uuid
import threading
import time
import queue
import itertools
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from dotenv import load_dotenv
from openai import OpenAI
from data import AREAS, FAULT_TYPE_INFO, STATUS_CONFIG, AREA_ADJACENCY, CREW_CAPACITY

load_dotenv()

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


# ═════════════════════════════════════════════════════════════
#  COMMUNICATION — Structured Message Protocol
# ═════════════════════════════════════════════════════════════


@dataclass
class AgentMessage:
    """
    Every inter-agent exchange is a typed, structured message.
    Types: REQUEST | RESPONSE | ALERT | NEGOTIATE | ESCALATE | GOAL_UPDATE
    """

    sender: str
    receiver: str
    msg_type: str
    content: dict
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    priority: int = 0  # 0 = highest


class MessageBus:
    """
    Central publish/subscribe bus — all inter-agent messages flow through here,
    making communication fully observable without tight coupling between agents.
    """

    def __init__(self):
        self.messages: list[AgentMessage] = []
        self._lock = threading.Lock()

    def send(self, msg: AgentMessage) -> None:
        with self._lock:
            self.messages.append(msg)

    def get_all(self) -> list[AgentMessage]:
        with self._lock:
            return list(self.messages)

    def get_since(self, index: int) -> list[AgentMessage]:
        with self._lock:
            return list(self.messages[index:])

    def count(self) -> int:
        with self._lock:
            return len(self.messages)


# ═════════════════════════════════════════════════════════════
#  TIER 3 — Technical Fault Agent
# ═════════════════════════════════════════════════════════════


class TechnicalFaultAgent:
    """
    Diagnoses power faults for one geographic zone.
    Reports confidence_score (UNCERTAINTY) and tracks avg confidence as its GOAL.
    """

    def __init__(self, area: str, bus: MessageBus):
        self.area = area
        self.area_data = AREAS.get(area, {})
        self.agent_id = f"TechAgent-{area.replace('-', '').replace(' ', '')}"
        self.bus = bus

        # GOAL: maintain average diagnosis confidence > 75 %
        self.goal_stats = {
            "description": "Avg diagnosis confidence > 75%",
            "total_diagnoses": 0,
            "total_confidence": 0,
            "avg_confidence": 0.0,
            "goal_met": True,
        }

    def diagnose(
        self, complaint: dict, log_callback: Optional[Callable] = None
    ) -> dict:
        fault = self.area_data.get("current_fault")
        substation = self.area_data.get("substation", "Unknown Substation")
        feeders = self.area_data.get("feeders", [])

        # COMMUNICATION: announce diagnosis start
        self.bus.send(
            AgentMessage(
                sender=self.agent_id,
                receiver="Coordinator",
                msg_type="RESPONSE",
                content={
                    "status": "diagnosis_started",
                    "complaint_id": complaint["id"][:8],
                    "area": self.area,
                },
            )
        )

        if log_callback:
            log_callback(
                self.agent_id,
                f"Received {complaint['id'][:8]}… — querying grid data for {self.area}",
                "tech",
            )

        system_prompt = (
            "You are a Technical Fault Diagnosis Agent for CEB (Ceylon Electricity Board) Sri Lanka. "
            "You have access to real-time grid sensor data and must produce an accurate technical report. "
            "Return ONLY valid JSON — no markdown, no explanation, no extra text."
        )

        user_prompt = f"""
Diagnose the following power complaint and return a structured JSON report.

Customer complaint ID : {complaint['id']}
Area reported         : {self.area}
Substation            : {substation}
Active feeders        : {json.dumps(feeders)}
Grid fault data       : {json.dumps(fault, indent=2) if fault else "null — no active fault detected"}
Customer message      : "{complaint.get('message', 'Power cut reported')}"
Time received         : {complaint.get('timestamp', datetime.now().isoformat())}

Return JSON with EXACTLY these fields (no extras):
{{
  "complaint_id":         "<string>",
  "area":                 "<string>",
  "substation":           "<string>",
  "fault_type":           "<string or null>",
  "feeder_affected":      "<string or null>",
  "technical_description":"<detailed technical description>",
  "severity":             "<none|low|medium|high|critical>",
  "eta_minutes":          <integer or null>,
  "crew_on_site":         <true|false>,
  "resolution_steps":     ["<step1>", "<step2>"],
  "customer_summary":     "<one friendly sentence for the customer>",
  "confidence_score":     <integer 0-100 — your confidence in this diagnosis>,
  "uncertainty_note":     "<what is uncertain, or 'Grid data confirms fault — high confidence' if certain>"
}}
"""
        try:
            resp = get_client().chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=700,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw = resp.choices[0].message.content.strip()
            for fence in ["```json", "```"]:
                if fence in raw:
                    raw = raw.split(fence)[-2 if raw.endswith("```") else 1]
                    raw = raw.strip().strip("```").strip()
            report = json.loads(raw)
        except Exception as e:
            report = {
                "complaint_id": complaint["id"],
                "area": self.area,
                "substation": substation,
                "fault_type": fault["type"] if fault else None,
                "feeder_affected": fault["feeder"] if fault else None,
                "technical_description": (
                    fault["description"] if fault else "No active fault detected."
                ),
                "severity": FAULT_TYPE_INFO.get(
                    fault["type"] if fault else None, {}
                ).get("severity", "none"),
                "eta_minutes": fault["eta_minutes"] if fault else None,
                "crew_on_site": fault.get("crew_on_site", False) if fault else False,
                "resolution_steps": [
                    "Grid monitoring active",
                    "Crew dispatched if required",
                ],
                "customer_summary": f"{'Fault detected: ' + fault['description'] if fault else 'No active fault in your area.'}",
                "confidence_score": 70,
                "uncertainty_note": "Fallback diagnosis — LLM unavailable",
                "_fallback": str(e),
            }

        # UNCERTAINTY — update goal stats
        confidence = int(report.get("confidence_score", 70))
        self.goal_stats["total_diagnoses"] += 1
        self.goal_stats["total_confidence"] += confidence
        self.goal_stats["avg_confidence"] = round(
            self.goal_stats["total_confidence"] / self.goal_stats["total_diagnoses"], 1
        )
        self.goal_stats["goal_met"] = self.goal_stats["avg_confidence"] >= 75

        # COMMUNICATION: publish diagnosis result
        self.bus.send(
            AgentMessage(
                sender=self.agent_id,
                receiver="Coordinator",
                msg_type="RESPONSE",
                content={
                    "complaint_id": complaint["id"][:8],
                    "fault_type": report.get("fault_type"),
                    "severity": report.get("severity", "none"),
                    "confidence_score": confidence,
                    "uncertainty_note": report.get("uncertainty_note", ""),
                    "eta_minutes": report.get("eta_minutes"),
                },
            )
        )

        if log_callback:
            log_callback(
                self.agent_id,
                f"Diagnosis complete — severity: {report.get('severity','none').upper()}, "
                f"confidence: {confidence}%, ETA: {report.get('eta_minutes', 'N/A')} min",
                "tech",
            )

        return report


# ═════════════════════════════════════════════════════════════
#  TIER 2 — Coordinator Agent
# ═════════════════════════════════════════════════════════════


class CoordinatorAgent:
    """
    Central orchestrator. Owns:
      - COORDINATION  : priority-queue routing (critical first)
      - NEGOTIATION   : crew allocation bargaining
      - BUTTERFLY     : stress propagation to adjacent areas
      - EMERGENCE     : grid-crisis detection from complaint patterns
      - GOALS         : routing accuracy and resolution-time tracking
    """

    def __init__(self, message_bus: MessageBus):
        self.bus = message_bus
        self.agent_id = "Coordinator"

        # TechAgents injected with shared bus
        self.AREA_ROUTING: dict[str, TechnicalFaultAgent] = {
            area: TechnicalFaultAgent(area, message_bus) for area in AREAS
        }

        self.registry: dict[str, dict] = {}
        self.activity_log: list[dict] = []
        self.pending_responses: dict = {}
        self._lock = threading.Lock()

        # COORDINATION: priority queue + 2 worker threads
        self._complaint_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._seq = itertools.count()
        for _ in range(2):
            threading.Thread(target=self._queue_worker, daemon=True).start()

        # BUTTERFLY EFFECT: grid stress per area (0–100)
        self.area_stress: dict[str, int] = {area: 0 for area in AREAS}

        # NEGOTIATION: available crews per area
        self.crew_available: dict[str, int] = dict(CREW_CAPACITY)

        # EMERGENT PROPERTIES: crisis state
        self.grid_crisis: bool = False
        self.crisis_areas: list[str] = []

        # GOAL TRACKING
        self.goal_stats = {
            "description": "100% routing accuracy; avg resolution < 60 s",
            "total_routed": 0,
            "routing_errors": 0,
            "resolution_times": [],
            "avg_resolution_sec": 0.0,
        }

    # ── Internal helpers ──────────────────────────────────────

    def _log(self, agent_id: str, message: str, log_type: str = "info"):
        with self._lock:
            self.activity_log.append(
                {
                    "agent": agent_id,
                    "message": message,
                    "type": log_type,
                    "time": datetime.now().strftime("%H:%M:%S"),
                }
            )

    def _resolve(self, complaint_id: str, report: dict):
        with self._lock:
            self.pending_responses[complaint_id] = report

    def _update_status(self, complaint_id: str, status: str, extra: dict = None):
        with self._lock:
            if complaint_id in self.registry:
                self.registry[complaint_id]["status"] = status
                self.registry[complaint_id][
                    "status_updated_at"
                ] = datetime.now().strftime("%H:%M:%S")
                if extra:
                    self.registry[complaint_id].update(extra)

    def _estimate_priority(self, complaint: dict) -> int:
        """COORDINATION: map area fault type to queue priority (lower = first)."""
        fault = AREAS.get(complaint.get("area", ""), {}).get("current_fault")
        if not fault:
            return 4
        return {
            "cable_break": 0,
            "line_tripped": 1,
            "transformer_overload": 1,
            "scheduled_maintenance": 3,
        }.get(fault.get("type"), 4)

    # ── Negotiation ───────────────────────────────────────────

    def _negotiate_crew(self, area: str, severity: str, complaint_id: str) -> bool:
        """
        NEGOTIATION: Coordinator requests crew deployment.
        1. If local crews available → approve immediately.
        2. If not → try reallocation from an adjacent area with surplus.
        3. If still none → escalate to ManualDispatch.
        All steps are published on the MessageBus.
        """
        tech_id = f"TechAgent-{area.replace('-', '').replace(' ', '')}"

        # Open negotiation
        self.bus.send(
            AgentMessage(
                sender=self.agent_id,
                receiver=tech_id,
                msg_type="NEGOTIATE",
                content={
                    "complaint_id": complaint_id[:8],
                    "request": "crew_deployment",
                    "area": area,
                    "severity": severity,
                },
                priority={
                    "critical": 0,
                    "high": 1,
                    "medium": 2,
                    "low": 3,
                    "none": 4,
                }.get(severity, 4),
            )
        )

        with self._lock:
            available = self.crew_available.get(area, 0)

        # Case 1 — local crew available
        if available > 0:
            with self._lock:
                self.crew_available[area] -= 1
            self._log(
                self.agent_id,
                f"NEGOTIATION ✓ Crew approved for {area} ({severity.upper()}) — "
                f"{available - 1} crew(s) remaining locally",
                "negotiate",
            )
            self.bus.send(
                AgentMessage(
                    sender=self.agent_id,
                    receiver=tech_id,
                    msg_type="RESPONSE",
                    content={
                        "outcome": "APPROVED",
                        "area": area,
                        "complaint_id": complaint_id[:8],
                    },
                )
            )
            return True

        # Case 2 — reallocate from adjacent area
        for adj in AREA_ADJACENCY.get(area, []):
            with self._lock:
                adj_avail = self.crew_available.get(adj, 0)
            if adj_avail > 1:
                with self._lock:
                    self.crew_available[adj] -= 1
                self._log(
                    self.agent_id,
                    f"NEGOTIATION ⟳ No local crew — reallocating from {adj} → {area} "
                    f"({severity.upper()} fault)",
                    "negotiate",
                )
                self.bus.send(
                    AgentMessage(
                        sender=self.agent_id,
                        receiver=tech_id,
                        msg_type="RESPONSE",
                        content={
                            "outcome": "REALLOCATED",
                            "from_area": adj,
                            "to_area": area,
                            "complaint_id": complaint_id[:8],
                        },
                    )
                )
                return True

        # Case 3 — escalate
        self._log(
            self.agent_id,
            f"NEGOTIATION ✗ No crew available for {area} — escalating to manual dispatch",
            "negotiate",
        )
        self.bus.send(
            AgentMessage(
                sender=self.agent_id,
                receiver="ManualDispatch",
                msg_type="ESCALATE",
                content={
                    "area": area,
                    "severity": severity,
                    "reason": "no_crew_available",
                    "complaint_id": complaint_id[:8],
                },
            )
        )
        return False

    # ── Butterfly Effect ──────────────────────────────────────

    def _check_butterfly_effect(self, area: str, severity: str, fault_type):
        """
        BUTTERFLY EFFECT: A significant fault in one area raises the grid stress
        of neighbouring areas. High stress (≥ 70 %) triggers preemptive standby alerts.
        """
        if not fault_type or severity in ("none", "low"):
            return

        stress_delta = {"critical": 40, "high": 25, "medium": 12}.get(severity, 5)

        for adj in AREA_ADJACENCY.get(area, []):
            with self._lock:
                old = self.area_stress.get(adj, 0)
                new = min(100, old + stress_delta)
                self.area_stress[adj] = new

            self._log(
                self.agent_id,
                f"BUTTERFLY EFFECT: {fault_type.replace('_',' ')} in {area} raises "
                f"grid stress in {adj}  {old}% → {new}%",
                "butterfly",
            )

            self.bus.send(
                AgentMessage(
                    sender=self.agent_id,
                    receiver=f"TechAgent-{adj.replace('-', '').replace(' ', '')}",
                    msg_type="ALERT",
                    content={
                        "trigger": "butterfly_effect",
                        "source_area": area,
                        "adjacent_area": adj,
                        "stress_level": new,
                        "fault_type": fault_type,
                    },
                )
            )

            if new >= 70:
                self._log(
                    self.agent_id,
                    f"⚠ HIGH STRESS ALERT: {adj} at {new}% — preemptive crew standby recommended",
                    "butterfly",
                )

    # ── Emergent Properties ───────────────────────────────────

    def _detect_emergence(self):
        """
        EMERGENT PROPERTY: When ≥ 3 concurrent high/critical faults are active,
        the system autonomously declares a GRID_CRISIS — a behaviour not
        explicitly programmed for any individual agent, but emerging from the
        collective complaint pattern.
        """
        with self._lock:
            all_c = list(self.registry.values())

        high = [c for c in all_c if c.get("severity") in ("high", "critical")]

        if len(high) >= 3 and not self.grid_crisis:
            self.grid_crisis = True
            self.crisis_areas = list({c["area"] for c in high})
            self._log(
                self.agent_id,
                f"🚨 EMERGENT PROPERTY — GRID CRISIS declared: "
                f"{len(high)} concurrent high/critical faults across "
                f"{', '.join(self.crisis_areas)}",
                "emergence",
            )
            self.bus.send(
                AgentMessage(
                    sender=self.agent_id,
                    receiver="ALL_AGENTS",
                    msg_type="ESCALATE",
                    content={
                        "event": "GRID_CRISIS",
                        "affected_areas": self.crisis_areas,
                        "fault_count": len(high),
                        "action": "Switch to crisis-response mode — prioritise all pending complaints",
                    },
                    priority=0,
                )
            )

        elif len(high) < 3 and self.grid_crisis:
            self.grid_crisis = False
            self.crisis_areas = []
            self._log(
                self.agent_id,
                "✅ Grid crisis resolved — returning to normal operations",
                "emergence",
            )

    # ── Queue worker ──────────────────────────────────────────

    def _queue_worker(self):
        """COORDINATION: worker thread draining the priority queue."""
        while True:
            try:
                _priority, _seq, complaint = self._complaint_queue.get(timeout=0.5)
                self._do_process(complaint)
                self._complaint_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self._log(self.agent_id, f"Worker error: {e}", "error")

    def _do_process(self, complaint: dict):
        """Full processing pipeline — runs inside a worker thread."""
        cid = complaint["id"]
        area = complaint["area"]
        t_start = time.time()

        priority_label = {
            0: "CRITICAL",
            1: "HIGH",
            2: "MEDIUM",
            3: "LOW",
            4: "STANDARD",
        }.get(complaint.get("_priority", 4), "STANDARD")

        with self._lock:
            self.registry[cid] = {
                **complaint,
                "status": "ROUTING",
                "status_updated_at": datetime.now().strftime("%H:%M:%S"),
                "priority_label": priority_label,
            }

        self._log(
            self.agent_id,
            f"[{priority_label}] Complaint {cid[:8]}… from {complaint['customer_name']} "
            f"({area}) — routing to TechAgent",
            "coordinator",
        )

        # COMMUNICATION: announce routing decision
        self.bus.send(
            AgentMessage(
                sender=self.agent_id,
                receiver=f"TechAgent-{area.replace('-', '').replace(' ', '')}",
                msg_type="REQUEST",
                content={
                    "complaint_id": cid[:8],
                    "area": area,
                    "priority": priority_label,
                },
                priority=complaint.get("_priority", 4),
            )
        )

        self._update_status(cid, "DIAGNOSING")
        time.sleep(0.3)

        tech_agent = self.AREA_ROUTING.get(area)
        if not tech_agent:
            self._log(self.agent_id, f"Unknown area: {area} — cannot route", "error")
            with self._lock:
                self.goal_stats["routing_errors"] += 1
            self._update_status(cid, "RESOLVED", {"error": "Unknown area"})
            return

        report = tech_agent.diagnose(complaint, log_callback=self._log)
        severity = report.get("severity", "none")
        confidence = int(report.get("confidence_score", 70))

        # UNCERTAINTY: flag low-confidence diagnoses
        if confidence < 65:
            self._log(
                self.agent_id,
                f"LOW CONFIDENCE ({confidence}%): {cid[:8]}… — "
                f"{report.get('uncertainty_note', 'Diagnosis uncertain')}",
                "coordinator",
            )
            report["_low_confidence"] = True

        # NEGOTIATION: request crew for significant faults
        if severity in ("high", "critical") and report.get("fault_type"):
            self._negotiate_crew(area, severity, cid)

        # BUTTERFLY EFFECT: propagate stress to adjacent areas
        self._check_butterfly_effect(area, severity, report.get("fault_type"))

        final_status = "NO_FAULT" if not report.get("fault_type") else "RESOLVED"

        # GOAL: track resolution time
        elapsed = time.time() - t_start
        with self._lock:
            self.goal_stats["total_routed"] += 1
            self.goal_stats["resolution_times"].append(elapsed)
            times = self.goal_stats["resolution_times"]
            self.goal_stats["avg_resolution_sec"] = round(sum(times) / len(times), 1)

        self._log(
            self.agent_id,
            f"Report for {cid[:8]}… complete — pushing to CustomerSupport agent "
            f"(resolved in {elapsed:.1f}s)",
            "coordinator",
        )

        self._update_status(
            cid,
            final_status,
            {
                "technical_report": report,
                "fault_type": report.get("fault_type"),
                "severity": severity,
                "confidence_score": confidence,
                "eta_minutes": report.get("eta_minutes"),
                "resolved_at": datetime.now().strftime("%H:%M:%S"),
                "priority_label": priority_label,
            },
        )
        self._resolve(cid, report)

        # EMERGENT PROPERTY: re-evaluate system-level patterns
        self._detect_emergence()

    # ── Public API ────────────────────────────────────────────

    def route(self, complaint: dict) -> None:
        """COORDINATION: assign priority and enqueue for processing."""
        priority = self._estimate_priority(complaint)
        complaint["_priority"] = priority

        self._log(
            self.agent_id,
            f"Queuing {complaint['id'][:8]}… priority={priority} "
            f"(0=critical, 4=standard)",
            "coordinator",
        )

        # COMMUNICATION: receive from customer agent via bus
        self.bus.send(
            AgentMessage(
                sender="CustomerSupport",
                receiver=self.agent_id,
                msg_type="REQUEST",
                content={
                    "complaint_id": complaint["id"][:8],
                    "customer": complaint["customer_name"],
                    "area": complaint["area"],
                    "estimated_priority": priority,
                },
            )
        )

        self._complaint_queue.put((priority, next(self._seq), complaint))

    def get_all_complaints(self) -> list[dict]:
        with self._lock:
            return list(self.registry.values())

    def get_complaint(self, complaint_id: str) -> Optional[dict]:
        with self._lock:
            return self.registry.get(complaint_id)


# ═════════════════════════════════════════════════════════════
#  TIER 1 — Customer Support Agent
# ═════════════════════════════════════════════════════════════


class CustomerSupportAgent:
    """
    Customer-facing layer. Collects complaints, dispatches to Coordinator,
    and formats technical reports into friendly responses.
    GOAL: acknowledge every complaint in < 5 s.
    """

    def __init__(self, coordinator: CoordinatorAgent, bus: MessageBus):
        self.coordinator = coordinator
        self.bus = bus
        self.agent_id = "CustomerSupport"

        # GOAL: fast acknowledgement
        self.goal_stats = {
            "description": "Acknowledge every complaint within 5 s",
            "total_received": 0,
            "fast_acks": 0,
            "ack_rate": 100.0,
        }

    def create_complaint(self, customer_name: str, area: str, message: str) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "customer_name": customer_name,
            "area": area,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "status": "RECEIVED",
        }

    def intake(self, customer_name: str, area: str, message: str) -> dict:
        """Full intake pipeline — non-blocking."""
        t0 = time.time()
        complaint = self.create_complaint(customer_name, area, message)

        self.coordinator._log(
            self.agent_id,
            f"New complaint from {customer_name} in {area} — ID {complaint['id'][:8]}…",
            "customer",
        )

        # COMMUNICATION: publish intake event
        self.bus.send(
            AgentMessage(
                sender=self.agent_id,
                receiver=self.coordinator.agent_id,
                msg_type="REQUEST",
                content={
                    "complaint_id": complaint["id"][:8],
                    "customer": customer_name,
                    "area": area,
                    "message": message[:80],
                },
            )
        )

        self.coordinator.route(complaint)

        # GOAL: measure ack latency
        elapsed = time.time() - t0
        self.goal_stats["total_received"] += 1
        if elapsed < 5.0:
            self.goal_stats["fast_acks"] += 1
        total = self.goal_stats["total_received"]
        self.goal_stats["ack_rate"] = round(
            100 * self.goal_stats["fast_acks"] / total, 1
        )

        return complaint

    def format_response(self, report: dict, customer_name: str) -> str:
        """Turn a technical report into an empathetic customer-facing message."""
        system_prompt = (
            "You are a friendly CEB (Ceylon Electricity Board) customer support agent. "
            "Turn the technical fault report into a warm, clear, reassuring message. "
            "Be empathetic. Avoid jargon. Mention ETA if available. Keep it under 80 words."
        )
        try:
            # Build user_prompt inside try so json.dumps failures are caught by the fallback
            try:
                report_text = json.dumps(report, indent=2)
            except (TypeError, ValueError):
                report_text = str(report)

            user_prompt = (
                f"Customer name: {customer_name}\n"
                f"Technical report: {report_text}\n\n"
                "Write a friendly response message."
            )
            resp = get_client().chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=200,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            fault_type = report.get("fault_type")
            eta = report.get("eta_minutes")
            if not fault_type:
                return (
                    f"Dear {customer_name}, we've checked our grid — no active faults detected. "
                    "If the issue persists please contact us again."
                )
            eta_text = (
                f"Estimated restoration time is {eta} minutes."
                if eta
                else "Our team is assessing the timeline."
            )
            return (
                f"Dear {customer_name}, we've identified a {fault_type.replace('_', ' ')} in your area. "
                f"{eta_text} Our technical team is working to restore power as quickly as possible."
            )
