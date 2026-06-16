import streamlit as st
import requests
import json
import os

# ─────────────────────────────────────────────────────────────
# CONFIGURATION & CONSTANTS
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Netra - Automated Document Processor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.markdown("""
    <style>
    .main .block-container { padding-top: 1.5rem; }
    .stAlert p { margin-bottom: 0; }
    footer {visibility: hidden;}
    .answer-box {
        background-color: #f0f7f4;
        border-left: 5px solid #2e7d32;
        padding: 1.5rem;
        border-radius: 4px;
        margin-bottom: 1.5rem;
    }
    /* Dark mode support for answer box */
    @media (prefers-color-scheme: dark) {
        .answer-box {
            background-color: #1e2b24;
            border-left: 5px solid #4caf50;
        }
    }
    </style>
""", unsafe_allow_html=True)

if "doc_processed" not in st.session_state:
    st.session_state["doc_processed"] = False
if "detected_module" not in st.session_state:
    st.session_state["detected_module"] = None
if "file_id" not in st.session_state:
    st.session_state["file_id"] = None
if "active_prompt" not in st.session_state:
    st.session_state["active_prompt"] = None

# ─────────────────────────────────────────────────────────────
# SIDEBAR SYSTEM STATUS
# ─────────────────────────────────────────────────────────────
st.sidebar.title("🤖 Netra Engine")
st.sidebar.markdown("---")

try:
    health_resp = requests.get(f"{BACKEND_URL}/health", timeout=2).json()
    if health_resp.get("status") == "running":
        st.sidebar.success("System Status: Operational")
except Exception:
    st.sidebar.error("System Status: Offline")

if st.session_state["doc_processed"]:
    st.sidebar.markdown("### Active Context")
    st.sidebar.info(f"**Target Module:**\n`{st.session_state['detected_module']}`")
    if st.sidebar.button("Clear Cache & Restart", type="secondary"):
        st.session_state["doc_processed"] = False
        st.session_state["detected_module"] = None
        st.session_state["file_id"] = None
        st.session_state["active_prompt"] = None
        st.rerun()

# ─────────────────────────────────────────────────────────────
# MAIN WORKFLOW INTERFACE
# ─────────────────────────────────────────────────────────────
st.title("Netra")
st.markdown("Upload any supported file to auto-detect its profile type, provision S3 configurations, and run structural query pipelines.")

# ==========================================
# STEP 1: UPLOAD & AUTO-DETECTION
# ==========================================
st.subheader("Document Detection ")

