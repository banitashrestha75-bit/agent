import streamlit as st
import os
import base64
from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox
from groq import Groq

# Import backend modules
import agent
import pdf_generator

# Page Configuration
st.set_page_config(
    page_title="E2B Document Sandbox Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()

# Design Custom Styling (Slate/Teal Theme)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Header Gradient */
    .header-container {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 2rem;
        border-left: 6px solid #0F766E;
    }
    .header-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.025em;
    }
    .header-subtitle {
        font-size: 1rem;
        color: #94A3B8;
        margin-top: 0.5rem;
        margin-bottom: 0;
        font-weight: 400;
    }
    
    /* Custom Card Style */
    .custom-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }
    
    /* Pill statuses */
    .status-pill {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 0.5rem;
    }
    .status-active {
        background-color: #D1FAE5;
        color: #065F46;
        border: 1px solid #A7F3D0;
    }
    .status-inactive {
        background-color: #FEE2E2;
        color: #991B1B;
        border: 1px solid #FCA5A5;
    }
</style>
""", unsafe_allow_html=True)

# Session State Initialization
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None
if "file_profile" not in st.session_state:
    st.session_state.file_profile = None
if "file_size_str" not in st.session_state:
    st.session_state.file_size_str = None
if "sandbox" not in st.session_state:
    st.session_state.sandbox = None

# Sidebar Config
st.sidebar.markdown("### 📊 E2B Sandbox Analyst")
st.sidebar.markdown("Execute advanced queries & charts in a secure cloud sandbox.")

# Check for API Keys in Env
env_groq_key = os.getenv("GROQ_API_KEY", "")
env_e2b_key = os.getenv("E2B_API_KEY", "")

# Fallback credentials in Sidebar
st.sidebar.subheader("Credentials")
groq_key_input = st.sidebar.text_input(
    "Groq API Key", 
    value=env_groq_key, 
    type="password",
    help="Get it from https://console.groq.com"
)
e2b_key_input = st.sidebar.text_input(
    "E2B API Key", 
    value=env_e2b_key, 
    type="password",
    help="Get it from https://e2b.dev"
)

# Select Model
model_choice = st.sidebar.selectbox(
    "Select LLM Model",
    options=[
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant"
    ],
    index=0
)

# API Status Indicators
groq_active = bool(groq_key_input)
e2b_active = bool(e2b_key_input)

status_cols = st.sidebar.columns(2)
with status_cols[0]:
    if groq_active:
        st.markdown('<span class="status-pill status-active">Groq Active</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-pill status-inactive">Groq Missing</span>', unsafe_allow_html=True)
with status_cols[1]:
    if e2b_active:
        st.markdown('<span class="status-pill status-active">E2B Active</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-pill status-inactive">E2B Missing</span>', unsafe_allow_html=True)

# Main Application Layout
st.markdown("""
<div class="header-container">
    <div class="header-title">E2B Coding Agent Sandbox</div>
    <div class="header-subtitle">Upload CSV, JSON, PDF, TXT, or MD documents. Ask questions, run sandbox Python analysis, and compile PDF reports with charts.</div>
