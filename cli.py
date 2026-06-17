#!/usr/bin/env python3
"""
OpsPilot AI — Command Line Interface
Enables running the multi-agent swarm resolution pipeline directly from the command line.
"""

import argparse
import json
import os
import sys
import time
from backend.agents import AgentOrchestrator
from backend.tools import execute_remediation_command, create_servicenow_incident

def main():
    # Force UTF-8 stdout encoding to support emojis on Windows terminals
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    parser = argparse.ArgumentParser(
        description="OpsPilot AI — Command Line Incident Swarm Resolution",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "scenario_path", 
        help="Path to the incident scenario JSON file (e.g., data/scenarios/scenario1.json)"
    )
    parser.add_argument(
        "--live-llm", 
        action="store_true", 
        help="Enable live LLM inference (requires vLLM server running on port 11434)"
    )
    parser.add_argument(
        "--model", 
        default="Qwen/Qwen2.5-7B-Instruct", 
        help="vLLM Model name (default: Qwen/Qwen2.5-7B-Instruct)"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompt and execute remediation directly"
    )
    parser.add_argument(
        "--output-postmortem", 
        help="Path to save the generated postmortem markdown report (e.g., postmortem.md)"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.scenario_path):
        print(f"❌ Error: Scenario file not found at '{args.scenario_path}'")
        sys.exit(1)
        
    try:
        with open(args.scenario_path, "r", encoding="utf-8") as f:
            scenario_data = json.load(f)
    except Exception as e:
        print(f"❌ Error parsing scenario JSON: {e}")
        sys.exit(1)
        
    scenario_name = scenario_data.get("name", "Custom Scenario")
    
    print("=" * 70)
    print(f"🚀 OpsPilot AI — Command Line Interface")
    print(f"Incident: {scenario_name}")
    print(f"Mode:     {'Live LLM (vLLM Engine)' if args.live_llm else 'Mock Mode (Local Fallback)'}")
    if args.live_llm:
        print(f"Model:    {args.model}")
    print("=" * 70)
    
    # Initialize the agent orchestrator
    orchestrator = AgentOrchestrator(use_real_llm=args.live_llm, model_name=args.model)
    
    try:
        start_time = time.time()
        results = orchestrator.run_pipeline(scenario_name, scenario_data)
        elapsed = time.time() - start_time
        
        # 1. Observability Agent Results
        obs = results.get("observability", {})
        print(f"\n👁️  [1. Observability Agent] (Confidence: {obs.get('confidence', 0)}%)")
        print("-" * 50)
        print(f"Evidence Identified:\n{obs.get('evidence', 'N/A')}")
        print(f"Conclusion: {obs.get('conclusion', 'N/A')}")
        
        # 2. RCA Agent Results
        rca = results.get("rca", {})
        print(f"\n🔍 [2. RCA Agent] (Confidence: {rca.get('consensus_confidence', 0)}%)")
        print("-" * 50)
        print(f"Consensus RCA: {rca.get('consensus_rca', 'N/A')}")
        print(f"Negotiation Trail: {rca.get('negotiation', 'N/A')}")
        print(f"Evidence Correlated: {rca.get('evidence', 'N/A')}")
        
        # 3. Blast Radius Agent Results
        blast = results.get("blast_radius", {})
        print(f"\n💥 [3. Blast Radius Agent] (Severity: {blast.get('severity', 'N/A')})")
        print("-" * 50)
        print(f"Affected Services: {', '.join(blast.get('affected_services', []))}")
        print(f"End User Impact:   {blast.get('user_impact', 'N/A')}")
        
        # 4. Remediation Agent Results
        rem = results.get("remediation", {})
        print(f"\n🛠️  [4. Remediation Agent]")
        print("-" * 50)
        print("Proposed Remediation Action Plan:")
        for step in rem.get("steps", []):
            print(f"  {step}")
        print(f"Do Nothing Projection (30m): {rem.get('do_nothing_30m', 'N/A')}")
        print(f"Do Nothing Projection (60m): {rem.get('do_nothing_60m', 'N/A')}")
        
        # 5. Operations Agent Results
        ops = results.get("operations", {})
        command = ops.get("command", "")
        print(f"\n⚡ [5. Operations Agent]")
        print("-" * 50)
        print(f"Generated Hot-Patch Command: {command}")
        
        # Execute remediation simulation (prompts for confirmation unless -y/--yes is provided)
        if command:
            should_execute = True
            if not args.yes:
                try:
                    user_input = input(f"\n❓ Do you want to execute the remediation command: '{command}'? [y/N]: ").strip().lower()
                    should_execute = user_input in ("y", "yes")
                except KeyboardInterrupt:
                    print("\nExecution cancelled.")
                    sys.exit(1)
            
            if should_execute:
                print(f"\n🔧 Executing Remediation Command...")
                exec_res = execute_remediation_command(command)
                print(f"  ↳ Status:    {exec_res.get('status')}")
                print(f"  ↳ Timestamp: {exec_res.get('timestamp')}")
                print(f"  ↳ Output:\n{exec_res.get('output')}")
                
                print(f"\n📝 Registering ServiceNow Incident Ticket...")
                incident_id = create_servicenow_incident(scenario_data)
                print(f"  ↳ Incident Logged: {incident_id} (State: Resolved)")
            else:
                print("\n⏭️ Remediation command execution skipped by user request.")
        else:
            print("\n⚠️ No remediation command available to execute.")
        
        # Save or display postmortem report
        postmortem_content = ops.get("postmortem", "")
        if args.output_postmortem:
            try:
                with open(args.output_postmortem, "w", encoding="utf-8") as pf:
                    pf.write(postmortem_content)
                print(f"\n📄 Saved postmortem report to: {args.output_postmortem}")
            except Exception as e:
                print(f"\n⚠️ Failed to save postmortem report: {e}")
        else:
            print("\n" + "=" * 70)
            print("📄 GENERATED INCIDENT POSTMORTEM REPORT")
            print("=" * 70)
            print(postmortem_content.strip())
            
        print("\n" + "=" * 70)
        print(f"⏱️ Swarm reasoning completed successfully in {elapsed:.2f} seconds.")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Pipeline execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
