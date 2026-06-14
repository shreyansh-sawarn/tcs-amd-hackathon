import os
import json
import time
from typing import Dict, Any

# Mock response library for fail-safe demo mode (in case LLM is offline or unconfigured)
MOCK_RESPONSES = {
    "Critical Payment Outage": {
        "observability": {
            "evidence": "• Payment API response time > 3 seconds (SLA breach)\n• DBConnectionPool saturation alert (100% utilized)",
            "reasoning": "The connection pool is fully saturated, leading to queue delays. Downstream services are failing to acquire database connections, which results in cascading timeouts and HTTP 500 errors in the Billing Service.",
            "conclusion": "Database connection pool exhaustion is causing a cascading payment processing failure.",
            "confidence": 88
        },
        "rca": {
            "consensus_rca": "Database Connection Pool Exhaustion",
            "obs_confidence": 88,
            "rca_confidence": 94,
            "consensus_confidence": 91,
            "negotiation": "Observability Agent flagged Payment API timeouts. RCA Agent correlated this with connection pool utilization at 100%, while server CPU (42%) and Memory (68%) remain healthy. Both agents negotiated and agreed that the root cause is Connection Pool Exhaustion, ruling out database server hardware starvation.",
            "evidence": "• Active DB connections: 100/100 (100% capacity)\n• Server CPU and Memory utilization remain in normal limits.",
            "reasoning": "Since the database host CPU/RAM are normal, the issue is not database hardware starvation. The bottleneck is the application-side pool limit of 100 connections.",
            "conclusion": "Database connection pool limit of 100 is too low for the current transaction volume, causing queue saturation."
        },
        "blast_radius": {
            "affected_services": ["Payment API", "Billing Service", "Checkout Page"],
            "user_impact": "35% of checkout transactions failing",
            "severity": "Critical"
        },
        "remediation": {
            "steps": [
                "1. Scale the database connection pool limits from 100 to 250 in the application deployment configurations.",
                "2. Force-terminate idle connection threads hung in wait states.",
                "3. Gracefully rolling-restart the Payment API service pods to clear connection pool states."
            ],
            "do_nothing_30m": "Payment failure rate will climb to 55%. Downstream order backlogs will saturate message queues, causing overall checkout page outages.",
            "do_nothing_60m": "SLA breaches will trigger automated customer refund pipelines. Total estimated transaction revenue loss: $18,500/hr."
        },
        "operations": {
            "command": "kubectl patch deployment payment-api -p '{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"payment-api\",\"env\":[{\"name\":\"DB_MAX_CONNECTIONS\",\"value\":\"250\"}]}]}}}}'",
            "postmortem": """# INCIDENT POSTMORTEM REPORT: INC-2026-001

## Incident Summary
OpsPilot AI detected a critical outage in the Payment processing flow. The system was unable to establish database connections, leading to cascading failures in Billing and Checkout services.

## Outage Timeline
* **12:03 PM**: Alert triggered: Payment API latency > 3 seconds.
* **12:04 PM**: Observability Agent scanned logs and identified connection pool exhaustion timeouts.
* **12:05 PM**: RCA Agent correlated normal CPU/Memory metrics with connection spikes, ruling out server starvation.
* **12:06 PM**: Blast Radius Agent identified downstream impact (Billing Service, Checkout Page).
* **12:07 PM**: Remediation Agent proposed pool expansion plan.
* **12:08 PM**: Operations Agent executed hot-patch to scale max pool connections to 250.
* **12:09 PM**: Automated checks confirmed database connection pool returned to stable utilization (35%). System marked Healthy.

## Root Cause
The database connection pool limit of 100 was exceeded due to a traffic spike on the Checkout flow, causing the Payment API to hang and fail liveness probes.

## Resolution
The database connection pool maximum was increased from 100 to 250 using deployment configuration hot-patching.

## Future Prevention
1. Implement dynamic connection pooling scale-up.
2. Establish rate-limiting on the Payment API endpoint.
3. Configure alerts for connection pool saturation at 80% threshold.
"""
        }
    },
    "Order Processing Collapse": {
        "observability": {
            "evidence": "• OrderProcessing Pod restarted (liveness probe failure)\n• Pod memory utilization exceeds 95% threshold",
            "reasoning": "JVM Heap utilization is pinned at 96% and logs contain `java.lang.OutOfMemoryError: Java heap space`. This indicates that the JVM heap size is fully saturated and cannot allocate new memory objects, leading to container crashes.",
            "conclusion": "JVM heap space saturation is causing recurrent service container restarts.",
            "confidence": 92
        },
        "rca": {
            "consensus_rca": "JVM Heap Out of Memory (OOM) due to Batch Memory Leak",
            "obs_confidence": 92,
            "rca_confidence": 96,
            "consensus_confidence": 94,
            "negotiation": "Observability Agent identified the repeated container restarts. RCA Agent reviewed metrics indicating RAM usage was pinned at 99% with high CPU load (85%), typical of JVM Garbage Collection thrashing prior to crash. Consensus reached: The batch processing algorithm is leaking memory under heavy loads, exhausting the 2G heap space.",
            "evidence": "• Memory usage pinned at 99%\n• High CPU load (85%) indicating Garbage Collection thrashing\n• Recurrent `java.lang.OutOfMemoryError: Java heap space`",
            "reasoning": "High CPU utilization combined with memory saturation is the classic signature of GC thrashing, where the garbage collector spends 98% of its time trying to recover memory but frees less than 2% of the heap.",
            "conclusion": "A batch processing memory leak is preventing memory recovery, causing JVM crash."
        },
        "blast_radius": {
            "affected_services": ["OrderProcessing Service", "Inventory Sync", "Mobile App Checkout"],
            "user_impact": "50% of orders stuck in processing state",
            "severity": "High"
        },
        "remediation": {
            "steps": [
                "1. Temporarily increase Java max heap memory limit (-Xmx) from 2G to 4G in the Kubernetes configuration map.",
                "2. Perform a rolling restart of the OrderProcessing deployment.",
                "3. Schedule code patch to fix the non-garbage-collected collection arrays in the batch service."
            ],
            "do_nothing_30m": "Order processing queue backlog will exceed 10,000 items, delaying shipping updates. Out of memory restarts will cascade to inventory sync daemon.",
            "do_nothing_60m": "Mobile App order placements will begin dropping entirely. Est. business impact: 15,000 users blocked from purchases."
        },
        "operations": {
            "command": "kubectl set env deployment/order-proc-service JAVA_OPTS='-Xmx4G'",
            "postmortem": """# INCIDENT POSTMORTEM REPORT: INC-2026-002

## Incident Summary
The OrderProcessing service became unstable due to a JVM heap exhaustion, leading to container restarts and order delays.

## Outage Timeline
* **11:45 AM**: High memory usage alert triggered.
* **11:47 AM**: Observability Agent flagged OutOfMemory logs.
* **11:48 AM**: RCA Agent confirmed GC thrashing via CPU metrics and memory pinning.
* **11:49 AM**: Blast Radius identified Order Sync and Mobile Client disruption.
* **11:50 AM**: Operations Agent executed JVM environment update scaling heap memory to 4G.
* **11:51 AM**: Service liveness and readiness checks passed. Recovery complete.

## Root Cause
A memory leak inside the batch order processing buffer caused the JVM heap space to fill up completely without garbage collection, triggering OOM errors.

## Resolution
The Max JVM Heap memory limit (-Xmx) was dynamically scaled from 2G to 4G to absorb current load, followed by a deployment rolling restart.

## Future Prevention
1. Refactor batch allocation loops to release object references.
2. Set heap dump analysis alerts.
"""
        }
    },
    "Telecom Network Failure": {
        "observability": {
            "evidence": "• BGP Session Down with core switch (EdgeRouter01)\n• Edge Gateway Packet Loss > 15%",
            "reasoning": "The primary GigabitEthernet0/1 protocol interface protocol is down. Outgoing network traffic has failed over to the backup link, causing routing congestion (packet loss 18.5% and latency 420ms).",
            "conclusion": "Primary edge link down forcing failover and saturation on the backup connection.",
            "confidence": 85
        },
        "rca": {
            "consensus_rca": "Primary Link Port Down causing Saturation on Backup Router Link",
            "obs_confidence": 85,
            "rca_confidence": 90,
            "consensus_confidence": 87,
            "negotiation": "Observability Agent identified the primary link GigabitEthernet0/1 protocol down. RCA Agent matched this with a BGP adjacency drop and validated that the backup interface GigabitEthernet0/2 is overloaded, causing the 420ms latency. Agreed that the root cause is physical port link down on the primary interface forcing high-latency fallback.",
            "evidence": "• BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down\n• Primary Link Gig0/1 Protocol down\n• Backup Link Gig0/2 saturated",
            "reasoning": "The primary fiber path failed, forcing dynamic routing failover to a smaller capacity backup path. This backup path is physically incapable of routing the edge voice/data traffic, causing packet queues to discard data.",
            "conclusion": "Physical fiber link flap or port failure on GigabitEthernet0/1."
        },
        "blast_radius": {
            "affected_services": ["Customer Edge VoIP Gateways", "WAN VPN Tunnel", "NOC Telemetry Stream"],
            "user_impact": "High-latency and dropped calls for 100% of VoIP users connected via EdgeRouter01",
            "severity": "Critical"
        },
        "remediation": {
            "steps": [
                "1. Reboot and reset GigabitEthernet0/1 interface on EdgeRouter01 to re-establish link state.",
                "2. Clear and reset the BGP routing neighbor table to force route re-advertisement.",
                "3. Adjust Quality of Service (QoS) on the backup GigabitEthernet0/2 link to prioritize voice traffic."
            ],
            "do_nothing_30m": "Complete BGP routing loop could form if backup saturated links drop keep-alive packets. Office VPN networks will disconnect.",
            "do_nothing_60m": "Total communication outage for regional office endpoints. Violation of enterprise SLA ($50,000 penalty tier)."
        },
        "operations": {
            "command": "ssh admin@10.255.0.1 'config t; interface GigabitEthernet0/1; shutdown; no shutdown; exit; clear ip bgp *'",
            "postmortem": """# INCIDENT POSTMORTEM REPORT: INC-2026-003

## Incident Summary
Primary edge router port Gig0/1 dropped protocol link, forcing all regional network traffic onto backup connection Gig0/2. The backup link saturated, causing voice quality drop and massive packet loss.

## Outage Timeline
* **10:10 AM**: GigabitEthernet0/1 protocol interface down.
* **10:11 AM**: Alerts triggered for BGP adjacency loss and 18.5% packet loss.
* **10:12 AM**: Observability Agent flagged interface down states.
* **10:13 AM**: RCA Agent verified link overload.
* **10:14 AM**: Operations Agent executed SSH switch reload on GigabitEthernet0/1 and reset BGP peer tables.
* **10:15 AM**: Link state returned to Green. Network latency dropped back to 12ms.

## Root Cause
Physical link layer flap on GigabitEthernet0/1 interface caused routing protocols to failover to a lower-capacity backup port.

## Resolution
The primary interface was rebooted via SSH administrative override, and routing tables were forced to re-converge.

## Future Prevention
1. Replace physical fiber patch cable on Gig0/1.
2. Upgrade backup link capacity.
"""
        }
    }
}

