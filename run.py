"""
Phalanx: Autonomous Adversarial Evaluation & Continuous Hardening Suite
Main CLI Entrypoint
"""

import argparse
import sys
import uvicorn
from phalanx.config import config
from phalanx.client import PhalanxClient
from phalanx.arena import FightArena
from phalanx.regression.suite import RegressionVault
from phalanx.regression.exporters import RegressionExporter
from phalanx.target.agent import TargetAgent
from phalanx.referee.judge import RefereeJudge


def run_terminal_benchmark(mutations: int = 2):
    print("\n" + "="*75)
    print(" 🛡️  PHALANX: AUTONOMOUS ADVERSARIAL RED-TEAMING & REGRESSION ENGINE")
    print("="*75)
    print(f"Inference Engine: {'Deterministic Mock Engine' if config.mock_mode else 'Nebius Token Factory'}")
    print(f"Models: Red Coach={config.red_model} | Target={config.blue_model} | Referee={config.judge_model}\n")

    client = PhalanxClient()
    vault = RegressionVault(storage_path="regression_vault.json")
    arena = FightArena(client=client, vault=vault)

    print("▶ Executing Multi-Turn Adversarial Self-Play Match...")
    report = arena.run_match(max_mutations_per_persona=mutations)

    print("\n" + "-"*75)
    print(" 📊 MATCH SUMMARY & QUANTITATIVE REMEDIATION RESULTS")
    print("-"*75)
    print(f"  • Total Fights / Scenarios:          {report.total_rounds}")
    print(f"  • Initial Attack Success Rate (ASR): {report.initial_asr:.1f}%")
    print(f"  • Post-Patch Replay ASR:             {report.patched_asr:.1f}%")
    print(f"  • Total Zero-Day Breaches Found:     {report.total_breaches}")
    print(f"  • Regression Test Cases Generated:   {report.regression_tests_added}")
    print(f"  • Delta Security Improvement:        +{(report.initial_asr - report.patched_asr):.1f}% Defense Delta")

    print("\n" + "-"*75)
    print(" 📋 DETAILED ROUND-BY-ROUND BREAKDOWN:")
    print("-"*75)
    for r in report.rounds:
        status_icon = "💥 BREACH" if r.verdict == "BREACH" else "🛡️ DEFENDED"
        print(f"  [{status_icon}] Round {r.round_number}: {r.persona}")
        print(f"     Strategy:  {r.strategy}")
        print(f"     Payload:   \"{r.attack_payload[:75]}...\"")
        print(f"     AVSS:      {r.avss_score} ({r.avss_severity}) | {r.owasp_tag}")
        print(f"     Action:    {r.agent_action} -> Tool: {r.tool_invoked}")
        if r.patch_generated:
            replayed_str = "Neutralized ✅" if r.replay_blocked else "Failed ❌"
            print(f"     Remedy:    {r.patch_generated}")
            print(f"     Replay:    {replayed_str}")
        print()

    # Export regression artifacts
    RegressionExporter.export_pytest_file(vault.cases, "test_phalanx_regression.py")
    RegressionExporter.export_sarif_report(vault.cases, "phalanx_report.sarif")
    print("  ✓ Exported Pytest test suite to: test_phalanx_regression.py")
    print("  ✓ Exported OASIS SARIF report to: phalanx_report.sarif")
    print("="*75 + "\n")


def run_terminal_probe(payload: str, patched: bool = False):
    print(f"\n[Injecting Probe: \"{payload}\" | Mode: {'Patched v2.0' if patched else 'Unprotected v1.0'}]")
    client = PhalanxClient()
    agent = TargetAgent(client=client, is_patched=patched)
    turn_res = agent.process_turn(payload)

    referee = RefereeJudge(client=client)
    verdict = referee.evaluate_turn(
        user_message=payload,
        agent_reasoning=turn_res.get("reasoning", ""),
        tool_call=turn_res.get("tool_call"),
        executed_result=turn_res.get("executed_result")
    )

    print(f"  • Agent Action:    {turn_res.get('action')}")
    print(f"  • Tool Invocation: {turn_res.get('tool_call')}")
    print(f"  • Referee Verdict: {verdict.verdict_text} (AVSS: {verdict.avss.score} - {verdict.avss.severity})")
    print(f"  • OWASP Tag:       {verdict.avss.owasp_tag}")
    print(f"  • Explanation:     {verdict.explanation}\n")


def launch_web_ui(host: str, port: int):
    print(f"\n🚀 Launching Phalanx Dashboard at: http://{host}:{port}")
    uvicorn.run("phalanx.ui.server:app", host=host, port=port, reload=False, log_level="info")


def main():
    parser = argparse.ArgumentParser(description="Phalanx: Adversarial Evaluation & Hardening Suite")
    subparsers = parser.add_subparsers(dest="command")

    # UI command
    ui_parser = subparsers.add_parser("ui", help="Launch interactive web dashboard")
    ui_parser.add_argument("--host", default=config.host, help="Bind host")
    ui_parser.add_argument("--port", type=int, default=config.port, help="Bind port")

    # Benchmark command
    bench_parser = subparsers.add_parser("benchmark", help="Run automated terminal adversarial benchmark")
    bench_parser.add_argument("--mutations", type=int, default=2, help="Max mutations per round")

    # Probe command
    probe_parser = subparsers.add_parser("probe", help="Run one-shot adversarial prompt injection")
    probe_parser.add_argument("--payload", required=True, help="Adversarial input text")
    probe_parser.add_argument("--patched", action="store_true", help="Test against patched agent")

    args = parser.parse_args()

    if args.command == "ui":
        launch_web_ui(args.host, args.port)
    elif args.command == "benchmark":
        run_terminal_benchmark(args.mutations)
    elif args.command == "probe":
        run_terminal_probe(args.payload, args.patched)
    else:
        # Default to running benchmark
        run_terminal_benchmark(2)


if __name__ == "__main__":
    main()
