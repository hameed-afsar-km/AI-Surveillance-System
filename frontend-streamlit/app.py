"""
app.py – Streamlit Dashboard for AI Surveillance System
========================================================
Professional real-time surveillance control centre.
Uses @st.fragment(run_every=...) for auto-refresh of live sections
WITHOUT reloading the whole page every cycle.
"""

import base64
import os
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
import streamlit as st
from PIL import Image

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Surveillance System",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ─────────────────────────────────────────────────────────────────

API_BASE       = "http://localhost:5050"
LIVE_REFRESH   = 1    # seconds between live metrics refreshes
MAX_EVENTS     = 30

# ── Inject CSS once (st.html bypasses Markdown parser) ────────────────────────

st.html("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
  :root {
    --bg-primary:    #080d1a;
    --bg-secondary:  #0e1628;
    --bg-card:       #121e35;
    --accent-blue:   #3b82f6;
    --accent-cyan:   #06b6d4;
    --accent-green:  #10b981;
    --accent-red:    #ef4444;
    --accent-purple: #8b5cf6;
    --text-primary:  #f1f5f9;
    --text-secondary:#94a3b8;
    --border-color:  rgba(59,130,246,0.15);
    --glow-blue:     0 0 20px rgba(59,130,246,0.3);
    --glow-red:      0 0 20px rgba(239,68,68,0.4);
    --glow-green:    0 0 20px rgba(16,185,129,0.3);
  }

  html, body, .stApp {
    background: var(--bg-primary) !important;
    font-family: 'Inter', sans-serif !important;
    color: var(--text-primary) !important;
  }

  #MainMenu, footer, .stDeployButton { display: none !important; }
  header[data-testid="stHeader"] { background: transparent !important; }

  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg-secondary); }
  ::-webkit-scrollbar-thumb { background: var(--accent-blue); border-radius: 3px; }

  /* Metric cards */
  .metric-card {
    background: linear-gradient(135deg, #0e1628 0%, #121e35 100%);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 18px 20px;
    text-align: center;
    position: relative;
    overflow: hidden;
    transition: transform 0.2s, box-shadow 0.2s;
    margin-bottom: 10px;
  }
  .metric-card:hover { transform: translateY(-2px); box-shadow: var(--glow-blue); }
  .metric-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan));
  }
  .metric-value {
    font-size: 2.4rem;
    font-weight: 800;
    line-height: 1.1;
    font-family: 'JetBrains Mono', monospace;
  }
  .metric-label {
    font-size: 0.72rem;
    color: var(--text-secondary);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 4px;
  }
  .metric-icon { font-size: 1.4rem; margin-bottom: 6px; display: block; }

  /* Alert banners */
  .alert-banner {
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 12px;
    animation: pulse-border 2s infinite;
  }
  .alert-banner.critical {
    background: linear-gradient(135deg,rgba(239,68,68,.15),rgba(185,28,28,.1));
    border: 2px solid rgba(239,68,68,.6);
    box-shadow: var(--glow-red);
  }
  .alert-banner.high {
    background: linear-gradient(135deg,rgba(249,115,22,.15),rgba(194,65,12,.1));
    border: 2px solid rgba(249,115,22,.6);
  }
  .alert-banner.medium {
    background: linear-gradient(135deg,rgba(245,158,11,.15),rgba(180,83,9,.1));
    border: 2px solid rgba(245,158,11,.5);
  }
  .alert-banner.low {
    background: linear-gradient(135deg,rgba(59,130,246,.12),rgba(37,99,235,.08));
    border: 2px solid rgba(59,130,246,.4);
  }
  .alert-banner.safe {
    background: linear-gradient(135deg,rgba(16,185,129,.12),rgba(5,150,105,.08));
    border: 2px solid rgba(16,185,129,.4);
    box-shadow: var(--glow-green);
  }
  @keyframes pulse-border { 0%,100%{opacity:1;} 50%{opacity:.82;} }

  /* Status dot */
  .status-dot {
    display: inline-block;
    width: 10px; height: 10px;
    border-radius: 50%;
    margin-right: 7px;
    animation: blink 1.2s infinite;
  }
  .status-dot.running { background: var(--accent-green); box-shadow: 0 0 8px var(--accent-green); }
  .status-dot.stopped { background: var(--text-secondary); animation: none; }
  @keyframes blink { 0%,100%{opacity:1;} 50%{opacity:.3;} }

  /* Event rows */
  .event-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 8px;
    margin-bottom: 6px;
    background: var(--bg-secondary);
    border-left: 3px solid;
    transition: background 0.15s;
  }
  .event-row:hover { background: var(--bg-card); }
  .event-row.overcrowding   { border-color: #f97316; }
  .event-row.loitering      { border-color: #eab308; }
  .event-row.restricted_zone{ border-color: #ef4444; }
  .event-row.sudden_crowd   { border-color: #a855f7; }
  .event-row.custom         { border-color: #3b82f6; }
  .event-row.none           { border-color: #475569; }
  .event-time {
    font-size: 0.7rem;
    color: var(--text-secondary);
    font-family: 'JetBrains Mono', monospace;
    white-space: nowrap;
    padding-top: 2px;
    min-width: 70px;
  }
  .event-msg  { font-size: 0.82rem; color: var(--text-primary); line-height: 1.4; }
  .event-type {
    font-size: 0.65rem;
    padding: 2px 8px;
    border-radius: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    white-space: nowrap;
  }

  /* Video placeholder */
  .video-container {
    background: #000;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 260px;
  }

  /* Section headers */
  .section-header {
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-secondary);
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .section-header::after {
    content:""; flex:1; height:1px; background: var(--border-color);
  }

  /* AI insight */
  .ai-insight {
    background: linear-gradient(135deg,rgba(59,130,246,.06),rgba(139,92,246,.06));
    border: 1px solid rgba(139,92,246,.25);
    border-radius: 10px;
    padding: 14px 16px;
    font-size: 0.88rem;
    line-height: 1.65;
    color: #c4b5fd;
    font-style: italic;
  }

  /* Navbar */
  .navbar {
    background: linear-gradient(90deg,#080d1a 0%,#0d1829 50%,#080d1a 100%);
    border-bottom: 1px solid var(--border-color);
    padding: 14px 28px;
    margin: -1rem -1rem 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .navbar-brand {
    font-size: 1.3rem;
    font-weight: 800;
    background: linear-gradient(90deg,#3b82f6,#06b6d4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.02em;
  }

  /* Override Streamlit buttons */
  .stButton button {
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    border: none !important;
    transition: all 0.2s !important;
    padding: 0.5rem 1.2rem !important;
  }
</style>
""")

# ── Session State ─────────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "running":       False,
        "last_status":   {},
        "sound_enabled": True,
        "ai_enabled":    True,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── API helpers ───────────────────────────────────────────────────────────────

def _api(method: str, path: str, **kwargs):
    try:
        r = requests.request(method, f"{API_BASE}{path}", timeout=3, **kwargs)
        try:
            return r.json()
        except:
            return None
    except Exception:
        return None

def _fetch_status() -> dict:
    return _api("GET", "/status") or {}

def _fetch_frame() -> Optional[Image.Image]:
    data = _api("GET", "/frame")
    if data and data.get("frame"):
        try:
            return Image.open(BytesIO(base64.b64decode(data["frame"])))
        except Exception:
            return None
    return None

def _fetch_events(n: int = MAX_EVENTS) -> list:
    return _api("GET", f"/events?n={n}") or []

def _start_system(mode: str, source: str) -> dict:
    return _api("POST", "/start", json={"mode": mode, "source": source}) or {}

def _stop_system() -> dict:
    return _api("POST", "/stop") or {}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _severity_css(s: str) -> str:
    return {"none":"safe","low":"low","medium":"medium","high":"high","critical":"critical"}.get(s,"safe")

def _severity_emoji(s: str) -> str:
    return {"none":"✅","low":"🔵","medium":"🟡","high":"🟠","critical":"🔴"}.get(s,"✅")

def _event_badge(t: str) -> str:
    c = {"overcrowding":"#f97316","loitering":"#eab308","restricted_zone":"#ef4444",
         "sudden_crowd":"#a855f7","custom":"#3b82f6"}.get(t,"#475569")
    return (f'<span class="event-type" style="background:rgba(255,255,255,.07);'
            f'color:{c};border:1px solid {c};">{t.replace("_"," ").title()}</span>')

def _fmt_time(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z","+00:00")).strftime("%H:%M:%S")
    except Exception:
        return iso[-8:] if len(iso) >= 8 else iso

def _fmt_uptime(s: float) -> str:
    s = int(s)
    h, r = divmod(s, 3600); m, sc = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{sc:02d}"

# ── Static: Navbar ─────────────────────────────────────────────────────────────

def render_navbar():
    """Rendered once – does NOT auto-refresh."""
    st.html("""
    <div class="navbar">
      <div>
        <span class="navbar-brand">⬡ AI Surveillance</span>
        <span style="color:#475569;font-size:.78rem;margin-left:14px;">
          Environmental Monitoring System
        </span>
      </div>
      <div style="color:#475569;font-size:.75rem;">
        Real-Time Detection · DeepSORT · YOLOv8 · Gemini AI
      </div>
    </div>
    """)

# ── Static: Control Panel ──────────────────────────────────────────────────────

def render_control_panel():
    """Rendered once – user interacts here without constant refresh."""
    st.markdown('<div class="section-header">⚙️ Control Panel</div>', unsafe_allow_html=True)

    mode = st.radio("Video Source", ["webcam", "simulation"], horizontal=True,
                    key="src_mode")

    if mode == "simulation":
        video_dir = Path(__file__).resolve().parent.parent / "videos"
        all_videos = []
        if video_dir.exists():
            all_videos = [f for f in os.listdir(video_dir) if f.endswith(".mp4")]
        
        if not all_videos:
            st.warning("No .mp4 files found in /videos folder.")
            source_val = ""
            source_mode = "file"
        else:
            video_file = st.selectbox(
                "Simulation Video",
                sorted(all_videos),
                key="sim_video"
            )
            source_val  = video_file
            source_mode = "file"
    else:
        cam_idx = st.number_input("Webcam Index", min_value=0, max_value=9,
                                  value=0, key="cam_idx")
        source_val  = str(cam_idx)
        source_mode = "webcam"

    st.markdown("<hr style='border-color:#1e293b;margin:12px 0;'/>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("▶ Start System", use_container_width=True,
                     type="primary", key="btn_start"):
            resp = _start_system(source_mode, source_val)
            if resp.get("status") == "started":
                st.session_state.running = True
                st.success("Started!")
            elif resp.get("error"):
                st.error(resp["error"])
            else:
                st.warning("Backend unreachable. Is Flask running on port 5050?")
    with c2:
        if st.button("⏹ Stop", use_container_width=True, key="btn_stop"):
            resp = _stop_system()
            if resp.get("status") == "stopped":
                st.session_state.running = False
                st.success("Stopped.")

    snd = st.toggle("🔊 Sound Alerts", value=st.session_state.sound_enabled, key="snd")
    if snd != st.session_state.sound_enabled:
        st.session_state.sound_enabled = snd
        _api("POST", "/settings", json={"sound_enabled": snd})

    ai = st.toggle("🧠 AI Insights", value=st.session_state.ai_enabled, key="ai_tgl")
    if ai != st.session_state.ai_enabled:
        st.session_state.ai_enabled = ai
        _api("POST", "/settings", json={"ai_enabled": ai})

    st.markdown("<hr style='border-color:#1e293b;margin:12px 0;'/>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">ℹ️ Backend Status</div>', unsafe_allow_html=True)
    health = _api("GET", "/health")
    if health:
        st.success(f"✅ Backend online · uptime {_fmt_uptime(health.get('uptime',0))}")
    else:
        st.error("❌ Backend offline — run `python app.py` in /backend")

# ── Live fragments (auto-refresh every LIVE_REFRESH seconds) ──────────────────

def live_feed_panel():
    running = st.session_state.get("running", False)

    st.markdown('<div class="section-header">🎥 Live Feed</div>', unsafe_allow_html=True)

    if running:
        stream_url = f"{API_BASE}/stream"
        st.html(f"""
        <div style="background:#000; border-radius:12px; overflow:hidden; border:1px solid rgba(59,130,246,0.15); display:flex; align-items:center; justify-content:center; min-height:260px;">
            <img src="{stream_url}" style="width:100%; height:auto; display:block;" />
        </div>""")
    else:
        st.html("""
        <div class="video-container">
          <div style="text-align:center;color:#475569;">
            <div style="font-size:3rem;">📷</div>
            <div style="margin-top:10px;font-size:.9rem;font-weight:600;">System Offline</div>
            <div style="font-size:.75rem;margin-top:4px;">Press ▶ Start System to begin</div>
          </div>
        </div>""")


@st.fragment(run_every=LIVE_REFRESH)
def live_metrics_panel():
    status = _fetch_status()
    count  = status.get("people_count", 0)
    ids    = status.get("active_ids", [])
    alert  = status.get("alert", False)
    uptime = status.get("uptime", 0)
    fps    = status.get("fps", 0.0)
    frames = status.get("frame_count", 0)
    running= status.get("running", False)

    dot   = "running" if running else "stopped"
    label = "LIVE" if running else "OFFLINE"
    col   = "#10b981" if running else "#64748b"

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:18px;margin-bottom:10px;">'
        f'<span style="font-size:.82rem;color:{col};">'
        f'<span class="status-dot {dot}"></span>{label}</span>'
        f'<span style="font-size:.75rem;color:#475569;">FPS: {fps:.1f} &nbsp;|&nbsp; '
        f'Frames: {frames:,} &nbsp;|&nbsp; ⏱ {_fmt_uptime(uptime)}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-header">📊 Live Metrics</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)

    count_color = "#ef4444" if count > 5 else ("#f59e0b" if count > 2 else "#10b981")
    alert_color = "#ef4444" if alert else "#10b981"
    alert_label = "ALERT" if alert else "NORMAL"

    with c1:
        st.markdown(f"""
        <div class="metric-card">
          <span class="metric-icon">👥</span>
          <div class="metric-value" style="color:{count_color};">{count}</div>
          <div class="metric-label">People Detected</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
          <span class="metric-icon">🆔</span>
          <div class="metric-value" style="color:#3b82f6;">{len(ids)}</div>
          <div class="metric-label">Active Track IDs</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
          <span class="metric-icon">🛡️</span>
          <div class="metric-value" style="color:{alert_color};font-size:1.4rem;">{alert_label}</div>
          <div class="metric-label">System Status</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
          <span class="metric-icon">⏱️</span>
          <div class="metric-value" style="color:#8b5cf6;font-size:1.6rem;">{_fmt_uptime(uptime)}</div>
          <div class="metric-label">Session Uptime</div>
        </div>""", unsafe_allow_html=True)

    # Active IDs badge strip
    if ids:
        st.markdown("<div class='section-header' style='margin-top:10px;'>🆔 Active Track IDs</div>",
                    unsafe_allow_html=True)
        badges = " ".join(
            f'<span style="display:inline-block;background:rgba(59,130,246,.12);'
            f'border:1px solid rgba(59,130,246,.4);border-radius:6px;padding:3px 10px;'
            f'font-size:.78rem;color:#93c5fd;margin:2px;'
            f'font-family:\'JetBrains Mono\',monospace;">ID:{i}</span>'
            for i in sorted(ids)
        )
        st.markdown(badges, unsafe_allow_html=True)


@st.fragment(run_every=LIVE_REFRESH)
def live_alert_panel():
    status     = _fetch_status()
    alert      = status.get("alert", False)
    alert_type = status.get("alert_type", "none")
    message    = status.get("message", "System nominal.")
    severity   = status.get("severity", "none")
    ai_insight = status.get("ai_insight", "")
    summary    = status.get("periodic_summary", "")
    css_cls    = _severity_css(severity)
    emoji      = _severity_emoji(severity)

    st.markdown('<div class="section-header">🚨 Alert Status</div>', unsafe_allow_html=True)

    if alert:
        type_label = alert_type.replace("_", " ").upper()
        insight_html = (f'<div class="ai-insight">🤖 <strong>AI Insight:</strong> {ai_insight}</div>'
                        if ai_insight else "")
        st.markdown(f"""
        <div class="alert-banner {css_cls}">
          <div style="font-size:1.05rem;font-weight:700;margin-bottom:6px;">{emoji} {type_label}</div>
          <div style="font-size:.85rem;color:#e2e8f0;margin-bottom:10px;">{message}</div>
          {insight_html}
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="alert-banner safe">
          <div style="font-size:1rem;font-weight:700;">✅ All Clear</div>
          <div style="font-size:.83rem;color:#a7f3d0;margin-top:4px;">{message}</div>
        </div>""", unsafe_allow_html=True)

    if summary:
        st.markdown(f"""
        <div style="margin-top:10px;">
          <div class="section-header">🤖 Periodic AI Summary</div>
          <div class="ai-insight">{summary}</div>
        </div>""", unsafe_allow_html=True)


@st.fragment(run_every=LIVE_REFRESH)
def live_event_log():
    events = _fetch_events()
    st.markdown('<div class="section-header">📋 Event Timeline</div>', unsafe_allow_html=True)

    if not events:
        st.markdown("""
        <div style="text-align:center;padding:24px;color:#475569;font-size:.85rem;">
          No events recorded yet.
        </div>""", unsafe_allow_html=True)
        return

    for ev in reversed(events[-MAX_EVENTS:]):
        et    = ev.get("type", "none")
        msg   = ev.get("message", "")
        ts    = ev.get("timestamp", "")
        count = ev.get("people_count", 0)
        st.markdown(f"""
        <div class="event-row {et}">
          <div class="event-time">{_fmt_time(ts)}</div>
          <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px;">
              {_event_badge(et)}
              <span style="font-size:.72rem;color:#64748b;">👥 {count}</span>
            </div>
            <div class="event-msg">{msg[:130]}{"…" if len(msg)>130 else ""}</div>
          </div>
        </div>""", unsafe_allow_html=True)


# ── Main layout (runs once on page load) ──────────────────────────────────────

def main():
    render_navbar()

    left, center, right = st.columns([1.05, 1.85, 1.1])

    with left:
        render_control_panel()

    with center:
        live_feed_panel()
        st.markdown("<div style='height:10px;'/>", unsafe_allow_html=True)
        live_metrics_panel()
        st.markdown("<div style='height:4px;'/>", unsafe_allow_html=True)
        live_alert_panel()

    with right:
        live_event_log()

if __name__ == "__main__":
    main()
