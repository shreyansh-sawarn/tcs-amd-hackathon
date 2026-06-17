# OpsPilot AI — Autonomous NOC Intelligence Platform

OpsPilot AI is an autonomous, sequential multi-agent swarm platform developed for the **TCS & AMD AI Hackathon (Track 1 — Agents)**. It is designed to run locally on enterprise infrastructure, utilizing **AMD Instinct™ MI300X** hardware acceleration via **AMD ROCm** and **vLLM** to diagnose system outages, predict business impact, execute hot-patch remediations, and log ITSM incident tickets automatically.

---

## 🗺️ System Architecture

The following diagram illustrates the sequential agent reasoning loop, vector database lookup, and live GPU performance telemetry capture loop:

```mermaid
graph TD
    %% Elements
    A1[Prometheus Alerts]
    A2[Kibana Log Streams]
    A3[System Metrics]

    subgraph "Agent Swarm Reasoning Loop (Sequential Consensus)"
        Agent1[👁️ 1. Observability Agent]
        AgentMemory[(🧠 Agent Memory <br/> Vector DB Lookup)]
        Agent2[🔍 2. RCA Agent]
        Agent3[💥 3. Blast Radius Agent]
        Agent4[🛠️ 4. Remediation Agent]
        Agent5[⚡ 5. Operations Agent]
    end

    subgraph "Inference & Telemetry Platform"
        vLLM[🚀 vLLM Server <br/> Qwen2.5-7B-Instruct]
        GPU[📟 AMD Instinct MI300X <br/> 192GB HBM3 VRAM]
        ROCM[📊 rocm-smi Background <br/> Telemetry Sampling]
    end

    subgraph "NOC Resolution Center"
        Repair[🔧 Hot-Patch Command Execution]
        ServiceNow[📝 ServiceNow Incident Logs]
        Postmortem[📄 Dynamic Postmortem Generation]
        PPTX[📥 Executive Presentation Outline]
    end

    %% Routing
    A1 & A2 & A3 --> Agent1
    Agent1 -->|Evidence & Anomaly Flags| Agent2
    AgentMemory -.->|Historical Case Retrieval| Agent2
    Agent2 -->|Consensus Root Cause| Agent3
    Agent3 -->|Downstream Services Affected| Agent4
    Agent4 -->|Proposed Resolution Steps| Agent5

    %% Inference Calls
    Agent1 & Agent2 & Agent3 & Agent4 & Agent5 ===>|LLM Chat Completions API| vLLM
    vLLM ===>|AMD ROCm Engine| GPU
    GPU -.->|rocm-smi Telemetry Peaks| ROCM
    ROCM -.->|Peak W / Temp / Load| PPTX

    %% Output routing
    Agent5 --> Repair
    Agent5 --> ServiceNow
    Agent5 --> Postmortem
    Agent5 --> PPTX

    %% Styling Definitions
    classDef inputs fill:#1b2838,stroke:#ff9900,stroke-width:2px,color:#fff;
    classDef agent fill:#0f172a,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef hardware fill:#0b1329,stroke:#10b981,stroke-width:2px,color:#fff;
    classDef output fill:#1c2541,stroke:#a855f7,stroke-width:2px,color:#fff;

    %% Class Bindings
    class A1,A2,A3 inputs;
    class Agent1,AgentMemory,Agent2,Agent3,Agent4,Agent5 agent;
    class vLLM,GPU,ROCM hardware;
    class Repair,ServiceNow,Postmortem,PPTX output;
```

---

## 🛠️ Tech Stack & Dependencies

* **Inference Engine:** AMD ROCm v6.x + vLLM (v0.6.x+)
* **Model:** `Qwen/Qwen2.5-7B-Instruct`
* **Dashboard Interface:** Streamlit (v1.32.x+)
* **Libraries:** `openai` (vLLM local client), `numpy<2.2` (compatibility runtime)
* **ITSM Integration:** ServiceNow REST API Simulation

---

## 🚀 Deplay & Run Instructions

To deploy and test the platform on your AMD GPU instance, open three terminal windows in Jupyter Lab:

