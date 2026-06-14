import streamlit as st
import json
import os
from backend.agents import AgentOrchestrator
from backend.tools import execute_remediation_command, create_servicenow_incident

# Page configuration
st.set_page_config(
    page_title="OpsPilot AI - Autonomous Operations Intelligence Platform",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling (Dark Mode / NOC Dashboard theme)
st.markdown("""
<style>
    /* Main container background */
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    
    /* Header styling */
    .main-title {
        color: #58a6ff;
        font-family: 'Outfit', sans-serif;
        font-weight: 800;
        font-size: 2.5rem;
        margin-bottom: 0px;
    }
    
    .subtitle {
        color: #8b949e;
        font-size: 1.1rem;
        margin-bottom: 25px;
    }
    
    /* Card panel styling */
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
    }
    
    .agent-card {
        background-color: #1f2937;
        border-left: 5px solid #58a6ff;
        border-radius: 4px;
        padding: 12px;
        margin-bottom: 12px;
    }

    .warning-card {
        background-color: #2d1d1d;
        border-left: 5px solid #f85149;
        border-radius: 4px;
        padding: 12px;
        margin-bottom: 12px;
    }
    
    .timeline-step {
        border-left: 2px solid #58a6ff;
        padding-left: 15px;
        margin-bottom: 12px;
        position: relative;
    }
    
    .timeline-time {
        color: #58a6ff;
        font-weight: bold;
        font-size: 0.85rem;
    }
    
    .timeline-desc {
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to load scenarios
def get_scenario_files():
    data_dir = "data/scenarios"
    scenarios = {}
    if os.path.exists(data_dir):
        for f in os.listdir(data_dir):
            if f.endswith(".json"):
                path = os.path.join(data_dir, f)
                with open(path, "r") as file:
                    data = json.load(file)
                    scenarios[data["name"]] = data
    return scenarios

scenarios = get_scenario_files()

# Session State Initialization
if "selected_scenario" not in st.session_state:
    st.session_state.selected_scenario = list(scenarios.keys())[0] if scenarios else ""
if "pipeline_results" not in st.session_state:
    st.session_state.pipeline_results = None
if "remediation_executed" not in st.session_state:
    st.session_state.remediation_executed = False
if "remediation_output" not in st.session_state:
    st.session_state.remediation_output = None
if "ticket_id" not in st.session_state:
    st.session_state.ticket_id = None

# Sidebar controls
with st.sidebar:
    st.image("https://img.icons8.com/nolan/96/airplane-take-off.png", width=60)
    st.markdown("### **OpsPilot AI**")
    st.markdown("`v1.0.0 (Hackathon Edition)`")
    st.write("---")
    
    st.markdown("#### **1. Select Incident Scenario**")
    scenario_selection = st.selectbox(
        "Choose a preloaded incident:",
        list(scenarios.keys()),
        index=0
    )
    
    # Check if scenario changed to reset pipeline state
    if scenario_selection != st.session_state.selected_scenario:
        st.session_state.selected_scenario = scenario_selection
        st.session_state.pipeline_results = None
        st.session_state.remediation_executed = False
        st.session_state.remediation_output = None
        st.session_state.ticket_id = None
        
    st.write("---")
    
    st.markdown("#### **2. LLM Configuration**")
    use_real_llm = st.checkbox("Enable Live LLM Pipeline", value=False, help="Connect to a live OpenAI/Ollama endpoint. If unchecked, runs in high-fidelity fail-safe mode.")
    model_name = st.text_input("Model Name", value="qwen2.5-7b-instruct", disabled=not use_real_llm)
    
    st.write("---")
    
    st.markdown("#### **3. Manual Upload (Optional)**")
    uploaded_file = st.file_uploader("Upload custom incident JSON", type=["json"])
    if uploaded_file is not None:
        try:
            custom_data = json.load(uploaded_file)
            custom_name = custom_data.get("name", "Custom Incident")
            scenarios[custom_name] = custom_data
            st.session_state.selected_scenario = custom_name
            st.success(f"Loaded: {custom_name}")
        except Exception as e:
            st.error(f"Invalid format: {e}")

# Retrieve selected scenario data
current_scenario = scenarios.get(st.session_state.selected_scenario, {})

# Title Block
st.markdown("<div class='main-title'>OpsPilot AI</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Autonomous Operations Intelligence Platform — Incident Diagnosis, RCA, & Resolution</div>", unsafe_allow_html=True)

# Main Dashboard Layout
col1, col2 = st.columns([2, 3])

with col1:
    st.markdown("### 📊 Live Telemetry & Alarm Stream")
    
    # Metric cards display
    if current_scenario:
        metrics = current_scenario.get("metrics", {})
        m_col1, m_col2 = st.columns(2)
        m_col3, m_col4 = st.columns(2)
        
        with m_col1:
            st.metric("CPU Load", metrics.get("CPU Usage", "N/A"), delta="Normal" if "normal" in metrics.get("CPU Usage", "").lower() or "22%" in metrics.get("CPU Usage", "") or "42%" in metrics.get("CPU Usage", "") else "Elevated", delta_color="inverse")
        with m_col2:
            st.metric("Memory Usage", metrics.get("Memory Usage", "N/A"), delta="Critical" if "99%" in metrics.get("Memory Usage", "") else "Normal", delta_color="inverse")
        with m_col3:
            st.metric("Active DB Conns", metrics.get("Active DB Connections", "N/A"))
        with m_col4:
            st.metric("Net Latency", metrics.get("Network Latency", "N/A"), delta="SLA Breach" if "severe" in metrics.get("Network Latency", "").lower() or "420ms" in metrics.get("Network Latency", "") else "Normal", delta_color="inverse")

    st.write("")
    
    # Alerts and logs display
    with st.container(border=True):
        st.markdown("🔔 **Active Alerts**")
        for alert in current_scenario.get("alerts", []):
            st.info(alert)
            
        st.markdown("📄 **System Logs**")
        log_text = "\n".join(current_scenario.get("logs", []))
        st.code(log_text, language="log")

    # Run Analysis Button
    st.write("")
    if st.button("🚀 Ingest & Start Multi-Agent Diagnostic Swarm", use_container_width=True, type="primary"):
        with st.spinner("Initializing sequential agent context pipeline..."):
            orchestrator = AgentOrchestrator(use_real_llm=use_real_llm, model_name=model_name)
            results = orchestrator.run_pipeline(st.session_state.selected_scenario, current_scenario)
            st.session_state.pipeline_results = results
            st.session_state.remediation_executed = False
            st.session_state.remediation_output = None
            st.session_state.ticket_id = None

with col2:
    # Always display Architecture Overview
    with st.expander("🗺️ How OpsPilot AI Works (Autonomous Reasoning Loop)", expanded=False):
        st.markdown("""
        **OpsPilot AI uses a sequential multi-agent loop with shared consensus memory:**
        ```
        [Raw Observability Inputs: Logs, Alerts, Metrics]
                             │
                             ▼
        1. Observability Agent (Gathers symptoms & evidence)
                             │
                             ▼
        [Agent Memory Panel: Semantic matches over Vector Store]
                             │
                             ▼
        2. RCA Agent (Consensus negotiation & root cause isolation)
                             │
                             ▼
        3. Blast Radius Agent (Downstream service mapping & user impact)
                             │
                             ▼
        4. Remediation Agent (Step-by-step resolution plan & do-nothing forecast)
                             │
                             ▼
        5. Operations Agent (Autonomous script execution & Postmortem documentation)
        ```
        """)

    if st.session_state.pipeline_results is None:
        st.info("Click **Ingest & Start Multi-Agent Diagnostic Swarm** on the left to initiate the analysis pipeline.")
    else:
        results = st.session_state.pipeline_results
        
        st.markdown("### 🤖 Collaborative Agent Swarm Analysis")
        
        # 1. Observability Agent View with Thinking Trail
        with st.expander("👁️ 1. Observability Agent Report", expanded=True):
            st.markdown(f"**🔍 Evidence Found:**\n{results['observability'].get('evidence', results['observability'].get('summary'))}")
            st.write("")
            st.markdown(f"**🧠 Reasoning:**\n*{results['observability'].get('reasoning', 'Analyzing metrics anomalies and error threshold alerts.')}*")
            st.write("")
            st.markdown(f"**🎯 Conclusion:**\n`{results['observability'].get('conclusion', results['observability'].get('summary'))}`")
            st.write("")
            st.markdown(f"**Anomaly Confidence Score:** `{results['observability']['confidence']}%`")

        # 2. Agent Memory Panel
        st.markdown("🧠 **Agent Memory (Vector DB Matches)**")
        history = current_scenario.get("historical_incidents", [])
        if history:
            for item in history:
                st.markdown(f"""
                <div style='background-color:#1b2838; border-left:3px solid #ff9900; padding:10px; border-radius:4px;'>
                    <strong>Similar Incident Matched:</strong> {item['id']} - {item['name']} ({item['date']})<br/>
                    <strong>Resolution:</strong> {item['resolution']}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.write("No matching historical records found.")
        st.write("")

        # 3. RCA Agent View with Thinking Trail & Consensus
        with st.expander("🔍 2. RCA Agent & Consensus Negotiation", expanded=True):
            st.markdown(f"**🤝 Diagnostic Negotiation Log:**\n*{results['rca']['negotiation']}*")
            st.write("---")
            st.markdown(f"**🔍 Evidence Correlated:**\n{results['rca'].get('evidence', 'Analyzing correlation between hardware starvation and application-side limits.')}")
            st.write("")
            st.markdown(f"**🧠 Reasoning:**\n*{results['rca'].get('reasoning', 'Isolating root cause by ruling out non-starved hardware interfaces.')}*")
            st.write("")
            st.markdown(f"**🎯 Conclusion:**\n`{results['rca'].get('conclusion', results['rca']['consensus_rca'])}`")
            st.write("---")
            
            # Confidence Consensus metrics
            c_col1, c_col2, c_col3 = st.columns(3)
            c_col1.metric("Observability Conf.", f"{results['rca']['obs_confidence']}%")
            c_col2.metric("RCA Agent Conf.", f"{results['rca']['rca_confidence']}%")
            c_col3.metric("Consensus Confidence", f"{results['rca']['consensus_confidence']}%")
            
            st.markdown(f"**Negotiated Consensus Root Cause:**\n`{results['rca']['consensus_rca']}`")

        # 4. Blast Radius Agent View
        with st.expander("💥 3. Blast Radius & Business Impact Analyzer", expanded=True):
            st.markdown(f"**Estimated User Impact:** `{results['blast_radius']['user_impact']}`")
            st.markdown(f"**Business Severity:** `{results['blast_radius']['severity']}`")
            
            st.markdown("**Downstream Services Affected:**")
            cols = st.columns(len(results['blast_radius']['affected_services']))
            for idx, service in enumerate(results['blast_radius']['affected_services']):
                cols[idx].markdown(f"⚡ `{service}`")

        # 5. Remediation Agent View
        with st.expander("🛠️ 4. Remediation Recommender & Predictive Impact", expanded=True):
            st.markdown("**Proposed Action Plan:**")
            for step in results['remediation']['steps']:
                st.markdown(step)
                
            st.write("---")
            st.markdown("🔮 **Do-Nothing Predictive Operations Forecast:**")
            st.markdown(f"""
            <div class='warning-card'>
                <strong>🔴 30 Minutes:</strong> {results['remediation']['do_nothing_30m']}
            </div>
            <div class='warning-card'>
                <strong>🔴 60 Minutes:</strong> {results['remediation']['do_nothing_60m']}
            </div>
            """, unsafe_allow_html=True)

        # 6. Action & Resolution (Operations Agent)
        st.markdown("### ⚡ Autonomous Action & Resolution Center")
        
        with st.container(border=True):
            st.markdown(f"**Recommended Repair Script:**")
            st.code(results['operations']['command'], language="bash")
            
            if not st.session_state.remediation_executed:
                if st.button("🔧 Approve & Execute Autonomous Repair", use_container_width=True, type="primary"):
                    with st.spinner("Executing simulated container deployment commands..."):
                        cmd_res = execute_remediation_command(results['operations']['command'])
                        st.session_state.remediation_output = cmd_res["output"]
                        st.session_state.remediation_executed = True
                        st.session_state.ticket_id = create_servicenow_incident({
                            "root_cause": results['rca']['consensus_rca'],
                            "remediation": results['operations']['command']
                        })
                        st.rerun()
            else:
                st.success("🎉 Remediation Hot-Patch Executed Successfully!")
                
                # Real-time Infrastructure Recovery Card (Priority 3)
                st.markdown("### 🟢 Real-time Infrastructure Recovery Metrics")
                rec_cols = st.columns(3)
                if st.session_state.selected_scenario == "Critical Payment Outage":
                    rec_cols[0].metric("System Status", "RECOVERED", delta="Healthy", delta_color="normal")
                    rec_cols[1].metric("Network Latency", "12ms", delta="-3438ms (Healthy)", delta_color="inverse")
                    rec_cols[2].metric("DB Connections", "35/100", delta="-65 connections", delta_color="inverse")
                elif st.session_state.selected_scenario == "Order Processing Collapse":
                    rec_cols[0].metric("System Status", "RECOVERED", delta="Healthy", delta_color="normal")
                    rec_cols[1].metric("Memory Usage", "45% Heap", delta="-54% Memory", delta_color="inverse")
                    rec_cols[2].metric("CPU Load", "12%", delta="-73% (GC OK)", delta_color="inverse")
                else:  # Telecom Network Failure
                    rec_cols[0].metric("System Status", "RECOVERED", delta="Healthy", delta_color="normal")
                    rec_cols[1].metric("Network Latency", "12ms", delta="-408ms (SLA OK)", delta_color="inverse")
                    rec_cols[2].metric("Packet Loss", "0.1%", delta="-18.4% loss", delta_color="inverse")
                
                st.write("")
                
                st.code(st.session_state.remediation_output, language="log")
                st.info(f"💾 ServiceNow ITSM Incident log updated. Ticket ID: **{st.session_state.ticket_id}**")
                
                # Interactive timeline display
                st.markdown("### ⏳ Resolution Lifecycle Timeline")
                timeline_data = [
                    ("12:03 PM", "Alert triggered in target infrastructure"),
                    ("12:04 PM", "Observability Agent analyzed errors and flags anomalies"),
                    ("12:05 PM", "RCA Agent established consensus and rules out hardware starvation"),
                    ("12:06 PM", "Blast Radius Agent identified affected services and revenue risk"),
                    ("12:07 PM", "Remediation Agent designed the scale-up patch and rollback commands"),
                    ("12:08 PM", f"Operations Agent successfully executed Hot-Patch script: {results['operations']['command']}"),
                    ("12:09 PM", "Automated system validation checks passed. Operations back to Healthy (VRAM/RAM stabilized).")
                ]
                
                for t, desc in timeline_data:
                    st.markdown(f"""
                    <div class='timeline-step'>
                        <div class='timeline-time'>{t}</div>
                        <div class='timeline-desc'>{desc}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Postmortem and Download
                st.write("")
                st.markdown("### 📄 Generated Incident Postmortem")
                st.markdown(results['operations']['postmortem'])
                
                st.download_button(
                    label="📥 Download Markdown Postmortem Report",
                    data=results['operations']['postmortem'],
                    file_name=f"postmortem_{st.session_state.ticket_id}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
