"""
customer_app.py — CEB Customer Portal
Conversational chat UI — no dropdown, no forms.

Flow
────
1. Agent asks for name  → customer types it in the chat input
2. Agent asks for area  → customer clicks an area button
3. Active chat          → customer types complaints freely; each session is isolated

Run:  streamlit run customer_app.py --server.port 8501
      (backend must be running on port 8000)
"""

import html as html_lib
import time

import requests
import streamlit as st

from data import AREAS, FAULT_TYPE_INFO, STATUS_CONFIG

BACKEND = "http://localhost:8000"

st.set_page_config(
    page_title="Customer Support",
    page_icon="⚡",
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


def api_post(path: str, data: dict):
    try:
        r = requests.post(f"{BACKEND}{path}", json=data, timeout=8)
        return r.json() if r.ok else None
    except Exception:
        return None


def backend_online() -> bool:
    h = api_get("/health")
    return h is not None and h.get("status") == "ok"


# ─────────────────────────────────────────────────────────────
#  CSS
# ─────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
[data-testid="stAppViewContainer"] { background: #0c0f1a; }
[data-testid="stHeader"]           { background: transparent; }
.block-container { padding-top: 1rem; max-width: 100%; }

.topbar {
    background: linear-gradient(135deg, #1a1f3a, #1e2547);
    border: 1px solid #2a3560;
    border-radius: 14px;
    padding: 14px 24px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.topbar-title { color: #e2e8f0; font-size: 20px; font-weight: 700; }
.topbar-sub   { color: #7c8db5; font-size: 13px; margin-top: 2px; }
.cust-chip {
    background: #1e3a5f; color: #93c5fd;
    font-size: 12px; font-weight: 600;
    padding: 5px 14px; border-radius: 20px;
    border: 1px solid #2563eb40;
}
.nav-link {
    font-size: 11px; text-decoration: none;
    border-radius: 12px; padding: 4px 12px;
    border: 1px solid;
}

.area-btn-wrap {
    background: #111827;
    border: 1px solid #1e2a45;
    border-radius: 12px;
    padding: 16px 18px;
    margin: 8px 0 4px;
}
.area-btn-title {
    color: #7c8db5; font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 1px;
    margin-bottom: 12px;
}

.panel-title {
    color: #7c8db5; font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 1px;
    margin-bottom: 10px;
}
.cust-card {
    background: #111827;
    border: 1px solid #1e2a45;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 12px;
}
.cust-card-name { color: #e2e8f0; font-size: 15px; font-weight: 700; margin-bottom: 2px; }
.cust-card-area { color: #6366f1; font-size: 12px; }

.complaint-card {
    background: #0f1523;
    border: 1px solid #1e2a45;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
}
.comp-area { color: #e2e8f0; font-size: 13px; font-weight: 600; }
.comp-msg  { color: #64748b; font-size: 12px; margin: 6px 0; }
.comp-id   { color: #334155; font-size: 10px; font-family: monospace; }
.badge     { display: inline-block; padding: 2px 10px; border-radius: 20px;
             font-size: 11px; font-weight: 600; }
.eta-tag   { color: #f59e0b; font-size: 11px; margin-top: 4px; }

.area-status-card {
    background: #111827;
    border: 1px solid #1e2a45;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 8px;
}
.area-status-name { color: #e2e8f0; font-size: 14px; font-weight: 600; }
.area-status-sub  { color: #475569; font-size: 11px; margin-top: 2px; }
.area-status-desc { color: #64748b; font-size: 12px; margin-top: 8px; }

.offline {
    background: #2a1a1a; border: 1px solid #ef4444;
    border-radius: 10px; padding: 10px 16px;
    color: #fca5a5; font-size: 13px; margin-bottom: 14px;
}
</style>
""",
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────
#  Session state
# ─────────────────────────────────────────────────────────────
def reset_session():
    for key in [
        "phase",
        "customer_name",
        "customer_area",
        "chat_messages",
        "submitted_ids",
        "shown_ids",
    ]:
        st.session_state.pop(key, None)
    st.rerun()


if "phase" not in st.session_state:
    st.session_state.phase = "ask_name"  # ask_name | ask_area | active

if "customer_name" not in st.session_state:
    st.session_state.customer_name = ""

if "customer_area" not in st.session_state:
    st.session_state.customer_area = ""

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "text": (
                "👋 Welcome to **CEB Power Outage Support**.\n\n"
                "I'm here to help you report power issues and get real-time updates "
                "from our technical team.\n\n"
                "**What's your name?**"
            ),
        }
    ]

if "submitted_ids" not in st.session_state:
    st.session_state.submitted_ids = set()

if "shown_ids" not in st.session_state:
    st.session_state.shown_ids = set()


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────
def add_msg(role: str, text: str):
    st.session_state.chat_messages.append({"role": role, "text": text})


def status_badge(status: str) -> str:
    cfg = STATUS_CONFIG.get(status, STATUS_CONFIG["RECEIVED"])
    return (
        f'<span class="badge" style="background:{cfg["bg"]};color:{cfg["color"]};'
        f'border:1px solid {cfg["color"]}40">{html_lib.escape(cfg["label"])}</span>'
    )


def sync_responses(complaints: list):
    """Pull resolved customer_message values into the chat (each shown only once)."""
    for comp in complaints:
        cid = comp.get("id", "")
        if (
            cid in st.session_state.submitted_ids
            and cid not in st.session_state.shown_ids
            and comp.get("customer_message")
        ):
            add_msg("assistant", comp["customer_message"])
            st.session_state.shown_ids.add(cid)


# ─────────────────────────────────────────────────────────────
#  Fetch live data and sync responses
# ─────────────────────────────────────────────────────────────
online = backend_online()
all_complaints = api_get("/complaints") or []

sync_responses(all_complaints)  # runs before render so new messages appear immediately

# local aliases for brevity
phase = st.session_state.phase
customer_name = st.session_state.customer_name
customer_area = st.session_state.customer_area


# ─────────────────────────────────────────────────────────────
#  Top bar
# ─────────────────────────────────────────────────────────────
if phase == "active":
    right_section = (
        f'<span class="cust-chip">👤 {html_lib.escape(customer_name)}'
        f" &nbsp;·&nbsp; {html_lib.escape(customer_area)}</span>"
    )
else:
    right_section = ""

st.markdown(
    f'<div class="topbar">'
    f'<div><div class="topbar-title">⚡ CEB Power Outage Support</div>'
    f'<div class="topbar-sub">Ceylon Electricity Board · Customer Portal · Sri Lanka</div></div>'
    f'<div style="display:flex;gap:12px;align-items:center">{right_section}'
    f'<a href="http://localhost:8502" target="_blank" style="color:#6366f1;font-size:11px;'
    f'text-decoration:none;border:1px solid #6366f140;padding:4px 12px;border-radius:12px">'
    f"🔧 Staff Portal</a></div></div>",
    unsafe_allow_html=True,
)

if not online:
    st.markdown(
        '<div class="offline">⚠ Service temporarily unavailable. '
        "Please try again shortly.</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────
#  Layout
#  Onboarding (ask_name / ask_area): centred single column
#  Active chat: chat column (3) + status panel (2)
# ─────────────────────────────────────────────────────────────
if phase == "active":
    col_chat, col_right = st.columns([3, 2], gap="large")
    show_right = True
else:
    _l, col_chat, _r = st.columns([1, 4, 1])
    col_right = None
    show_right = False


# ═══════════════════════════════════════════════════════════════
#  CHAT COLUMN — messages + area buttons only (NO chat_input here)
# ═══════════════════════════════════════════════════════════════
with col_chat:
    # Render chat history
    for msg in st.session_state.chat_messages:
        is_user = msg["role"] == "user"
        with st.chat_message(
            "user" if is_user else "assistant", avatar="👤" if is_user else "⚡"
        ):
            st.markdown(msg["text"])

    # Area selection buttons (ask_area phase only)
    if phase == "ask_area":
        st.markdown(
            '<div class="area-btn-wrap">'
            '<div class="area-btn-title">Select your area</div>',
            unsafe_allow_html=True,
        )

        area_list = list(AREAS.keys())
        for row_start in range(0, len(area_list), 3):
            row_areas = area_list[row_start : row_start + 3]
            btn_cols = st.columns(len(row_areas))
            for bcol, aname in zip(btn_cols, row_areas):
                fault = AREAS[aname].get("current_fault")
                fi = FAULT_TYPE_INFO.get(
                    fault["type"] if fault else None, FAULT_TYPE_INFO[None]
                )
                if bcol.button(
                    f"{fi['icon']} {aname}",
                    use_container_width=True,
                    key=f"area_{aname}",
                ):
                    st.session_state.customer_area = aname
                    add_msg("user", f"📍 {aname}")
                    add_msg(
                        "assistant",
                        f"Got it — you're in **{aname}**. 📍\n\n"
                        "Please describe your power issue and our technical agents will "
                        "diagnose it in real time. You'll receive an update here shortly.",
                    )
                    st.session_state.phase = "active"
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
#  CHAT INPUT — must be at page level (outside any column/with block)
#  so Streamlit renders it correctly at the bottom of the viewport.
# ═══════════════════════════════════════════════════════════════
prompt = None

if phase == "ask_name":
    prompt = st.chat_input("Type your name here…", key="input_name")

elif phase == "active":
    prompt = st.chat_input(
        f"Describe your issue in {customer_area}…",
        key="input_complaint",
        disabled=not online,
    )

# ── Process whatever the user typed ──────────────────────────
if prompt:
    prompt = prompt.strip()

    if phase == "ask_name" and prompt:
        st.session_state.customer_name = prompt
        add_msg("user", prompt)
        add_msg(
            "assistant",
            f"Nice to meet you, **{prompt}**! 😊\n\n"
            "Which **area** are you in? Please select below:",
        )
        st.session_state.phase = "ask_area"
        st.rerun()

    elif phase == "active" and prompt:
        add_msg("user", prompt)

        if not online:
            add_msg(
                "assistant",
                "⚠ Sorry, the service is temporarily unavailable. Please try again shortly.",
            )
            st.rerun()

        result = api_post(
            "/complaints",
            {
                "customer_name": customer_name,
                "area": customer_area,
                "message": prompt,
            },
        )

        if result and "id" in result:
            cid = result["id"]
            st.session_state.submitted_ids.add(cid)
            add_msg(
                "assistant",
                f"✅ **Complaint registered** (ref: `{cid[:8]}…`)\n\n"
                "Our technical team is diagnosing the issue now. "
                "I'll update you here as soon as our technical team reports back.",
            )
        else:
            add_msg(
                "assistant",
                "⚠ We couldn't submit your complaint right now. Please try again.",
            )

        st.rerun()


# ═══════════════════════════════════════════════════════════════
#  RIGHT PANEL — only visible in active phase
# ═══════════════════════════════════════════════════════════════
if show_right and col_right is not None:
    with col_right:

        # Customer info + New Session
        col_info, col_ns = st.columns([3, 1])
        with col_info:
            st.markdown(
                f'<div class="cust-card">'
                f'<div class="cust-card-name">👤 {html_lib.escape(customer_name)}</div>'
                f'<div class="cust-card-area">📍 {html_lib.escape(customer_area)}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
        with col_ns:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("↩ New\nSession", use_container_width=True):
                reset_session()

        # My complaints (this session only)
        st.markdown(
            '<div class="panel-title">📋 My Complaints</div>', unsafe_allow_html=True
        )

        my_c = [
            c
            for c in reversed(all_complaints)
            if c.get("id") in st.session_state.submitted_ids
        ]

        if not my_c:
            st.markdown(
                '<div style="color:#475569;font-size:13px;padding:16px 0;text-align:center">'
                "No complaints yet.<br>Describe your issue in the chat below.</div>",
                unsafe_allow_html=True,
            )
        else:
            cards = []
            for comp in my_c:
                status = comp.get("status", "RECEIVED")
                fault_type = comp.get("fault_type")
                eta = comp.get("eta_minutes")
                fi = FAULT_TYPE_INFO.get(fault_type, FAULT_TYPE_INFO[None])
                spin = "⏳ " if status in ("ROUTING", "DIAGNOSING") else ""
                msg_prev = html_lib.escape(comp.get("message", "")[:65])
                if len(comp.get("message", "")) > 65:
                    msg_prev += "…"
                fault_html = (
                    f'<span style="color:#f59e0b;font-size:12px">'
                    f'{fi["icon"]} {html_lib.escape(fi["label"])}</span>'
                    if fault_type
                    else '<span style="color:#10b981;font-size:12px">✅ No fault detected</span>'
                )
                eta_html = f'<div class="eta-tag">⏱ Est. {eta} min</div>' if eta else ""
                cards.append(f"""
<div class="complaint-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
    <span class="comp-area">{spin}{html_lib.escape(comp.get('area',''))}</span>
    {status_badge(status)}
  </div>
  <div class="comp-msg">"{msg_prev}"</div>
  <div>{fault_html}</div>
  {eta_html}
  <div class="comp-id" style="margin-top:6px">ref: {comp.get('id','')[:8]}…</div>
</div>""")
            st.markdown("".join(cards), unsafe_allow_html=True)

        # Selected area fault status
        st.markdown(
            '<br><div class="panel-title">🗺 Your Area Status</div>',
            unsafe_allow_html=True,
        )

        area_data = AREAS.get(customer_area, {})
        fault = area_data.get("current_fault")
        fi = FAULT_TYPE_INFO.get(
            fault["type"] if fault else None, FAULT_TYPE_INFO[None]
        )
        sub_safe = html_lib.escape(area_data.get("substation", ""))

        if fault:
            desc_safe = html_lib.escape(fault.get("description", ""))
            eta_part = (
                f'<div style="color:#f59e0b;font-size:12px;margin-top:6px">'
                f'⏱ ETA: {fault["eta_minutes"]} min</div>'
                if fault.get("eta_minutes")
                else ""
            )
            crew_part = (
                '<div style="color:#10b981;font-size:11px;margin-top:4px">✅ Crew on site</div>'
                if fault.get("crew_on_site")
                else '<div style="color:#f59e0b;font-size:11px;margin-top:4px">🚗 Crew en route</div>'
            )
        else:
            desc_safe = html_lib.escape(
                area_data.get("note", "All feeders operating normally.")
            )
            eta_part = ""
            crew_part = ""

        st.markdown(
            f"""
<div class="area-status-card" style="border-color:#4f46e550">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <div class="area-status-name">{html_lib.escape(customer_area)}</div>
      <div class="area-status-sub">{sub_safe}</div>
    </div>
    <span style="font-size:13px;color:#94a3b8">{fi['icon']} {html_lib.escape(fi['label'])}</span>
  </div>
  <div class="area-status-desc">{desc_safe}</div>
  {eta_part}
  {crew_part}
</div>""",
            unsafe_allow_html=True,
        )

        # Other areas — compact list
        st.markdown(
            '<div class="panel-title" style="margin-top:12px">Other Areas</div>',
            unsafe_allow_html=True,
        )
        other_parts = []
        for aname, adata in AREAS.items():
            if aname == customer_area:
                continue
            f2 = adata.get("current_fault")
            fi2 = FAULT_TYPE_INFO.get(f2["type"] if f2 else None, FAULT_TYPE_INFO[None])
            c2 = {
                "red": "#ef4444",
                "orange": "#f97316",
                "green": "#10b981",
                "blue": "#3b82f6",
            }.get(fi2.get("color", "green"), "#10b981")
            other_parts.append(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:7px 0;border-bottom:1px solid #1e2535">'
                f'<span style="color:#94a3b8;font-size:12px">{html_lib.escape(aname)}</span>'
                f'<span style="font-size:11px;color:{c2}">'
                f'{fi2["icon"]} {html_lib.escape(fi2["label"])}</span></div>'
            )
        st.markdown("".join(other_parts), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  Auto-refresh while this customer's complaints are in-flight
#  OR resolved but customer_message not yet shown in chat.
# ─────────────────────────────────────────────────────────────
if phase == "active":
    in_flight = [
        c
        for c in all_complaints
        if c.get("id") in st.session_state.submitted_ids
        and c.get("id") not in st.session_state.shown_ids
        and (
            # Still being processed by agents
            c.get("status") in ("RECEIVED", "ROUTING", "DIAGNOSING")
            # OR resolved but customer_message not yet populated by backend
            or not c.get("customer_message")
        )
    ]
    if in_flight:
        time.sleep(1.5)
        st.rerun()