### Terminal 1: Initialize the vLLM Server
Serve the model locally using the ROCm-optimized vLLM container. This will bind the model to port `11434`:
```bash
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-7B-Instruct \
    --port 11434 \
    --gpu-memory-utilization 0.90 \
    --max-model-len 8192
```
*Note: `--gpu-memory-utilization 0.90` allocates ~172 GB of HBM3 VRAM to support Qwen's KV cache.*

### Terminal 2: Run the Streamlit Dashboard
Activate your virtual environment and launch the Streamlit app on port `8503` (to avoid system port conflicts):
```bash
source .venv/bin/activate
streamlit run app.py \
    --server.port 8503 \
    --server.address 0.0.0.0 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
```
You can access the UI via the Jupyter Proxy URL:
`https://<your-notebook-domain>/proxy/8503/`

### Alternative: Run the CLI Utility (Headless/CI Integration)
OpsPilot AI includes a standalone CLI tool (`cli.py`) for executing the agent swarm pipeline directly from your local terminal/shell environment (ideal for headless servers or automated alert triggers):
```bash
# Run in Mock Mode (local keyword-fallback for zero-LLM setup)
python cli.py data/scenarios/scenario1.json

# Run in Mock Mode, prompting the user for confirmation before executing the remediation
python cli.py data/scenarios/scenario1.json --execute

# Run in Mock Mode and execute the remediation instantly without prompting (auto-approve)
python cli.py data/scenarios/scenario1.json --execute -y

# Run in Live LLM Mode (requires the vLLM server to be active)
python cli.py data/scenarios/scenario1.json --live-llm --model Qwen/Qwen2.5-7B-Instruct

# Save the generated postmortem markdown report to a file
python cli.py data/scenarios/scenario1.json --output-postmortem postmortem.md
```

> [!NOTE]
> **Key CLI Features:**
> * **Interactive Safety Guard:** Specifying `--execute` alone will prompt you with `[y/N]` to confirm the repair. Supply the `-y` or `--yes` flag to bypass this confirmation (ideal for fully autonomous loops or cronjobs).
> * **Mock Mode (Default):** Runs instantly using pre-cached, high-fidelity scenario templates. This is great for rapid demonstrations, debugging, and verification without booting up a heavy GPU model.
> * **Live LLM Mode (`--live-llm`):** Routes agent prompts to the local OpenAI-compatible endpoint served by the vLLM server on port `11434`. Ensure your vLLM server (Terminal 1) is active before using this flag.



### Terminal 3: Monitor GPU Performance
Keep an eye on the GPU power draw, temperatures, and compute utilization:
```bash
watch -n 1 rocm-smi
```
During active swarm reasoning loops, you will observe the socket power draw rise from the **191W** idle state up to a peak of **~750W** at **98% GPU utilization**.

---

## 🧪 Testing Scenarios

OpsPilot AI is preloaded with three high-stakes incident scenarios, which can be selected via the sidebar:
1. **Critical Payment Outage:** Application database connection pool saturation.
2. **Order Processing Collapse:** JVM garbage collection (GC) thrashing and Heap Out-of-Memory (OOM).
3. **Telecom Network Failure:** BGP routing adjacency drop on a primary edge switch forcing fallback saturation.

### Testing Custom Scenarios
Reviewers can upload a custom JSON incident file (following the schema of `data/scenarios/scenario1.json`) using the **"Manual Upload"** panel in the sidebar. 
* **If Live LLM is ON:** The local vLLM endpoint performs real-time diagnostics, consensus negotiation, and postmortem writing.
* **If Live LLM is OFF:** A backend router (`_generate_fallback_mock` in `agents.py`) matches keywords (e.g. `"db"`, `"oom"`, `"bgp"`) to fallback on a matching high-fidelity mock template for fail-safe demo runs.

---

## 📄 Exporters & Postmortem Reports

1. **ServiceNow Ticket Log:** When remediation is executed, a ServiceNow incident ID (e.g., `INC-49281`) is simulated and printed alongside execution logs.
2. **Dynamic Postmortem:** A full post-incident markdown report is generated automatically, detailing root causes and future preventative actions.
3. **Executive Presentation Exporter:** The dashboard features a button to export a Markdown slide outline. This outline automatically embeds the peak **socket power draw**, **core junction temp**, **throughput (tokens/sec)**, and **GPU compute load** captured from `rocm-smi` during the diagnostic swarm.