</div>
""", unsafe_allow_html=True)

# Ensure credentials are present
if not groq_active or not e2b_active:
    st.info("💡 **Please provide your Groq API Key and E2B API Key in the sidebar or in a local `.env` file to start.**")
    st.stop()

# Initialize clients
groq_client = Groq(api_key=groq_key_input)

# Function to get E2B Sandbox
def get_sandbox_instance():
    if st.session_state.sandbox is None:
        try:
            os.environ["E2B_API_KEY"] = e2b_key_input
            st.session_state.sandbox = Sandbox.create()
        except Exception as e:
            st.error(f"Failed to create E2B Sandbox: {e}")
            st.stop()
    return st.session_state.sandbox

# Clean/Reset Sandbox
if st.sidebar.button("Reset Sandbox Session", use_container_width=True):
    if st.session_state.sandbox:
        try:
            st.session_state.sandbox.close()
        except:
            pass
        st.session_state.sandbox = None
    st.session_state.uploaded_filename = None
    st.session_state.file_profile = None
    st.session_state.file_size_str = None
    st.session_state.chat_history = []
    st.success("Sandbox session reset successfully!")
    st.rerun()

# Document Upload Section
uploaded_file = st.file_uploader(
    "Upload Document (PDF, MD, TXT, JSON, CSV)",
    type=["pdf", "md", "txt", "json", "csv"]
)

if uploaded_file is not None:
    filename = uploaded_file.name
    # Trigger upload to E2B if the filename is new or sandbox was reset
    if st.session_state.uploaded_filename != filename:
        sbx = get_sandbox_instance()
        with st.status(f"Uploading and analyzing {filename}...", expanded=True) as status:
            st.write("Writing file to remote sandbox...")
            file_bytes = uploaded_file.getvalue()
            sbx.files.write(filename, file_bytes)
            
            st.write("Running sandbox file profiling...")
            profile = agent.profile_file(sbx, filename)
            
            st.session_state.uploaded_filename = filename
            st.session_state.file_profile = profile
            st.session_state.file_size_str = f"{len(file_bytes) / 1024:.1f} KB"
            status.update(label="Document profiling complete!", state="complete")
            st.rerun()

# Layout splits: File Preview (if uploaded) and Query Chat
if st.session_state.uploaded_filename:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("📄 Document Profile")
        st.markdown(f"**Filename**: `{st.session_state.uploaded_filename}`")
        st.markdown(f"**Size**: `{st.session_state.file_size_str}`")
        
        with st.expander("Metadata & Sandbox Inspection", expanded=True):
            st.code(st.session_state.file_profile, language="text")
            
    with col2:
        st.subheader("💬 Ask Questions & Run Analysis")
        
        # Query text box
        query_input = st.text_input(
            "What would you like to analyze or visualize?",
            placeholder="e.g. Plot sales growth by category, or Summarize page 1."
        )
        
        if st.button("Run Query Agent", type="primary", use_container_width=True) and query_input:
            sbx = get_sandbox_instance()
            
            # Step 1: Formulate execution plan and python code
            with st.status("Agent planning & writing analysis code...", expanded=True) as status:
                st.write("Prompting Groq LLM...")
                plan, code = agent.generate_analysis_code(
                    groq_client,
                    model_choice,
                    query_input,
                    st.session_state.uploaded_filename,
                    st.session_state.file_profile,
                    st.session_state.chat_history
                )
                
                st.write("Plan formulated:")
                st.info(plan)
                
                if not code:
                    status.update(label="Planning complete, no sandbox code required.", state="complete")
                    stdout, stderr, charts = "", "", []
                else:
                    st.write("Executing Python code inside the cloud sandbox...")
                    stdout, stderr, charts = agent.execute_sandbox_code(sbx, code)
                    status.update(label="Sandbox execution complete!", state="complete")
            
            # Show logs / errors if any
            if code:
                with st.expander("Sandbox Logs & Code", expanded=False):
                    st.markdown("**Executed Code:**")
                    st.code(code, language="python")
                    if stdout:
                        st.markdown("**Console Output:**")
                        st.code(stdout, language="text")
                    if stderr:
                        st.markdown("**Execution Errors:**")
                        st.error(stderr)
            
            # Render charts in Streamlit
            if charts:
                st.markdown("#### Generated Charts")
                for c_b64 in charts:
                    st.image(base64.b64decode(c_b64), caption="Generated Visualization", use_column_width=True)
            
            # Step 2: Final human-readable response summarizing findings
            with st.spinner("Compiling final analysis results..."):
                full_console_output = stdout or ""
                if stderr:
                    full_console_output += f"\n[Errors]:\n{stderr}"
                    
                final_summary = agent.generate_final_summary(
                    groq_client,
                    model_choice,
                    query_input,
                    st.session_state.uploaded_filename,
                    st.session_state.file_profile,
                    code,
                    full_console_output,
                    st.session_state.chat_history
                )
                
            # Render Final Response
            st.markdown("### Analysis Results")
            st.markdown(final_summary)
            
            # PDF Generation
            with st.spinner("Preparing PDF report download..."):
                pdf_bytes = pdf_generator.generate_pdf_report(
                    query=query_input,
                    text_response=final_summary,
                    code_executed=code,
                    console_output=full_console_output,
                    base64_charts=charts,
                    doc_name=st.session_state.uploaded_filename,
                    doc_size_str=st.session_state.file_size_str
                )
                
            st.download_button(
                label="📥 Download Analysis PDF Report",
                data=pdf_bytes,
                file_name=f"analysis_report_{st.session_state.uploaded_filename.split('.')[0]}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
            # Save query & answer to session history
            st.session_state.chat_history.append({"role": "user", "content": query_input})
            st.session_state.chat_history.append({"role": "assistant", "content": final_summary})
            
        # Display chat history below if there is any
        if st.session_state.chat_history:
            st.markdown("---")
            st.subheader("History")
            for msg in reversed(st.session_state.chat_history[:-2]):
                role_label = "👤 You" if msg["role"] == "user" else "🤖 Agent"
                st.markdown(f"**{role_label}**: {msg['content']}")
else:
    st.info("👈 Upload a document in the upload panel to get started.")
