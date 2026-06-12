import streamlit as st
import requests
import time
import difflib
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Prompt Management",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# DESIGN SYSTEM CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap');

:root {
  --bg:         #080c10;
  --surface:    #0d1117;
  --surface2:   #111823;
  --border:     #1c2433;
  --border2:    #243044;
  --text:       #c9d4e0;
  --text-dim:   #4a6080;
  --text-faint: #2a3a50;
  --accent:     #00c2ff;
  --accent2:    #0077aa;
  --green:      #00e5a0;
  --red:        #ff4d6a;
  --yellow:     #ffb800;
  --purple:     #a78bfa;
}

html, body, [class*="css"] {
  font-family: 'JetBrains Mono', monospace;
  background-color: var(--bg) !important;
  color: var(--text);
}

#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 !important; max-width: 100% !important; }
[data-testid="stAppViewContainer"] { background: var(--bg); }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
  padding: 0 !important;
  min-width: 240px !important;
  width: 240px !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 0 !important; }
 /* Keep sidebar visible — override any collapse transitions */
[data-testid="stSidebar"][aria-expanded="false"] {
  min-width: 240px !important;
  width: 240px !important;
}
section[data-testid="stSidebar"] { display: block !important; }

::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

.stTextInput input, .stTextArea textarea {
  background: var(--surface2) !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
  border-radius: 6px !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 13px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--accent2) !important;
  box-shadow: 0 0 0 2px rgba(0,119,170,0.15) !important;
}

.stButton > button {
  background: var(--surface2) !important;
  color: var(--accent) !important;
  border: 1px solid var(--border2) !important;
  border-radius: 6px !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 12px !important;
  font-weight: 500 !important;
  letter-spacing: 0.5px !important;
  padding: 6px 16px !important;
  transition: all 0.15s ease !important;
}
.stButton > button:hover {
  background: var(--border2) !important;
  color: #fff !important;
  border-color: var(--accent) !important;
}

/* Active module button highlight */
.module-active > button {
  background: #001f33 !important;
  color: var(--accent) !important;
  border-color: var(--accent) !important;
}

[data-testid="stFileUploader"] {
  background: var(--surface2) !important;
  border: 1px dashed var(--border2) !important;
  border-radius: 8px !important;
}

.stTabs [data-baseweb="tab-list"] {
  background: var(--surface) !important;
  border-bottom: 1px solid var(--border) !important;
  gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  color: var(--text-dim) !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 11px !important;
  letter-spacing: 1px !important;
  text-transform: uppercase !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  padding: 12px 20px !important;
}
.stTabs [aria-selected="true"] {
  color: var(--accent) !important;
  border-bottom: 2px solid var(--accent) !important;
  background: transparent !important;
}
.stTabs [data-baseweb="tab-panel"] {
  background: var(--bg) !important;
  padding: 24px !important;
}

.streamlit-expanderHeader {
  background: var(--surface2) !important;
  border: 1px solid var(--border) !important;
  border-radius: 6px !important;
  color: var(--text) !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 12px !important;
}

[data-testid="metric-container"] {
  background: var(--surface2) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  padding: 16px !important;
}
[data-testid="metric-container"] label {
  color: var(--text-dim) !important;
  font-size: 10px !important;
  letter-spacing: 1.5px !important;
  text-transform: uppercase !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
  color: var(--text) !important;
  font-size: 24px !important;
  font-family: 'Syne', sans-serif !important;
}

[data-testid="stSelectbox"] > div > div {
  background: var(--surface2) !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
}

hr { border-color: var(--border) !important; margin: 16px 0 !important; }

.stSuccess, .stError, .stWarning, .stInfo {
  border-radius: 6px !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# HTML COMPONENT HELPERS
# ─────────────────────────────────────────────────────────────

def topbar():
    st.markdown("""
    <div style="background:#0d1117;border-bottom:1px solid #1c2433;
                padding:14px 32px;display:flex;align-items:center;
                justify-content:space-between;position:sticky;top:0;z-index:100">
      <div style="display:flex;align-items:center;gap:12px">
        <div style="width:28px;height:28px;background:#00c2ff;
                    clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);"></div>
        <span style="font-family:'Syne',sans-serif;font-size:16px;
                     font-weight:700;color:#fff;letter-spacing:2px">PROMPT MANAGEMENT</span>
      </div>
      <div style="font-size:10px;color:#2a3a50;letter-spacing:1px">{ts}</div>
    </div>
    """.format(ts=datetime.now().strftime("%Y-%m-%d  %H:%M:%S")), unsafe_allow_html=True)


def badge(text, color="blue"):
    colors = {
        "blue":   ("#00c2ff", "#001f33", "#003d66"),
        "green":  ("#00e5a0", "#001a0f", "#003322"),
        "red":    ("#ff4d6a", "#1a000a", "#3d0016"),
        "yellow": ("#ffb800", "#1a1000", "#3d2800"),
        "purple": ("#a78bfa", "#0f0a1a", "#231544"),
        "gray":   ("#4a6080", "#0d1117", "#1c2433"),
    }
    fg, bg, border = colors.get(color, colors["blue"])
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:20px;'
        f'font-size:10px;font-weight:500;letter-spacing:0.8px;'
        f'color:{fg};background:{bg};border:1px solid {border};'
        f'font-family:JetBrains Mono,monospace">{text}</span>'
    )