uploaded_file = st.file_uploader("Drop document format (PDF, PNG, JPG, JPEG) here", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file is not None and not st.session_state["doc_processed"]:
    if st.button("Analyze & Match Document", type="primary"):
        with st.spinner("Classifying document..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                response = requests.post(f"{BACKEND_URL}/upload", files=files)
                
                if response.status_code == 200:
                    res_data = response.json()
                    
                    doc_type = res_data.get("document_type")
                    bank_name = res_data.get("bank_name")
                    computed_module = f"bank/{bank_name}" if doc_type == "bank" else "aadhaar"
                    
                    st.session_state["doc_processed"] = True
                    st.session_state["detected_module"] = computed_module
                    st.session_state["file_id"] = res_data.get("file_id")
                    st.session_state["active_prompt"] = res_data.get("active_prompt")
                    
                    st.success(f"Analysis Complete! Detected dcument type: `{computed_module}`")
                    st.rerun()
                else:
                    st.error(f"Upload processing failed: {response.text}")
            except Exception as e:
                st.error(f"Error establishing communication with backend service: {e}")

# ==========================================
# STEP 2: STABLE S3 BUCKET RESOLUTION & VERSION CONTROL
# ==========================================
if st.session_state["doc_processed"]:
    st.markdown("---")
    active_mod = st.session_state["detected_module"]
    st.subheader(f"Dynamic Prompt Versioning (`prompts/{active_mod}/`)")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        
        try:
            stable_resp = requests.get(f"{BACKEND_URL}/prompts/{active_mod}/stable")
            if stable_resp.status_code == 200:
                stable_data = stable_resp.json()
                st.success(f" **Active Stable Version:** v{stable_data.get('version')}")
                with st.expander("Show Deployed Content"):
                    st.code(stable_data.get("prompt"), language="text")
            else:
                st.warning(" No stable tracking flag initialized under this workspace route yet.")
        except Exception as e:
            st.error(f"Failed to fetch current S3 state metadata: {e}")
            
        st.markdown("---")
      
        st.markdown("#### Custom Version Selection")
        try:
            v_resp = requests.get(f"{BACKEND_URL}/prompts/{active_mod}/versions")
            if v_resp.status_code == 200:
                versions = v_resp.json().get("versions", [])
                if versions:
                    selected_ver = st.selectbox("Select Target Version:", options=versions)
                    
                    # Split horizontally into two action columns
                    act_col, del_col = st.columns(2)
                    
                    # Column A: Activate Version
                    if act_col.button("Force Activate", use_container_width=True, type="primary"):
                        act_resp = requests.post(f"{BACKEND_URL}/prompts/{active_mod}/{selected_ver}/activate")
                        if act_resp.status_code == 200:
                            st.toast(f"Promoted and activated version v{selected_ver} successfully!")
                            st.rerun()
                        else:
                            st.error(act_resp.text)
                            
                    # Column B: Delete Version
                    if del_col.button("Delete Version", use_container_width=True, type="secondary"):
                        del_resp = requests.delete(f"{BACKEND_URL}/prompts/{active_mod}/{selected_ver}")
                        if del_resp.status_code == 200:
                            st.toast(f"Version v{selected_ver} successfully deleted from S3.")
                            st.rerun()
                        else:
                            err_detail = del_resp.json().get("detail", del_resp.text)
                            st.error(f"Deletion Blocked: {err_detail}")
                else:
                    st.info("No version found.")
        except Exception as e:
            st.sidebar.error(f"Failed listing: {e}")

    with col2:
        st.markdown("#### Create New Prompt")
        
        with st.form("append_prompt_form", clear_on_submit=True):
            author_id = st.text_input("Committer ID", value="admin_dashboard")
            prompt_body = st.text_area("Enter your prompt here", height=180, 
                                       placeholder="Add instructions, structuring parameters or execution rules...")
            
            submit_prompt = st.form_submit_button("Create new version", type="primary")
            
            if submit_prompt:
                if not prompt_body.strip():
                    st.error("Text context cannot be empty.")
                else:
                    try:
                        payload = {"prompt_text": prompt_body, "author": author_id}
                        create_resp = requests.post(f"{BACKEND_URL}/prompts/{active_mod}/create", json=payload)
                        if create_resp.status_code == 200:
                            res_json = create_resp.json()
                            st.toast(f"Created version: v{res_json.get('version')}")
                            st.rerun()
                        else:
                            st.error(f"Error code {create_resp.status_code}: {create_resp.text}")
                    except Exception as e:
                        st.error(f"Failed processing deployment updates: {e}")
# ==========================================
# STEP 3: CONTEXTUAL RESPONSIVE INQUIRY (Q&A)
# ==========================================
if st.session_state["doc_processed"]:
    st.markdown("---")
    st.subheader("Ask question here")
    
    user_query = st.text_area("", 
                              placeholder="e.g., What are the names mentioned? What transaction values match the records?")
    
    if st.button("Submit Question", type="secondary"):
        if not user_query.strip():
            st.warning("Please type a valid structured inquiry string.")
        else:
            with st.spinner("Loading..."):
                try:
                    payload = {
                        "file_id": st.session_state["file_id"],
                        "question": user_query
                    }
                    q_resp = requests.post(f"{BACKEND_URL}/question", json=payload)
                    
                    if q_resp.status_code == 200:
                        raw_content = q_resp.text
                        
                        # Try parsing as JSON to cleanly extract a text-only target if present
                        final_answer = raw_content
                        is_json = False
                        try:
                            parsed_json = json.loads(raw_content)
                            is_json = True
                            # Look for typical fields your processing pipeline might return
                            final_answer = (
                                parsed_json.get("answer") or 
                                parsed_json.get("result") or 
                                parsed_json.get("extracted_text") or 
                                str(parsed_json)
                            )
                        except json.JSONDecodeError:
                            pass
                        
                        #  1. CLEAN FINAL ANSWER BOX
                        st.markdown("### Final Reply")
                        st.markdown(
                            f'<div class="answer-box"><strong>Result:</strong> {final_answer}</div>', 
                            unsafe_allow_html=True
                        )
                        
                        #  2. FULL JSON PAYLOAD INSPECTOR
                        st.markdown("### JSON Payload")
                        if is_json:
                            st.json(parsed_json)
                        else:
                            st.info(raw_content)
                            
                    else:
                        st.error(f"Query Execution Error: {q_resp.text}")
                except Exception as e:
                    st.error(f"Network processing exception encountered: {e}")