class AgentOrchestrator:
    def __init__(self, use_real_llm: bool = False, model_name: str = "qwen3-8b"):
        self.use_real_llm = use_real_llm
        self.model_name = model_name
        self.client = None
        
        if self.use_real_llm:
            try:
                from openai import OpenAI
                # Typically points to local Ollama, vLLM, or LM Studio running on user's setup
                self.client = OpenAI(
                    base_url=os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1"),
                    api_key=os.getenv("OPENAI_API_KEY", "ollama")
                )
            except ImportError:
                print("OpenAI SDK not installed. Defaulting to mock mode.")
                self.use_real_llm = False

    def run_pipeline(self, scenario_name: str, raw_input: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Runs the 5-agent sequential context pipeline.
        If use_real_llm is true, calls the LLM with structured outputs.
        Otherwise, returns highly detailed mock outputs for a flawless demo.
        """
        if not self.use_real_llm:
            # Check if it's one of our preloaded scenarios
            if scenario_name in MOCK_RESPONSES:
                # Add simulated pipeline delay to make the Streamlit demo feel real
                time.sleep(0.5) 
                return MOCK_RESPONSES[scenario_name]
            else:
                # Fallback generator for custom uploads if LLM is offline
                return self._generate_fallback_mock(scenario_name, raw_input)
        
        # Real LLM implementation
        return self._run_real_llm_pipeline(scenario_name, raw_input)

    def _run_real_llm_pipeline(self, scenario_name: str, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        # Implementation of real LLM chain
        try:
            alerts = raw_input.get("alerts", [])
            logs = raw_input.get("logs", [])
            metrics = raw_input.get("metrics", {})
            history = raw_input.get("historical_incidents", [])

            # 1. Observability Agent Call
            obs_prompt = f"""You are the Observability Agent. Analyze the following alerts and logs.
Alerts: {json.dumps(alerts)}
Logs: {json.dumps(logs)}
Identify key anomalies and error patterns. 
Return JSON format ONLY:
{{
  "evidence": "Describe the evidence found (key logs, errors, metrics)...",
  "reasoning": "Explain your reasoning about the anomaly...",
  "conclusion": "Provide a concise summary/conclusion of the observability analysis...",
  "confidence": 90
}}"""

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": obs_prompt}],
                response_format={"type": "json_object"}
            )
            obs_out = json.loads(response.choices[0].message.content)

            # 2. RCA Agent Call
            rca_prompt = f"""You are the RCA Agent. You receive:
- Observability Agent's findings: {obs_out['conclusion']} (Confidence: {obs_out['confidence']}%)
- Metrics: {json.dumps(metrics)}
- Historical Incident: {json.dumps(history)}

Identify the exact Root Cause. Synthesize the findings and negotiate a consensus with the Observability Agent's view.
Return JSON format ONLY:
{{
  "consensus_rca": "Exact Name of Root Cause",
  "obs_confidence": {obs_out['confidence']},
  "rca_confidence": 95,
  "consensus_confidence": 92,
  "negotiation": "Explain the collaboration and consensus path...",
  "evidence": "Evidence found for root cause...",
  "reasoning": "Reasoning path leading to the root cause...",
  "conclusion": "Root Cause conclusion statement"
}}"""
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": rca_prompt}],
                response_format={"type": "json_object"}
            )
            rca_out = json.loads(response.choices[0].message.content)

            # 3. Blast Radius Agent
            blast_prompt = f"""You are the Blast Radius Agent. Given the diagnosed root cause: {rca_out['consensus_rca']}.
Analyze the downstream service impact, user failure rates, and business severity.
Return JSON format ONLY:
{{
  "affected_services": ["Service A", "Service B"],
  "user_impact": "X% of operations affected",
  "severity": "Low/Medium/High/Critical"
}}"""
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": blast_prompt}],
                response_format={"type": "json_object"}
            )
            blast_out = json.loads(response.choices[0].message.content)

            # 4. Remediation Agent
            rem_prompt = f"""You are the Remediation Agent. Given the root cause: {rca_out['consensus_rca']} and Blast Radius: {json.dumps(blast_out)}.
Propose step-by-step remediation commands. Also project the business impact if we do nothing for 30 minutes and 60 minutes.
Return JSON format ONLY:
{{
  "steps": ["Step 1...", "Step 2..."],
  "do_nothing_30m": "Impact if we do nothing for 30m...",
  "do_nothing_60m": "Impact if we do nothing for 60m..."
}}"""
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": rem_prompt}],
                response_format={"type": "json_object"}
            )
            rem_out = json.loads(response.choices[0].message.content)

            # 5. Operations Agent (Simulates remediation and creates postmortem report)
            ops_prompt = f"""You are the Operations Agent. Write a detailed incident postmortem in markdown format.
Root Cause: {rca_out['consensus_rca']}
Remediation Steps: {json.dumps(rem_out['steps'])}
Scenario: {scenario_name}
Create a complete postmortem including: Incident Summary, Timeline of Events, Root Cause, Resolution, and Future Prevention. Also suggest a single shell/kubectl command to execute the remediation.
Return JSON format ONLY:
{{
  "command": "remediation shell command here",
  "postmortem": "markdown formatted postmortem report here"
}}"""
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": ops_prompt}],
                response_format={"type": "json_object"}
            )
            ops_out = json.loads(response.choices[0].message.content)

            return {
                "observability": obs_out,
                "rca": rca_out,
                "blast_radius": blast_out,
                "remediation": rem_out,
                "operations": ops_out
            }

        except Exception as e:
            # Raise the exception with helpful setup diagnostic instructions
            raise RuntimeError(
                f"LLM Connection Error: {e}.\n"
                f"Please verify:\n"
                f"1. Is the vLLM server running in Terminal 1?\n"
                f"2. Does the 'Model Name' text box exactly match the vLLM model name (case-sensitive: 'Qwen/Qwen2.5-7B-Instruct')?"
            )

    def _generate_fallback_mock(self, scenario_name: str, raw_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dynamically extracts keywords from custom user input files to generate
        a semi-realistic analysis report even without a live LLM connection.
        """
        # Parse what we can from user inputs
        alerts = raw_input.get("alerts", []) if raw_input else []
        logs = raw_input.get("logs", []) if raw_input else []
        
        alert_str = " ".join(alerts).lower()
        log_str = " ".join(logs).lower()
        
        # Simple rule matcher to fit custom uploads
        if "db" in alert_str or "database" in alert_str or "connection" in log_str:
            return MOCK_RESPONSES["Critical Payment Outage"]
        elif "oom" in alert_str or "memory" in log_str or "heap" in log_str:
            return MOCK_RESPONSES["Order Processing Collapse"]
        else:
            return MOCK_RESPONSES["Telecom Network Failure"]