def section_label(text):
    st.markdown(
        f'<div style="font-size:9px;letter-spacing:2.5px;text-transform:uppercase;'
        f'color:#2a3a50;margin:24px 0 10px;padding-bottom:8px;'
        f'border-bottom:1px solid #1c2433;font-family:JetBrains Mono,monospace">'
        f'{text}</div>',
        unsafe_allow_html=True,
    )


def step_tracker(steps):
    icons  = {"done": "✓", "active": "◎", "pending": "○", "error": "✗"}
    colors = {
        "done":    ("#00e5a0", "#001a0f", "#003322"),
        "active":  ("#00c2ff", "#001f33", "#003d66"),
        "pending": ("#2a3a50", "#0d1117", "#1c2433"),
        "error":   ("#ff4d6a", "#1a000a", "#3d0016"),
    }
    html = '<div style="display:flex;flex-direction:column;gap:6px;padding:4px 0">'
    for s in steps:
        st_key = s.get("status", "pending")
        fg, bg, bdr = colors[st_key]
        ts_html = (
            f'<span style="color:#2a3a50;font-size:10px;margin-left:auto">'
            f'{s.get("ts","")}</span>'
        ) if s.get("ts") else ""
        txt_color = "#c9d4e0" if st_key != "pending" else "#2a3a50"
        html += (
            f'<div style="display:flex;align-items:center;gap:10px;'
            f'padding:8px 12px;border-radius:6px;background:{bg};border:1px solid {bdr}">'
            f'<span style="color:{fg};font-size:12px;width:16px;text-align:center">'
            f'{icons[st_key]}</span>'
            f'<span style="color:{txt_color};font-size:12px;flex:1">{s["label"]}</span>'
            f'{ts_html}</div>'
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def answer_box(question, answer, source, duration, ts):
    st.markdown(
        f'<div style="background:#001a0f;border:1px solid #003322;border-left:3px solid #00e5a0;'
        f'border-radius:8px;padding:18px 20px;margin:12px 0">'
        f'<div style="display:flex;gap:8px;align-items:center;margin-bottom:10px">'
        f'{badge("ANSWER","green")}'
        f'<span style="color:#2a3a50;font-size:10px">{source} · {ts} · {duration}s</span></div>'
        f'<div style="color:#4a6080;font-size:11px;margin-bottom:6px">Q: {question}</div>'
        f'<div style="color:#f0f6ff;font-size:14px;font-weight:500;'
        f'font-family:Syne,sans-serif;line-height:1.6">{answer}</div></div>',
        unsafe_allow_html=True,
    )


def prompt_box(content):
    safe = content.replace("<", "&lt;").replace(">", "&gt;")
    st.markdown(
        f'<div style="background:#080c10;border:1px solid #1c2433;border-radius:6px;'
        f'padding:16px;font-family:JetBrains Mono,monospace;font-size:11px;'
        f'color:#4a6080;white-space:pre-wrap;max-height:220px;overflow-y:auto;'
        f'line-height:1.7">{safe}</div>',
        unsafe_allow_html=True,
    )


def version_row_html(ver, status, created_at, created_by, is_stable):
    status_color = {"stable": "green", "draft": "yellow", "archived": "gray"}.get(status, "gray")
    stable_tag   = badge("● ACTIVE", "green") if is_stable else ""
    ver_display  = ver if str(ver).endswith(".txt") else f"v{ver}"
    return (
        f'<div style="display:flex;align-items:center;gap:12px;'
        f'padding:10px 14px;border-radius:6px;'
        f'background:#0d1117;border:1px solid #1c2433;margin-bottom:6px">'
        f'<span style="color:#00c2ff;font-family:JetBrains Mono,monospace;'
        f'font-size:12px;font-weight:500;min-width:120px;display:inline-block">{ver_display}</span>'
        f'{badge(status.upper(), status_color)}'
        f'{stable_tag}'
        f'<span style="color:#2a3a50;font-size:11px;flex:1">'
        f'{str(created_at)[:19] if created_at else "—"}</span>'
        f'<span style="color:#4a6080;font-size:11px">{created_by}</span></div>'
    )


def diff_viewer(text_a, text_b, label_a="Version A", label_b="Version B"):
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()
    sm      = difflib.SequenceMatcher(None, lines_a, lines_b)
    html_a = html_b = ""

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for l in lines_a[i1:i2]:
                row = f'<div style="padding:2px 8px;color:#4a6080">{l or "&nbsp;"}</div>'
                html_a += row; html_b += row
        elif tag == "replace":
            for l in lines_a[i1:i2]:
                html_a += (
                    f'<div style="padding:2px 8px;background:#2d0a10;'
                    f'color:#ff4d6a;border-left:2px solid #ff4d6a">{l or "&nbsp;"}</div>'
                )
            for l in lines_b[j1:j2]:
                html_b += (
                    f'<div style="padding:2px 8px;background:#001a0f;'
                    f'color:#00e5a0;border-left:2px solid #00e5a0">{l or "&nbsp;"}</div>'
                )
        elif tag == "delete":
            for l in lines_a[i1:i2]:
                html_a += (
                    f'<div style="padding:2px 8px;background:#2d0a10;'
                    f'color:#ff4d6a;border-left:2px solid #ff4d6a">{l or "&nbsp;"}</div>'
                )
            html_b += f'<div style="padding:2px 8px;color:#1c2433">&nbsp;</div>' * (i2 - i1)
        elif tag == "insert":
            html_a += f'<div style="padding:2px 8px;color:#1c2433">&nbsp;</div>' * (j2 - j1)
            for l in lines_b[j1:j2]:
                html_b += (
                    f'<div style="padding:2px 8px;background:#001a0f;'
                    f'color:#00e5a0;border-left:2px solid #00e5a0">{l or "&nbsp;"}</div>'
                )

    mono = "font-family:JetBrains Mono,monospace;font-size:11px;line-height:1.6"
    st.markdown(
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px">'
        f'<div><div style="font-size:10px;letter-spacing:1px;color:#4a6080;margin-bottom:6px">'
        f'{label_a}</div>'
        f'<div style="background:#080c10;border:1px solid #1c2433;border-radius:6px;'
        f'padding:12px;{mono};max-height:300px;overflow-y:auto">{html_a}</div></div>'
        f'<div><div style="font-size:10px;letter-spacing:1px;color:#4a6080;margin-bottom:6px">'
        f'{label_b}</div>'
        f'<div style="background:#080c10;border:1px solid #1c2433;border-radius:6px;'
        f'padding:12px;{mono};max-height:300px;overflow-y:auto">{html_b}</div></div></div>'
        f'<div style="display:flex;gap:16px;margin-top:8px">'
        f'<span style="font-size:10px;color:#ff4d6a">■ Removed</span>'
        f'<span style="font-size:10px;color:#00e5a0">■ Added</span>'
        f'<span style="font-size:10px;color:#4a6080">■ Unchanged</span></div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────

def init_state():
    defaults = {
        # ── active module — persists across reruns ──────────
        "active_module":      "bank",
        # ── bank ────────────────────────────────────────────
        "bank_file_id":       None,
        "bank_filename":      None,
        "bank_detected":      None,
        "bank_versions":      [],
        "bank_stable":        None,
        "bank_prompt":        "",
        "bank_prompt_meta":   {},
        "bank_qa_log":        [],
        # ── aadhar ──────────────────────────────────────────
        "aadhar_file_id":     None,
        "aadhar_filename":    None,
        "aadhar_detected":    None,
        "aadhar_versions":    [],
        "aadhar_stable":      None,
        "aadhar_prompt":      "",
        "aadhar_prompt_meta": {},
        "aadhar_qa_log":      [],
        # ── shared ──────────────────────────────────────────
        "last_answer":        None,
        "backend_ok":         None,
        "health_ts":          0,
        "audit_log":          [],
        "total_runs":         0,
        "success_runs":       0,
        "fail_runs":          0,
        "total_duration":     0.0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


# ─────────────────────────────────────────────────────────────
# API LAYER
# ─────────────────────────────────────────────────────────────

def api_get(path, timeout=30):
    try:
        r = requests.get(f"{BACKEND_URL}{path}", timeout=timeout)
        if r.status_code == 200:
            return {"ok": True, "data": r.json()}
        return {"ok": False, "error": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def api_post(path, json_data=None, files=None, timeout=120):
    try:
        if files:
            r = requests.post(f"{BACKEND_URL}{path}", files=files, timeout=timeout)
        else:
            r = requests.post(f"{BACKEND_URL}{path}", json=json_data, timeout=timeout)
        if r.status_code == 200:
            return {"ok": True, "data": r.json()}
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        return {"ok": False, "error": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def api_delete(path, timeout=8):
    try:
        r = requests.delete(f"{BACKEND_URL}{path}", timeout=timeout)
        if r.status_code == 200:
            return {"ok": True, "data": r.json()}
        return {"ok": False, "error": r.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_health():
    now = time.time()
    if now - st.session_state.health_ts < 30:
        return st.session_state.backend_ok
    res = api_get("/health", timeout=4)
    st.session_state.backend_ok = res["ok"]
    st.session_state.health_ts  = time.time()
    return res["ok"]


def add_audit(module, action, detail=""):
    st.session_state.audit_log.insert(0, {
        "ts":     datetime.now().strftime("%H:%M:%S"),
        "module": module,
        "action": action,
        "detail": detail,
    })


# ─────────────────────────────────────────────────────────────
# PROMPT VERSION HELPERS
# ─────────────────────────────────────────────────────────────

def fetch_versions(module):
    res = api_get(f"/prompts/{module}/versions")
    if res["ok"]:
        data = res["data"]
        # Backend returns a plain list
        return data if isinstance(data, list) else data.get("versions", [])
    return []


def fetch_stable_version(module):
    res = api_get(f"/prompts/{module}/stable")
    return res["data"] if res["ok"] else None


def fetch_prompt_version(module, version):
    res = api_get(f"/prompts/{module}/{version}")
    return res["data"] if res["ok"] else None


def create_version(module, prompt_text, author="admin"):
    return api_post(f"/prompts/{module}/create", {"prompt_text": prompt_text, "author": author})


def activate_version(module, version):
    return api_post(f"/prompts/{module}/{version}/activate")


def delete_version(module, version):
    return api_delete(f"/prompts/{module}/{version}")


def load_prompt_from_backend(module):
    """Fetch stable version metadata + prompt content and store in session state."""
    stable = fetch_stable_version(module)
    if not stable:
        return False
    ver    = stable.get("version")
    if not ver:
        return False
    detail = fetch_prompt_version(module, ver)
    if not detail:
        return False
    st.session_state[f"{module}_prompt"]      = detail.get("content", "")
    st.session_state[f"{module}_stable"]      = ver
    st.session_state[f"{module}_prompt_meta"] = {
        "version":    ver,
        "created_at": detail.get("created_at", ""),
        "created_by": detail.get("created_by", ""),
    }
    add_audit(module, "Prompt Loaded", f"v{ver}")
    return True


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# FIX: use st.session_state directly for module switching instead
# of calling st.rerun() inside a button callback, which caused
# the sidebar to lose its rendered state on some Streamlit versions.
# ─────────────────────────────────────────────────────────────

def _set_module(module_key: str):
    """Callback for module selector radio — avoids double-rerun issue."""
    st.session_state.active_module = module_key
    st.session_state.last_answer   = None


def render_sidebar():
    with st.sidebar:
        # ── Logo + title ────────────────────────────────────
        st.markdown("""
        <div style="padding:20px 16px 12px;border-bottom:1px solid #1c2433">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
            <div style="width:22px;height:22px;background:#00c2ff;
                        clip-path:polygon(50% 0%,100% 25%,100% 75%,
                                          50% 100%,0% 75%,0% 25%)"></div>
            <span style="font-family:Syne,sans-serif;font-size:14px;
                         font-weight:700;color:#fff;letter-spacing:2px">PROMPT MGT</span>
          </div>
          <div style="font-size:9px;color:#2a3a50;letter-spacing:2px;text-transform:uppercase">
            Document Q&A  ·  Version Control
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Backend health ───────────────────────────────────
        backend_ok  = check_health()
        status_html = badge("● ONLINE", "green") if backend_ok else badge("● OFFLINE", "red")
        st.markdown(
            f'<div style="padding:10px 16px;border-bottom:1px solid #1c2433;'
            f'display:flex;align-items:center;justify-content:space-between">'
            f'<span style="font-size:10px;color:#2a3a50;letter-spacing:1px">BACKEND</span>'
            f'{status_html}</div>',
            unsafe_allow_html=True,
        )

        # ── Module selector (radio avoids sidebar collapse bug) ──
        st.markdown("""
        <div style="padding:16px 16px 4px;font-size:9px;
                    letter-spacing:2px;color:#2a3a50;text-transform:uppercase">
          MODULES
        </div>""", unsafe_allow_html=True)

        # Radio widget maintains state across reruns without collapsing sidebar
        module_options = {"🏦  Bank Statement": "bank", "🪪  Aadhaar Card": "aadhar"}
        current_label  = {v: k for k, v in module_options.items()}.get(
            st.session_state.active_module, "🏦  Bank Statement"
        )

        selected_label = st.radio(
            "module_radio",
            options=list(module_options.keys()),
            index=list(module_options.keys()).index(current_label),
            label_visibility="collapsed",
            key="module_radio_widget",
        )

        # Update active_module if user changed selection
        chosen_module = module_options[selected_label]
        if chosen_module != st.session_state.active_module:
            st.session_state.active_module = chosen_module
            st.session_state.last_answer   = None
            st.rerun()

        st.markdown("---")

        # ── Session stats ─────────────────────────────────────
        total = st.session_state.total_runs
        ok_r  = st.session_state.success_runs
        avg   = round(st.session_state.total_duration / total, 1) if total else 0

        st.markdown(
            f'<div style="padding:0 16px">'
            f'<div style="font-size:9px;letter-spacing:2px;color:#2a3a50;'
            f'text-transform:uppercase;margin-bottom:10px">SESSION STATS</div>'
            f'<div style="display:flex;flex-direction:column;gap:6px">'
            f'<div style="display:flex;justify-content:space-between;font-size:11px">'
            f'<span style="color:#2a3a50">Total runs</span>'
            f'<span style="color:#c9d4e0">{total}</span></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:11px">'
            f'<span style="color:#2a3a50">Success</span>'
            f'<span style="color:#00e5a0">{ok_r}</span></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:11px">'
            f'<span style="color:#2a3a50">Failed</span>'
            f'<span style="color:#ff4d6a">{st.session_state.fail_runs}</span></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:11px">'
            f'<span style="color:#2a3a50">Avg response</span>'
            f'<span style="color:#c9d4e0">{avg}s</span></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown("---")

        if st.button("⟳  Refresh Backend", use_container_width=True, key="refresh_backend"):
            st.session_state.health_ts = 0
            st.rerun()

        # ── Migration helper ──────────────────────────────────
        st.markdown("""
        <div style="padding:8px 16px 0;font-size:9px;letter-spacing:2px;
                    color:#2a3a50;text-transform:uppercase">SETUP</div>
        """, unsafe_allow_html=True)

        if st.button("⚡  Migrate S3 Prompts", use_container_width=True, key="migrate_btn"):
            res = api_get("/migrate", timeout=30)
            if res["ok"]:
                results = res["data"].get("migration_results", [])
                for r in results:
                    st.markdown(
                        f'<div style="font-size:10px;color:#4a6080;padding:2px 16px">'
                        f'{r["bank"]}: {r["status"]}</div>',
                        unsafe_allow_html=True,
                    )
                add_audit("system", "S3 Migration", f"{len(results)} banks processed")
            else:
                st.error(f"Migration failed: {res['error']}")


# ─────────────────────────────────────────────────────────────
# TAB 1 — EXECUTE
# ─────────────────────────────────────────────────────────────

def tab_execute(module):
    is_bank      = (module == "bank")
    accepts      = ["pdf"] if is_bank else ["pdf", "jpg", "jpeg", "png"]
    upload_ep    = "/upload" if is_bank else "/upload/aadhar"
    question_ep  = "/question" if is_bank else "/question/aadhar"
    file_id_key  = f"{module}_file_id"
    filename_key = f"{module}_filename"
    detected_key = f"{module}_detected"
    qa_log_key   = f"{module}_qa_log"

    # ── Upload ──────────────────────────────────────────────
    section_label("01 · UPLOAD DOCUMENT")

    uploaded = st.file_uploader(
        "Drop document",
        type=accepts,
        label_visibility="collapsed",
        key=f"uploader_{module}",
    )

    if uploaded:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(
                f'<div style="display:inline-flex;align-items:center;gap:10px;'
                f'background:#111823;border:1px solid #1c2433;border-radius:6px;'
                f'padding:8px 14px;font-size:12px;color:#4a6080">'
                f'📄 <b style="color:#c9d4e0">{uploaded.name}</b>'
                f'<span style="color:#2a3a50">·</span>'
                f'{round(uploaded.size/1024,1)} KB</div>',
                unsafe_allow_html=True,
            )
        with c2:
            if st.button("⬆  Upload", use_container_width=True, key=f"upload_btn_{module}"):
                steps = [
                    {"label": "Reading file",       "status": "active",  "ts": ""},
                    {"label": "Sending to backend", "status": "pending", "ts": ""},
                    {"label": "Extracting content", "status": "pending", "ts": ""},
                    {"label": "Detecting document", "status": "pending", "ts": ""},
                    {"label": "Ready",              "status": "pending", "ts": ""},
                ]
                ph = st.empty()

                def upd_step(idx, nxt="active"):
                    steps[idx]["status"] = "done"
                    steps[idx]["ts"]     = datetime.now().strftime("%H:%M:%S")
                    if idx + 1 < len(steps):
                        steps[idx + 1]["status"] = nxt
                    with ph.container():
                        step_tracker(steps)

                with ph.container():
                    step_tracker(steps)
                time.sleep(0.2)
                upd_step(0)

                mime  = ("application/pdf" if uploaded.name.lower().endswith(".pdf") else "image/jpeg")
                files = {"file": (uploaded.name, uploaded.getvalue(), mime)}
                upd_step(1)
                res = api_post(upload_ep, files=files)

                if res["ok"]:
                    data = res["data"]
                    upd_step(2); time.sleep(0.15)
                    upd_step(3); time.sleep(0.15)
                    steps[4]["status"] = "done"
                    steps[4]["ts"]     = datetime.now().strftime("%H:%M:%S")
                    with ph.container():
                        step_tracker(steps)

                    st.session_state[file_id_key]  = data.get("file_id")
                    st.session_state[filename_key] = uploaded.name
                    detected = (
                        data.get("bank") or data.get("document_type", module.upper())
                    )
                    st.session_state[detected_key] = detected
                    add_audit(module, "File Uploaded", uploaded.name)
                    st.success(f"✓ Uploaded — detected: **{detected}**")
                else:
                    for i in range(2, 5):
                        steps[i]["status"] = "error"
                    with ph.container():
                        step_tracker(steps)
                    st.error(f"Upload failed: {res['error']}")

    if st.session_state[file_id_key]:
        detected = st.session_state[detected_key] or "—"
        st.markdown(
            f'<div style="display:flex;gap:16px;align-items:center;'
            f'background:#111823;border:1px solid #1c2433;border-radius:8px;'
            f'padding:12px 16px;margin:12px 0">'
            f'{badge("FILE READY","green")}'
            f'<div style="font-size:12px;color:#4a6080">'
            f'{st.session_state[filename_key]}</div>'
            f'<div style="margin-left:auto">{badge(detected,"blue")}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Q&A ─────────────────────────────────────────────────
    section_label("02 · ASK QUESTION")

    if not st.session_state[file_id_key]:
        st.markdown(
            '<div style="background:#111823;border:1px dashed #1c2433;border-radius:8px;'
            'padding:32px;text-align:center;color:#2a3a50;font-size:12px">'
            'Upload a document first to enable Q&A</div>',
            unsafe_allow_html=True,
        )
        return

    presets = (
        [
            "Account holder name?", "Account number?", "IFSC code?", "Available balance?",
            "Total debit amount?",  "Total credit amount?", "Statement period?", "Account type?",
        ]
        if is_bank else
        [
            "Name of cardholder?", "Aadhaar number?", "Date of birth?", "Current age?",
            "Gender?",             "Residential address?", "State?",        "Pincode?",
        ]
    )

    st.markdown(
        '<div style="font-size:9px;color:#2a3a50;letter-spacing:2px;margin-bottom:8px">'
        'QUICK QUESTIONS</div>',
        unsafe_allow_html=True,
    )
    cols    = st.columns(4)
    clicked = None
    for i, q in enumerate(presets):
        with cols[i % 4]:
            if st.button(q, key=f"pre_{module}_{i}", use_container_width=True):
                clicked = q

    question = st.text_input(
        "Question",
        value=clicked or "",
        placeholder="Ask anything about the document…",
        label_visibility="collapsed",
        key=f"q_input_{module}",
    )

    c1, _ = st.columns([1, 5])
    with c1:
        run = st.button("▶  Run", use_container_width=True, key=f"run_{module}")

    if run and question.strip():
        steps = [
            {"label": "Preparing request",         "status": "active",  "ts": ""},
            {"label": "Connecting to backend",      "status": "pending", "ts": ""},
            {"label": "Loading prompt from S3",     "status": "pending", "ts": ""},
            {"label": "Selecting relevant content", "status": "pending", "ts": ""},
            {"label": "Ollama processing",          "status": "pending", "ts": ""},
            {"label": "Response received",          "status": "pending", "ts": ""},
            {"label": "Logging to S3",              "status": "pending", "ts": ""},
        ]
        ph = st.empty()

        def adv(idx):
            steps[idx]["status"] = "done"
            steps[idx]["ts"]     = datetime.now().strftime("%H:%M:%S")
            if idx + 1 < len(steps):
                steps[idx + 1]["status"] = "active"
            with ph.container():
                step_tracker(steps)

        with ph.container():
            step_tracker(steps)
        for i in range(4):
            time.sleep(0.18)
            adv(i)

        t0  = time.time()
        res = api_post(
            question_ep,
            {"file_id": st.session_state[file_id_key], "question": question},
        )
        dur = round(time.time() - t0, 2)

        if res["ok"]:
            adv(4); time.sleep(0.15)
            adv(5); time.sleep(0.15)
            adv(6)

            data  = res["data"]
            entry = {
                "question": question,
                "answer":   data.get("answer", "—"),
                "source":   data.get("bank") or data.get("document_type", module.upper()),
                "duration": dur,
                "ts":       datetime.now().strftime("%H:%M:%S"),
            }
            st.session_state[qa_log_key].insert(0, entry)
            st.session_state.last_answer     = entry
            st.session_state.total_runs     += 1
            st.session_state.success_runs   += 1
            st.session_state.total_duration += dur
            add_audit(module, "Prompt Executed", f"Q: {question[:40]}")
        else:
            for i in range(4, 7):
                steps[i]["status"] = "error"
            with ph.container():
                step_tracker(steps)
            st.session_state.fail_runs  += 1
            st.session_state.total_runs += 1
            st.error(f"Error: {res['error']}")

    elif run:
        st.warning("Enter a question first.")

    if st.session_state.last_answer:
        a = st.session_state.last_answer
        answer_box(a["question"], a["answer"], a["source"], a["duration"], a["ts"])

    # History table
    log = st.session_state[qa_log_key]
    if log:
        section_label("03 · QUESTION HISTORY")
        header = (
            '<div style="display:grid;grid-template-columns:60px 90px 1fr 1fr 50px;'
            'gap:10px;padding:6px 12px;font-size:9px;letter-spacing:1.5px;'
            'color:#2a3a50;text-transform:uppercase;border-bottom:1px solid #1c2433">'
            '<div>TIME</div><div>SOURCE</div><div>QUESTION</div>'
            '<div>ANSWER</div><div>SEC</div></div>'
        )
        rows = ""
        for e in log[:15]:
            rows += (
                f'<div style="display:grid;grid-template-columns:60px 90px 1fr 1fr 50px;'
                f'gap:10px;padding:8px 12px;font-size:11px;'
                f'border-bottom:1px solid #1c2433;align-items:start">'
                f'<div style="color:#2a3a50">{e["ts"]}</div>'
                f'<div style="color:#00c2ff">{e["source"]}</div>'
                f'<div style="color:#4a6080">{e["question"]}</div>'
                f'<div style="color:#c9d4e0;font-weight:500">{e["answer"]}</div>'
                f'<div style="color:#2a3a50">{e["duration"]}</div></div>'
            )
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid #1c2433;'
            f'border-radius:8px;overflow:hidden;margin-top:12px">{header}{rows}</div>',
            unsafe_allow_html=True,
        )
        if st.button("🗑  Clear History", key=f"clr_{module}"):
            st.session_state[qa_log_key] = []
            st.session_state.last_answer = None
            st.rerun()


# ─────────────────────────────────────────────────────────────
# TAB 2 — PROMPT MANAGEMENT
# ─────────────────────────────────────────────────────────────

def tab_prompts(module):
    section_label("ACTIVE PROMPT")

    c_load, c_info = st.columns([1, 3])
    with c_load:
        if st.button("⟳  Load from S3", use_container_width=True, key=f"load_{module}"):
            with st.spinner("Loading…"):
                ok = load_prompt_from_backend(module)
            if ok:
                st.success("✓ Prompt loaded from S3")
            else:
                st.warning(
                    "No stable version found. "
                    "Click '⚡ Migrate S3 Prompts' in the sidebar first, then try again."
                )

    meta = st.session_state[f"{module}_prompt_meta"]
    if meta:
        ver_val     = meta.get("version", "—")
        ver_display = ver_val if str(ver_val).endswith(".txt") else f"v{ver_val}"
        with c_info:
            st.markdown(
                f'<div style="display:flex;gap:10px;align-items:center;'
                f'flex-wrap:wrap;padding-top:6px">'
                f'{badge(ver_display,"blue")}'
                f'{badge("STABLE","green")}'
                f'<span style="font-size:10px;color:#2a3a50">'
                f'by {meta.get("created_by","—")} · '
                f'{str(meta.get("created_at",""))[:19]}</span></div>',
                unsafe_allow_html=True,
            )

    prompt_content = st.session_state[f"{module}_prompt"]
    if prompt_content:
        prompt_box(prompt_content)
    else:
        st.markdown(
            '<div style="background:#0d1117;border:1px dashed #1c2433;border-radius:6px;'
            'padding:24px;text-align:center;color:#2a3a50;font-size:11px">'
            'Click "Load from S3" to fetch the active prompt</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Create new version ───────────────────────────────────
    section_label("CREATE NEW VERSION")

    current_ver = st.session_state.get(f"{module}_stable") or "1.0.0"
    try:
        parts       = current_ver.split(".")
        parts[-1]   = str(int(parts[-1]) + 1)
        next_ver    = ".".join(parts)
    except (ValueError, TypeError):
        next_ver = "1.0.1"

    current_ver_display = current_ver if str(current_ver).endswith(".txt") else f"v{current_ver}"
    next_ver_display    = next_ver    if str(next_ver).endswith(".txt")    else f"v{next_ver}"

    st.markdown(
        f'<div style="display:flex;gap:10px;align-items:center;margin-bottom:10px">'
        f'<span style="font-size:11px;color:#4a6080">Current stable:</span>'
        f'{badge(current_ver_display,"blue")}'
        f'<span style="font-size:11px;color:#2a3a50">→</span>'
        f'<span style="font-size:11px;color:#4a6080">New will be:</span>'
        f'{badge(next_ver_display,"yellow")} {badge("DRAFT","yellow")}</div>',
        unsafe_allow_html=True,
    )

    new_text = st.text_area(
        "New prompt text",
        value=prompt_content,
        height=180,
        label_visibility="collapsed",
        placeholder="Write new prompt here…",
        key=f"new_prompt_{module}",
    )
    author = st.text_input("Author", value="admin", key=f"author_{module}")

    if st.button("＋  Create Draft Version", key=f"create_{module}"):
        if new_text.strip():
            with st.spinner("Saving to S3…"):
                res = create_version(module, new_text, author)
            if res["ok"]:
                new_v = res["data"].get("version", next_ver)
                add_audit(module, "Version Created", f"v{new_v}")
                st.success(f"✓ Draft v{new_v} created — click 'Fetch Versions' to see it.")
            else:
                st.error(f"Failed: {res['error']}")
        else:
            st.warning("Prompt text cannot be empty.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Version History ──────────────────────────────────────
    section_label("VERSION HISTORY")

    if st.button("⟳  Fetch Versions", key=f"fetch_vers_{module}"):
        with st.spinner("Fetching from S3…"):
            vers = fetch_versions(module)
        st.session_state[f"{module}_versions"] = vers
        if vers:
            st.success(f"✓ Found {len(vers)} version(s)")
        else:
            st.warning(
                "No versions found. "
                "Run '⚡ Migrate S3 Prompts' in the sidebar first."
            )

    versions = st.session_state[f"{module}_versions"]
    stable_v = st.session_state[f"{module}_stable"]

    if not versions:
        st.markdown(
            '<div style="color:#2a3a50;font-size:12px;padding:8px 0">'
            'No versions loaded. Click "Fetch Versions".</div>',
            unsafe_allow_html=True,
        )
    else:
        rows_html = ""
        for v in reversed(versions):
            is_stable = (v == stable_v)
            status    = "stable" if is_stable else "draft"
            rows_html += version_row_html(v, status, "", "—", is_stable)
        st.markdown(rows_html, unsafe_allow_html=True)

        section_label("VERSION ACTIONS")

        sel_ver = st.selectbox(
            "Select version",
            options=versions,
            index=len(versions) - 1,
            label_visibility="collapsed",
            key=f"sel_ver_{module}",
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button("👁  View Prompt", use_container_width=True, key=f"view_{module}"):
                with st.spinner("Loading…"):
                    detail = fetch_prompt_version(module, sel_ver)
                if detail:
                    st.markdown(f"**Prompt — v{sel_ver}:**")
                    prompt_box(detail.get("content", ""))
                else:
                    st.error("Could not load version from S3.")

        with c2:
            if st.button("✓  Activate Version", use_container_width=True, key=f"act_{module}"):
                with st.spinner("Activating…"):
                    res = activate_version(module, sel_ver)
                if res["ok"]:
                    st.session_state[f"{module}_stable"] = sel_ver
                    add_audit(module, "Version Activated", f"v{sel_ver}")
                    st.success(f"✓ v{sel_ver} is now the active version.")
                    # Auto-reload the prompt so frontend shows it immediately
                    load_prompt_from_backend(module)
                    st.rerun()
                else:
                    st.error(res["error"])

        with c3:
            if st.button("✗  Delete Version", use_container_width=True, key=f"del_{module}"):
                if sel_ver == stable_v:
                    st.error("Cannot delete the currently active stable version.")
                else:
                    with st.spinner("Deleting from S3…"):
                        res = delete_version(module, sel_ver)
                    if res["ok"]:
                        st.session_state[f"{module}_versions"] = [
                            v for v in versions if v != sel_ver
                        ]
                        add_audit(module, "Version Deleted", f"v{sel_ver}")
                        st.success(f"✓ v{sel_ver} deleted.")
                        st.rerun()
                    else:
                        st.error(res["error"])


# ─────────────────────────────────────────────────────────────
# TAB 3 — AUDIT TRAIL
# ─────────────────────────────────────────────────────────────

def tab_audit():
    section_label("AUDIT TRAIL  —  ALL MODULES")

    audit = st.session_state.audit_log
    if not audit:
        st.markdown(
            '<div style="color:#2a3a50;font-size:12px">No actions recorded yet.</div>',
            unsafe_allow_html=True,
        )
        return

    header = (
        '<div style="display:grid;grid-template-columns:60px 90px 160px 1fr;'
        'gap:10px;padding:6px 12px;font-size:9px;letter-spacing:1.5px;'
        'color:#2a3a50;text-transform:uppercase;border-bottom:1px solid #1c2433">'
        '<div>TIME</div><div>MODULE</div><div>ACTION</div><div>DETAIL</div></div>'
    )
    rows = ""
    for e in audit[:60]:
        mc = "blue" if e["module"] == "bank" else "purple"
        rows += (
            f'<div style="display:grid;grid-template-columns:60px 90px 160px 1fr;'
            f'gap:10px;padding:8px 12px;font-size:11px;'
            f'border-bottom:1px solid #1c2433;align-items:start">'
            f'<div style="color:#2a3a50">{e["ts"]}</div>'
            f'<div>{badge(e["module"].upper(), mc)}</div>'
            f'<div style="color:#c9d4e0">{e["action"]}</div>'
            f'<div style="color:#4a6080">{e["detail"]}</div></div>'
        )
    st.markdown(
        f'<div style="background:#0d1117;border:1px solid #1c2433;'
        f'border-radius:8px;overflow:hidden">{header}{rows}</div>',
        unsafe_allow_html=True,
    )

    if st.button("🗑  Clear Audit Log", key="clr_audit"):
        st.session_state.audit_log = []
        st.rerun()


# ─────────────────────────────────────────────────────────────
# TAB 4 — ANALYTICS
# ─────────────────────────────────────────────────────────────

def tab_analytics():
    section_label("ANALYTICS OVERVIEW")

    total  = st.session_state.total_runs
    ok_r   = st.session_state.success_runs
    fail_r = st.session_state.fail_runs
    avg    = round(st.session_state.total_duration / total, 2) if total else 0

    bank_runs = len(st.session_state.bank_qa_log)
    adh_runs  = len(st.session_state.aadhar_qa_log)
    bank_v    = len(st.session_state.bank_versions)
    adh_v     = len(st.session_state.aadhar_versions)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Executions", total)
    c2.metric("Successful",       ok_r)
    c3.metric("Failed",           fail_r)
    c4.metric("Avg Response (s)", avg)

    st.markdown("<br>", unsafe_allow_html=True)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Bank Queries",    bank_runs)
    c6.metric("Aadhaar Queries", adh_runs)
    c7.metric("Bank Versions",   bank_v)
    c8.metric("Aadhaar Versions", adh_v)

    st.markdown("<br>", unsafe_allow_html=True)
    section_label("MODULE BREAKDOWN")

    success_rate = round((ok_r / total * 100), 1) if total else 0

    st.markdown(
        f'<div style="background:#0d1117;border:1px solid #1c2433;border-radius:8px;padding:20px">'
        f'<div style="display:flex;justify-content:space-between;margin-bottom:8px">'
        f'<span style="font-size:11px;color:#4a6080">Success Rate</span>'
        f'<span style="font-size:11px;color:#00e5a0">{success_rate}%</span></div>'
        f'<div style="background:#111823;border-radius:3px;height:6px;overflow:hidden">'
        f'<div style="background:linear-gradient(90deg,#00e5a0,#00c2ff);'
        f'width:{success_rate}%;height:100%;border-radius:3px"></div></div>'
        f'<div style="display:flex;gap:32px;margin-top:20px">'
        f'<div><div style="font-size:9px;color:#2a3a50;letter-spacing:1px;margin-bottom:4px">'
        f'BANK</div>'
        f'<div style="font-size:22px;font-family:Syne,sans-serif;color:#00c2ff">'
        f'{bank_runs}</div></div>'
        f'<div><div style="font-size:9px;color:#2a3a50;letter-spacing:1px;margin-bottom:4px">'
        f'AADHAAR</div>'
        f'<div style="font-size:22px;font-family:Syne,sans-serif;color:#a78bfa">'
        f'{adh_runs}</div></div>'
        f'<div><div style="font-size:9px;color:#2a3a50;letter-spacing:1px;margin-bottom:4px">'
        f'ERRORS</div>'
        f'<div style="font-size:22px;font-family:Syne,sans-serif;color:#ff4d6a">'
        f'{fail_r}</div></div>'
        f'<div><div style="font-size:9px;color:#2a3a50;letter-spacing:1px;margin-bottom:4px">'
        f'AVG (s)</div>'
        f'<div style="font-size:22px;font-family:Syne,sans-serif;color:#ffb800">'
        f'{avg}</div></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    render_sidebar()
    topbar()

    module = st.session_state.active_module
    icons  = {"bank": "🏦", "aadhar": "🪪"}
    labels = {"bank": "Bank Statement", "aadhar": "Aadhaar Card"}

    st.markdown(
        f'<div style="padding:20px 32px 0">'
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px">'
        f'<span style="font-size:22px">{icons[module]}</span>'
        f'<span style="font-family:Syne,sans-serif;font-size:22px;font-weight:700;color:#fff">'
        f'{labels[module]}</span>'
        f'<span style="margin-left:8px">{badge(module.upper(),"blue")}</span></div>'
        f'<div style="font-size:11px;color:#2a3a50;padding-left:36px;margin-bottom:8px">'
        f'Prompt Management · Document Q&A · Version Control · Analytics</div></div>',
        unsafe_allow_html=True,
    )

    tabs = st.tabs([
        "▶  Execute",
        "⚙  Prompts",
        "◎  Audit",
        "▪  Analytics",
    ])

    with tabs[0]: tab_execute(module)
    with tabs[1]: tab_prompts(module)
    with tabs[2]: tab_audit()
    with tabs[3]: tab_analytics()


if __name__ == "__main__":
    main()
