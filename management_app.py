"""
management_app.py — Power Outage Management Dashboard
Full operational view of agent behaviour — for operators only.

Run:  streamlit run management_app.py --server.port 8502
      (backend must be running on port 8000)

Tabs
────
1. Complaints    — all cases with priority, severity, confidence score
2. Agent Messages— MessageBus feed (Communication)
3. Activity Log  — colour-coded per agent type + negotiate/butterfly/emergence
4. Grid & Stress — live fault map, butterfly-effect stress bars, crew availability (Negotiation)
5. Agent Goals   — per-agent goal_stats (Goal-Directed Behaviour)
"""

import html as html_lib
import time

import requests
import streamlit as st

from data import AREAS, FAULT_TYPE_INFO, STATUS_CONFIG, CREW_CAPACITY

BACKEND = "http://localhost:8000"

st.set_page_config(
    page_title="Management Dashboard",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────
#  API helpers
# ─────────────────────────────────────────────────────────────
def api_get(path: str):
    try:
        r = requests.get(f"{BACKEND}{path}", timeout=5)
        return r.json() if r.ok else None
    except Exception:
        return None


def api_post(path: str, data: dict = None):
    try:
        r = requests.post(f"{BACKEND}{path}", json=data or {}, timeout=8)
        return r.json() if r.ok else None
    except Exception:
        return None


def backend_online() -> bool:
    h = api_get("/health")
    return h is not None and h.get("status") == "ok"


# ─────────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background:#0f1117; }
[data-testid="stHeader"]           { background:transparent; }
.block-container { padding-top:1rem; max-width:100%; }

.topbar {
    background:linear-gradient(135deg,#1e2035,#252840);
    border:1px solid #2e3355; border-radius:12px;
    padding:14px 24px; margin-bottom:14px;
    display:flex; align-items:center; justify-content:space-between;
}
.topbar-title { color:#e2e8f0; font-size:20px; font-weight:700; }
.topbar-sub   { color:#94a3b8; font-size:13px; margin-top:2px; }
.badge-blue   { background:#1e3a5f; color:#93c5fd; font-size:11px; font-weight:600;
                padding:3px 10px; border-radius:20px; border:1px solid #2563eb40; }
.badge-red    { background:#450a0a; color:#fca5a5; font-size:11px; font-weight:600;
                padding:3px 10px; border-radius:20px; border:1px solid #ef444440; }

.crisis-banner {
    background:linear-gradient(135deg,#450a0a,#7f1d1d);
    border:1px solid #ef4444; border-radius:10px;
    padding:14px 20px; margin-bottom:14px;
    display:flex; align-items:center; gap:14px;
}
.crisis-text { color:#fca5a5; font-size:14px; font-weight:700; }
.crisis-sub  { color:#f87171; font-size:12px; }

.metric-row  { display:flex; gap:10px; margin-bottom:14px; }
.metric-card { flex:1; background:#12151f; border:1px solid #2e3355;
               border-radius:10px; padding:12px; text-align:center; }
.metric-num  { font-size:26px; font-weight:700; }
.metric-lbl  { font-size:11px; color:#64748b; text-transform:uppercase;
               letter-spacing:0.5px; margin-top:2px; }

.cc { background:#12151f; border:1px solid #2e3355;
      border-radius:10px; padding:12px 14px; margin-bottom:8px; }
.cc-hdr { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }
.cc-name{ color:#e2e8f0; font-size:14px; font-weight:600; }
.cc-area{ color:#64748b; font-size:12px; }
.cc-msg { color:#94a3b8; font-size:13px; margin:4px 0; }
.badge  { display:inline-block; padding:2px 10px; border-radius:20px;
          font-size:11px; font-weight:600; }
.pchip  { font-size:10px; font-weight:600; padding:2px 8px; border-radius:12px; }

.log-wrap    { max-height:480px; overflow-y:auto; }
.log-entry   { padding:5px 8px; border-radius:6px; margin-bottom:4px;
               font-size:12px; font-family:monospace; }
.log-customer    { background:#1e2535; color:#93c5fd;  border-left:3px solid #3b82f6; }
.log-coordinator { background:#1e1a35; color:#c4b5fd;  border-left:3px solid #7c3aed; }
.log-tech        { background:#1a2535; color:#6ee7b7;  border-left:3px solid #10b981; }
.log-negotiate   { background:#2a2010; color:#fcd34d;  border-left:3px solid #f59e0b; }
.log-butterfly   { background:#0f2535; color:#67e8f9;  border-left:3px solid #06b6d4; }
.log-emergence   { background:#350a2a; color:#f0abfc;  border-left:3px solid #d946ef; }
.log-error       { background:#2a1a1a; color:#fca5a5;  border-left:3px solid #ef4444; }
.log-lbl  { font-weight:700; margin-right:6px; }
.log-time { color:#475569; margin-right:8px; }

.msg-card    { background:#12151f; border:1px solid #2e3355;
               border-radius:8px; padding:10px 14px; margin-bottom:6px;
               font-size:12px; font-family:monospace; }
.msg-route   { color:#94a3b8; margin-bottom:4px; }
.msg-content { color:#64748b; }

.grid-card { background:#12151f; border:1px solid #2e3355;
             border-radius:10px; padding:12px 14px; margin-bottom:8px; }
.grid-name { color:#e2e8f0; font-size:14px; font-weight:600; }
.grid-sub  { color:#475569; font-size:11px; }
.grid-desc { color:#64748b; font-size:11px; margin-top:6px; }
.bar-wrap  { background:#1e2535; border-radius:4px; height:8px; overflow:hidden; margin-top:4px; }
.bar       { height:8px; border-radius:4px; }

.goal-card  { background:#12151f; border:1px solid #2e3355;
              border-radius:10px; padding:16px; margin-bottom:10px; }
.goal-title { color:#e2e8f0; font-size:14px; font-weight:600; margin-bottom:4px; }
.goal-desc  { color:#64748b; font-size:12px; margin-bottom:10px; }
.goal-row   { display:flex; justify-content:space-between;
              padding:4px 0; border-bottom:1px solid #1e2535; }
.goal-key   { color:#475569; font-size:12px; }
.goal-val   { font-size:12px; font-weight:600; }
.ok  { color:#10b981; }
.bad { color:#ef4444; }

.live-dot { display:inline-block; width:7px; height:7px; border-radius:50%;
            background:#10b981; box-shadow:0 0 6px #10b981;
            animation:pulse 1.5s infinite; margin-right:5px; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }

.offline-banner {
    background:#2a1a1a; border:1px solid #ef4444; border-radius:10px;
    padding:12px 18px; color:#fca5a5; font-size:13px; margin-bottom:14px;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  Badge helpers  (build strings, never call st.markdown per-item)
# ─────────────────────────────────────────────────────────────
def status_badge(status: str) -> str:
    cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["RECEIVED"])
    return (f'<span class="badge" style="background:{cfg["bg"]};color:{cfg["color"]};'
            f'border:1px solid {cfg["color"]}40">{html_lib.escape(cfg["label"])}</span>')


def severity_badge(sev: str) -> str:
    colors = {
        "critical": ("#fee2e2","#dc2626"),
        "high":     ("#fff7ed","#ea580c"),
        "medium":   ("#fefce8","#ca8a04"),
        "low":      ("#f0fdf4","#16a34a"),
        "none":     ("#eff6ff","#2563eb"),
    }
    bg, fg = colors.get(sev, ("#1e2535","#94a3b8"))
    return (f'<span class="badge" style="background:{bg};color:{fg};'
            f'border:1px solid {fg}40">{sev.upper()}</span>')


def priority_chip(label: str) -> str:
    c = {"CRITICAL":"#dc2626","HIGH":"#ea580c","MEDIUM":"#ca8a04",
         "LOW":"#16a34a","STANDARD":"#6366f1"}.get(label,"#6366f1")
    return (f'<span class="pchip" style="background:{c}20;color:{c};'
            f'border:1px solid {c}40">{html_lib.escape(label)}</span>')


def msg_type_color(t: str) -> str:
    return {
        "REQUEST":"#6366f1","RESPONSE":"#10b981","ALERT":"#f59e0b",
        "NEGOTIATE":"#f97316","ESCALATE":"#ef4444","GOAL_UPDATE":"#8b5cf6",
    }.get(t,"#94a3b8")


def conf_color(score: int) -> str:
    return "#10b981" if score >= 80 else "#f59e0b" if score >= 65 else "#ef4444"


def stress_color(level: int) -> str:
    return "#ef4444" if level >= 70 else "#f59e0b" if level >= 40 else "#10b981"


# ─────────────────────────────────────────────────────────────
#  Fetch data from backend
# ─────────────────────────────────────────────────────────────
online       = backend_online()
all_c        = api_get("/complaints") or []
all_msgs     = api_get("/messages") or []
activity_log = api_get("/activity-log") or []
status_data  = api_get("/status") or {}

area_stress    = status_data.get("area_stress", {})
crew_available = status_data.get("crew_available", {})
grid_crisis    = status_data.get("grid_crisis", False)
crisis_areas   = status_data.get("crisis_areas", [])
agent_goals    = status_data.get("agent_goals", {})

active_c   = [c for c in all_c if c.get("status") in ("ROUTING","DIAGNOSING","RECEIVED")]
resolved_c = [c for c in all_c if c.get("status") in ("RESOLVED","NO_FAULT")]
fault_c    = [c for c in all_c if c.get("fault_type")]


# ─────────────────────────────────────────────────────────────
#  Top bar
# ─────────────────────────────────────────────────────────────
live_html = (f'<span class="live-dot"></span>'
             f'<span style="color:#10b981;font-size:12px">{len(active_c)} active</span>'
             if active_c else
             '<span style="color:#475569;font-size:12px">All clear</span>')

crisis_badge = ('<span class="badge-red">🚨 GRID CRISIS</span>'
                if grid_crisis else "")

st.markdown(
    f'<div class="topbar">'
    f'<div><div class="topbar-title">🔧 Operations Centre</div>'
    f'<div class="topbar-sub">Management Dashboard · Agent Behaviour Monitor</div></div>'
    f'<div style="display:flex;gap:10px;align-items:center">{live_html}'
    f'<span class="badge-blue">{len(all_msgs)} bus messages</span>{crisis_badge}'
    f'<a href="http://localhost:8501" target="_blank" style="color:#10b981;font-size:11px;'
    f'text-decoration:none;border:1px solid #10b98140;padding:3px 10px;border-radius:12px">'
    f'👤 Customer Portal</a></div></div>',
    unsafe_allow_html=True,
)

if not online:
    st.markdown(
        '<div class="offline-banner">⚠ Backend offline — start <code>python backend.py</code> first.</div>',
        unsafe_allow_html=True)

# Crisis banner (Emergent Properties)
if grid_crisis:
    st.markdown(f"""
<div class="crisis-banner">
  <div style="font-size:28px">🚨</div>
  <div>
    <div class="crisis-text">GRID CRISIS — Emergent Property Detected</div>
    <div class="crisis-sub">
      ≥ 3 concurrent high/critical faults triggered autonomous crisis mode.
      Affected: {html_lib.escape(', '.join(crisis_areas))}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# Metrics
st.markdown(f"""
<div class="metric-row">
  <div class="metric-card">
    <div class="metric-num" style="color:#6366f1">{len(all_c)}</div>
    <div class="metric-lbl">Total</div>
  </div>
  <div class="metric-card">
    <div class="metric-num" style="color:#f59e0b">{len(active_c)}</div>
    <div class="metric-lbl">In Progress</div>
  </div>
  <div class="metric-card">
    <div class="metric-num" style="color:#ef4444">{len(fault_c)}</div>
    <div class="metric-lbl">Faults Found</div>
  </div>
  <div class="metric-card">
    <div class="metric-num" style="color:#10b981">{len(resolved_c)}</div>
    <div class="metric-lbl">Resolved</div>
  </div>
  <div class="metric-card">
    <div class="metric-num" style="color:#06b6d4">{len(all_msgs)}</div>
    <div class="metric-lbl">Bus Messages</div>
  </div>
</div>
""", unsafe_allow_html=True)

col_refresh, _ = st.columns([1, 5])
with col_refresh:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()


# ─────────────────────────────────────────────────────────────
#  Tabs
# ─────────────────────────────────────────────────────────────
tab_comp, tab_msgs, tab_log, tab_grid, tab_goals = st.tabs([
    "📋 Complaints",
    "💬 Agent Messages",
    "🔄 Activity Log",
    "🗺 Grid & Stress",
    "🎯 Agent Goals",
])


# ══ TAB 1 — Complaints ═══════════════════════════════════════
with tab_comp:
    if not all_c:
        st.markdown('<div style="color:#475569;text-align:center;padding:40px;font-size:14px">'
                    'No complaints yet. Use the Customer Portal to submit one.</div>',
                    unsafe_allow_html=True)
    else:
        cards = []
        for comp in reversed(all_c):
            status     = comp.get("status", "RECEIVED")
            report     = comp.get("technical_report") or {}
            fault_type = comp.get("fault_type")
            severity   = comp.get("severity", "none")
            eta        = comp.get("eta_minutes")
            confidence = comp.get("confidence_score")
            pri_label  = comp.get("priority_label", "STANDARD")
            fi         = FAULT_TYPE_INFO.get(fault_type, FAULT_TYPE_INFO[None])
            low_conf   = report.get("_low_confidence", False)
            spin       = "⏳ " if status in ("ROUTING","DIAGNOSING") else ""

            eta_html  = (f'<span style="color:#f59e0b;font-size:12px">⏱ {eta} min</span>'
                         if eta else "")
            conf_html = ""
            if confidence is not None:
                cc = conf_color(confidence)
                warn = "⚠ " if low_conf else ""
                conf_html = (f'<span style="color:{cc};font-size:11px;font-family:monospace">'
                             f'{warn}conf {confidence}%</span>')
            fault_html = (
                f'<span style="color:#f59e0b;font-size:12px">{fi["icon"]} {html_lib.escape(fi["label"])}</span>'
                if fault_type else
                '<span style="color:#10b981;font-size:12px">✅ No fault detected</span>'
            )
            sev_html = (severity_badge(severity)
                        if status in ("RESOLVED","NO_FAULT") else "")
            msg_safe = html_lib.escape(comp.get("message","")[:80])
            if len(comp.get("message","")) > 80:
                msg_safe += "…"
            desc_html = ""
            if report.get("technical_description") and status in ("RESOLVED","NO_FAULT"):
                desc = html_lib.escape(report["technical_description"][:120])
                desc_html = (f'<div style="margin-top:8px;padding-top:8px;'
                             f'border-top:1px solid #1e2535;color:#64748b;font-size:12px">{desc}</div>')
            cards.append(f"""
<div class="cc">
  <div class="cc-hdr">
    <div>
      <span class="cc-name">{spin}{html_lib.escape(comp.get('customer_name',''))}</span>
      <span class="cc-area"> · {html_lib.escape(comp.get('area',''))}</span>
      &nbsp;{priority_chip(pri_label)}
    </div>
    <div style="display:flex;gap:6px;align-items:center">{sev_html}{status_badge(status)}</div>
  </div>
  <div class="cc-msg">"{msg_safe}"</div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin-top:6px">
    <div>{fault_html}</div>
    <div style="display:flex;gap:10px;align-items:center">
      {conf_html}{eta_html}
      <span style="color:#334155;font-size:10px;font-family:monospace">{comp.get('id','')[:8]}…</span>
    </div>
  </div>
  {desc_html}
</div>""")
        st.markdown("".join(cards), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("🧪 Demo: Simulate 3 concurrent complaints"):
        st.markdown('<div style="color:#64748b;font-size:13px;margin-bottom:10px">'
                    'Fires 3 complaints simultaneously to demonstrate priority-queue coordination, '
                    'crew negotiation, and butterfly-effect propagation.</div>',
                    unsafe_allow_html=True)
        if st.button("⚡ Fire 3 concurrent complaints", use_container_width=True,
                     disabled=not online):
            result = api_post("/demo")
            if result:
                st.success(f"Dispatched {result.get('count',3)} complaints — check Activity Log.")
                time.sleep(0.5)
                st.rerun()


# ══ TAB 2 — Agent Messages (Communication) ═══════════════════
with tab_msgs:
    st.markdown(
        '<div style="color:#475569;font-size:12px;margin-bottom:10px">'
        '📡 Every structured message exchanged between agents via the '
        '<strong style="color:#6366f1">MessageBus</strong>. '
        'Type colours: '
        '<span style="color:#6366f1">REQUEST</span> · '
        '<span style="color:#10b981">RESPONSE</span> · '
        '<span style="color:#f59e0b">ALERT</span> · '
        '<span style="color:#f97316">NEGOTIATE</span> · '
        '<span style="color:#ef4444">ESCALATE</span>'
        '</div>', unsafe_allow_html=True)

    if not all_msgs:
        st.markdown('<div style="color:#475569;text-align:center;padding:40px;font-size:14px">'
                    'No messages yet.</div>', unsafe_allow_html=True)
    else:
        parts = ['<div style="max-height:500px;overflow-y:auto">']
        for m in reversed(all_msgs[-100:]):
            tc = msg_type_color(m.get("msg_type",""))
            content = m.get("content", {})
            content_str = html_lib.escape(
                "  ".join(f"{k}: {v}" for k, v in content.items())
            )
            sender   = html_lib.escape(m.get("sender",""))
            receiver = html_lib.escape(m.get("receiver",""))
            mtype    = html_lib.escape(m.get("msg_type",""))
            parts.append(f"""
<div class="msg-card" style="border-left:3px solid {tc}">
  <div class="msg-route">
    <span style="color:{tc};font-weight:700">[{mtype}]</span>
    &nbsp;
    <span style="color:#e2e8f0">{sender}</span>
    <span style="color:#334155"> → </span>
    <span style="color:#e2e8f0">{receiver}</span>
    &nbsp;&nbsp;
    <span style="color:#334155">{html_lib.escape(m.get('timestamp',''))} · #{html_lib.escape(m.get('msg_id',''))}</span>
  </div>
  <div class="msg-content">{content_str}</div>
</div>""")
        parts.append("</div>")
        st.markdown("".join(parts), unsafe_allow_html=True)


# ══ TAB 3 — Activity Log ═════════════════════════════════════
with tab_log:
    st.markdown(
        '<div style="color:#475569;font-size:12px;margin-bottom:10px">'
        'Colour-coded: '
        '<span style="color:#93c5fd">Blue=Customer</span> · '
        '<span style="color:#c4b5fd">Purple=Coordinator</span> · '
        '<span style="color:#6ee7b7">Green=TechAgent</span> · '
        '<span style="color:#fcd34d">Amber=Negotiation</span> · '
        '<span style="color:#67e8f9">Cyan=Butterfly</span> · '
        '<span style="color:#f0abfc">Magenta=Emergence</span>'
        '</div>', unsafe_allow_html=True)

    if not activity_log:
        st.markdown('<div style="color:#475569;text-align:center;padding:40px;font-size:14px">'
                    'Agent activity will appear here.</div>', unsafe_allow_html=True)
    else:
        css_map = {
            "customer":    "log-customer",
            "coordinator": "log-coordinator",
            "tech":        "log-tech",
            "negotiate":   "log-negotiate",
            "butterfly":   "log-butterfly",
            "emergence":   "log-emergence",
            "error":       "log-error",
        }
        parts = ['<div class="log-wrap">']
        for entry in reversed(activity_log[-120:]):
            css  = css_map.get(entry.get("type","info"), "log-coordinator")
            safe = html_lib.escape(entry.get("message",""))
            parts.append(
                f'<div class="log-entry {css}">'
                f'<span class="log-time">{html_lib.escape(entry.get("time",""))}</span>'
                f'<span class="log-lbl">[{html_lib.escape(entry.get("agent",""))}]</span>'
                f'{safe}</div>'
            )
        parts.append("</div>")
        st.markdown("".join(parts), unsafe_allow_html=True)


# ══ TAB 4 — Grid & Stress ════════════════════════════════════
with tab_grid:
    col_g1, col_g2 = st.columns(2, gap="medium")

    with col_g1:
        st.markdown(
            '<div style="color:#64748b;font-size:12px;margin-bottom:10px">'
            '🦋 <strong style="color:#67e8f9">Butterfly Effect</strong>: '
            'A fault in one area propagates grid stress to adjacent areas. '
            'Stress ≥ 70% triggers a preemptive standby alert.</div>',
            unsafe_allow_html=True)

        cards = []
        for aname, adata in AREAS.items():
            fault   = adata.get("current_fault")
            fi      = FAULT_TYPE_INFO.get(fault["type"] if fault else None, FAULT_TYPE_INFO[None])
            stress  = area_stress.get(aname, 0)
            sc      = stress_color(stress)
            dot_c   = {"red":"#ef4444","orange":"#f97316","green":"#10b981","blue":"#3b82f6"}.get(
                        fi.get("color","green"),"#10b981")
            if fault:
                desc = fault.get("description","")
                note = html_lib.escape(desc[:55]+"…" if len(desc)>55 else desc)
                eta_part = f" · ETA {fault['eta_minutes']} min" if fault.get("eta_minutes") else ""
            else:
                note = html_lib.escape(adata.get("note","Stable"))
                eta_part = ""
            warn = "⚠" if stress >= 70 else ""
            cards.append(f"""
<div class="grid-card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div style="display:flex;align-items:center;gap:8px">
      <span style="width:9px;height:9px;border-radius:50%;background:{dot_c};
                   box-shadow:0 0 6px {dot_c};display:inline-block"></span>
      <span class="grid-name">{html_lib.escape(aname)}</span>
    </div>
    <span style="font-size:12px;color:#94a3b8">{fi['icon']} {html_lib.escape(fi['label'])}{html_lib.escape(eta_part)}</span>
  </div>
  <div class="grid-desc">{note}</div>
  <div style="display:flex;justify-content:space-between;align-items:center;margin:6px 0 3px">
    <span style="color:#64748b;font-size:11px">Grid Stress</span>
    <span style="color:{sc};font-size:11px;font-weight:600">{stress}% {warn}</span>
  </div>
  <div class="bar-wrap"><div class="bar" style="width:{stress}%;background:{sc}"></div></div>
</div>""")
        st.markdown("".join(cards), unsafe_allow_html=True)

    with col_g2:
        st.markdown(
            '<div style="color:#64748b;font-size:12px;margin-bottom:10px">'
            '🤝 <strong style="color:#fcd34d">Negotiation</strong>: '
            'Coordinator bargains crew deployment. Reallocates from adjacent areas when local crews are exhausted. '
            'Escalates to manual dispatch if all fail.</div>',
            unsafe_allow_html=True)

        cards = []
        for aname in AREAS:
            cap   = CREW_CAPACITY.get(aname, 2)
            avail = crew_available.get(aname, cap)
            used  = max(0, cap - avail)
            pct   = int(100 * avail / cap) if cap > 0 else 0
            bc    = "#10b981" if pct > 50 else "#f59e0b" if pct > 20 else "#ef4444"
            state = ("Critical — reallocating" if pct == 0
                     else "Low" if pct <= 25 else "OK")
            cards.append(f"""
<div class="grid-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
    <span class="grid-name">{html_lib.escape(aname)}</span>
    <span style="color:#94a3b8;font-size:12px">{avail}/{cap} available</span>
  </div>
  <div class="bar-wrap"><div class="bar" style="width:{pct}%;background:{bc}"></div></div>
  <div style="display:flex;justify-content:space-between;margin-top:4px">
    <span style="color:#475569;font-size:11px">{used} deployed</span>
    <span style="color:{bc};font-size:11px">{state}</span>
  </div>
</div>""")
        st.markdown("".join(cards), unsafe_allow_html=True)


# ══ TAB 5 — Agent Goals ══════════════════════════════════════
with tab_goals:
    st.markdown(
        '<div style="color:#475569;font-size:12px;margin-bottom:14px">'
        '🎯 Each agent pursues an explicit goal. Stats update in real time.</div>',
        unsafe_allow_html=True)

    # CustomerSupport
    cs_g = agent_goals.get("customer_support", {})
    cs_met = cs_g.get("ack_rate", 100) >= 95
    st.markdown(f"""
<div class="goal-card">
  <div class="goal-title">👤 CustomerSupport Agent</div>
  <div class="goal-desc">{html_lib.escape(cs_g.get('description','Acknowledge every complaint within 5 s'))}</div>
  <div class="goal-row">
    <span class="goal-key">Complaints received</span>
    <span class="goal-val">{cs_g.get('total_received',0)}</span>
  </div>
  <div class="goal-row">
    <span class="goal-key">Fast acks (&lt; 5 s)</span>
    <span class="goal-val">{cs_g.get('fast_acks',0)}</span>
  </div>
  <div class="goal-row">
    <span class="goal-key">Ack rate (target ≥ 95%)</span>
    <span class="goal-val {'ok' if cs_met else 'bad'}">{cs_g.get('ack_rate',100)}% {"✓" if cs_met else "✗"}</span>
  </div>
</div>""", unsafe_allow_html=True)

    # Coordinator
    co_g  = agent_goals.get("coordinator", {})
    total = co_g.get("total_routed", 0)
    errs  = co_g.get("routing_errors", 0)
    acc   = round(100*(total-errs)/total, 1) if total else 100.0
    avg_s = co_g.get("avg_resolution_sec", 0)
    co_acc_met = acc >= 100
    co_spd_met = avg_s < 60 or total == 0
    st.markdown(f"""
<div class="goal-card">
  <div class="goal-title">🔀 Coordinator Agent</div>
  <div class="goal-desc">{html_lib.escape(co_g.get('description','100% routing accuracy; avg resolution &lt; 60 s'))}</div>
  <div class="goal-row">
    <span class="goal-key">Total routed</span>
    <span class="goal-val">{total}</span>
  </div>
  <div class="goal-row">
    <span class="goal-key">Routing errors</span>
    <span class="goal-val {'ok' if errs==0 else 'bad'}">{errs} {"✓" if errs==0 else "✗"}</span>
  </div>
  <div class="goal-row">
    <span class="goal-key">Routing accuracy (target 100%)</span>
    <span class="goal-val {'ok' if co_acc_met else 'bad'}">{acc}% {"✓" if co_acc_met else "✗"}</span>
  </div>
  <div class="goal-row">
    <span class="goal-key">Avg resolution (target &lt; 60 s)</span>
    <span class="goal-val {'ok' if co_spd_met else 'bad'}">{avg_s} s {"✓" if co_spd_met else "✗"}</span>
  </div>
  <div class="goal-row">
    <span class="goal-key">Grid crisis active</span>
    <span class="goal-val {'bad' if grid_crisis else 'ok'}">{"Yes 🚨" if grid_crisis else "No ✓"}</span>
  </div>
</div>""", unsafe_allow_html=True)

    # TechAgents
    st.markdown('<div style="color:#64748b;font-size:12px;margin:4px 0 8px">Technical Fault Agents</div>',
                unsafe_allow_html=True)
    tech_goals = agent_goals.get("tech_agents", {})
    cards = []
    for aname, tg in tech_goals.items():
        avg  = tg.get("avg_confidence", 0)
        met  = tg.get("goal_met", True)
        n    = tg.get("total_diagnoses", 0)
        vc   = "#10b981" if met else "#ef4444"
        cards.append(f"""
<div class="goal-card" style="margin-bottom:8px">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <div class="goal-title" style="margin-bottom:2px">TechAgent — {html_lib.escape(aname)}</div>
      <div class="goal-desc" style="margin-bottom:0">
        {html_lib.escape(tg.get('description','Avg diagnosis confidence &gt; 75%'))}
      </div>
    </div>
    <div style="text-align:right">
      <div style="font-size:22px;font-weight:700;color:{vc}">{avg}%</div>
      <div style="font-size:11px;color:#475569">{n} diagnos{'is' if n==1 else 'es'}</div>
    </div>
  </div>
</div>""")
    st.markdown("".join(cards), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  Auto-refresh while complaints are in-flight OR resolved but
#  customer_message not yet populated by the backend drain loop.
# ─────────────────────────────────────────────────────────────
needs_refresh = [
    c for c in all_c
    if c.get("status") in ("RECEIVED", "ROUTING", "DIAGNOSING")   # still processing
]
if needs_refresh:
    time.sleep(1.5)
    st.rerun()
