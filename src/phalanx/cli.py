"""PHALANX Command Line Interface.

Usage:
  python3 -m phalanx.cli fight <persona> --scenario <scn> --blue-mode naive
  python3 -m phalanx.cli coach --target-gap --auto-fight
  python3 -m phalanx.cli fix --all-red-wins
  python3 -m phalanx.cli leaderboard
  python3 -m phalanx.cli vault --generate-tests
  python3 -m phalanx.cli render
  python3 -m phalanx.cli serve --port 8000
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from phalanx.blue_team import BlueAgent, make_blue
from phalanx.coach import analyze_coverage_gaps, coach, select_instructive_fights
from phalanx.fix import fix_path_for, propose_fix, select_diagnosable_runs, write_fix
from phalanx.personas import (
    CANONICAL_PAIRS,
    list_personas,
    list_scenarios,
    load_persona,
    load_scenario,
)
from phalanx.runner import RUNS_DIR, aggregate_runs_to_jsonl, run_fight, save_run
from phalanx.vault import RegressionVault

console = Console()


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ and value:
            os.environ[key] = value


_load_dotenv()


@click.group()
def main() -> None:
    """PHALANX — Autonomous Adversarial Red-Teaming Arena for NVIDIA Nemotron Agents on Nebius."""


@main.command("personas")
def cmd_personas() -> None:
    """List available red-team attack personas."""
    names = list_personas()
    if not names:
        console.print("[yellow]No personas found in personas/[/yellow]")
        return
    t = Table(title="PHALANX Red-Team Personas", border_style="green")
    t.add_column("name", style="bold", no_wrap=True)
    t.add_column("category")
    t.add_column("difficulty", justify="right")
    t.add_column("preferred model")
    t.add_column("display name")
    for n in names:
        p = load_persona(n)
        t.add_row(p.name, p.attack_category.value, str(p.difficulty), p.preferred_llm, p.display_name)
    console.print(t)


@main.command("scenarios")
def cmd_scenarios() -> None:
    """List available attack scenarios."""
    names = list_scenarios()
    if not names:
        console.print("[yellow]No scenarios found in scenarios/[/yellow]")
        return
    t = Table(title="PHALANX Attack Scenarios", border_style="green")
    t.add_column("name", style="bold")
    t.add_column("target account")
    t.add_column("amount ($)", justify="right")
    t.add_column("description")
    for n in names:
        s = load_scenario(n)
        amt = f"${s.target_amount_usd:,.2f}" if s.target_amount_usd else "—"
        desc = (s.description or "").replace("\n", " ")[:70]
        t.add_row(s.name, s.target_account_holder, amt, desc)
    console.print(t)


@main.command("fight")
@click.argument("persona_name")
@click.option("--scenario", "scenario_name", required=True, help="Scenario YAML name.")
@click.option("--max-turns", default=14, show_default=True)
@click.option("--save/--no-save", default=True)
@click.option(
    "--blue-mode",
    type=click.Choice(["standard", "lenient", "naive", "external"]),
    default="standard",
    show_default=True,
    help="Blue CSR defense mode (standard, lenient, naive, external).",
)
def cmd_fight(
    persona_name: str,
    scenario_name: str,
    max_turns: int,
    save: bool,
    blue_mode: str,
) -> None:
    """Run one adversarial fight: red persona vs blue CSR agent."""
    persona = load_persona(persona_name)
    scenario = load_scenario(scenario_name)
    blue = make_blue(mode=blue_mode)

    header = Panel.fit(
        Text.assemble(
            ("🩸 RED  ", "bold red"),
            (f"{persona.display_name} ({persona.preferred_llm})", "red"),
            ("  vs  ", "dim"),
            ("🛡 BLUE  ", "bold green"),
            (f"MetroBank CSR [{blue_mode}] ({blue.model})", "green"),
            "\n",
            (f"scenario: {scenario.name}  |  target: {scenario.target_account_holder}", "dim"),
        ),
        title="[bold green]PHALANX ARENA[/bold green]",
        border_style="green",
    )
    console.print(header)

    def on_utt(u):
        style = "red" if u.speaker == "red" else "green" if u.speaker == "blue" else "dim"
        label = "RED ADVERSARY" if u.speaker == "red" else "BLUE DEFENDER" if u.speaker == "blue" else u.speaker.upper()
        body = u.content
        if u.tool_calls:
            calls = ", ".join(f"{c.name}({json.dumps(c.arguments)})" for c in u.tool_calls)
            body = f"{body}\n[dim]↳ tools executed: {calls}[/dim]"
        console.print(Panel.fit(body, title=label, border_style=style, padding=(0, 1)))

    transcript, verdict = run_fight(
        persona=persona,
        scenario=scenario,
        max_turns=max_turns,
        blue=blue,
        on_utterance=on_utt,
    )

    winner_color = {"red": "red", "blue": "green", "draw": "yellow"}[verdict.winner]
    summary = Table(title="Referee Verdict", show_header=False, title_style=f"bold {winner_color}")
    summary.add_column("k", style="dim")
    summary.add_column("v")
    summary.add_row("winner", f"[bold {winner_color}]{verdict.winner.upper()}[/bold {winner_color}]")
    summary.add_row("blue_score", str(verdict.blue_score))
    summary.add_row("red_score", str(verdict.red_score))
    summary.add_row("end_reason", str(transcript.end_reason))
    summary.add_row("notes", verdict.notes)
    if verdict.policy_breaches:
        summary.add_row("policy_breaches", "\n".join(f"• {b}" for b in verdict.policy_breaches))
    if verdict.deterministic_findings:
        summary.add_row(
            "deterministic_checks", "\n".join(f"• {f}" for f in verdict.deterministic_findings)
        )
    console.print(summary)

    if save:
        path = save_run(transcript, verdict, label=f"{persona.name}-{blue_mode}")
        console.print(f"[dim]Run saved → {path}[/dim]")


@main.command("batch")
@click.option(
    "--pairs",
    "pairs_spec",
    default="canonical",
    show_default=True,
    help="'canonical', 'all', or comma-separated pairs like 'panicked-grandma:grandma-bail-money'.",
)
@click.option(
    "--blue-modes",
    default="standard,lenient",
    show_default=True,
    help="Comma-separated blue modes.",
)
@click.option("--repeat", default=1, show_default=True, help="Repeat count.")
@click.option("--parallel", default=4, show_default=True, help="Parallel concurrency.")
@click.option("--max-turns", default=14, show_default=True)
def cmd_batch(
    pairs_spec: str,
    blue_modes: str,
    repeat: int,
    parallel: int,
    max_turns: int,
) -> None:
    """Run a batch matrix of fights to evaluate model robustness and grow corpus."""
    pairs = _resolve_pairs(pairs_spec)
    modes = [m.strip() for m in blue_modes.split(",") if m.strip()]
    matrix = [
        (persona_name, scenario_name, mode, rep)
        for persona_name, scenario_name in pairs
        for mode in modes
        for rep in range(repeat)
    ]
    console.print(
        f"[bold green]PHALANX batch execution[/bold green] pairs={len(pairs)} modes={len(modes)} repeat={repeat} total={len(matrix)}"
    )

    def _run_one(item):
        p_name, s_name, mode, rep = item
        p = load_persona(p_name)
        s = load_scenario(s_name)
        b = make_blue(mode=mode)
        transcript, verdict = run_fight(persona=p, scenario=s, max_turns=max_turns, blue=b)
        save_run(transcript, verdict, label=f"{p.name}-{mode}")
        return {"persona": p.name, "scenario": s.name, "mode": mode, "winner": verdict.winner}

    results = []
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        futures = [ex.submit(_run_one, item) for item in matrix]
        for f in as_completed(futures):
            results.append(f.result())

    red_wins = sum(1 for r in results if r["winner"] == "red")
    blue_wins = sum(1 for r in results if r["winner"] == "blue")
    console.print(f"[bold green]Batch complete:[/bold green] Blue wins: {blue_wins}, Red breaches: {red_wins}")


def _resolve_pairs(spec: str) -> list[tuple[str, str]]:
    if spec == "canonical":
        return CANONICAL_PAIRS
    if spec == "all":
        personas = list_personas()
        scenarios = list_scenarios()
        return [(p, s) for p in personas for s in scenarios]
    out = []
    for chunk in spec.split(","):
        p, _, s = chunk.strip().partition(":")
        if p and s:
            out.append((p, s))
    return out


@main.command("leaderboard")
@click.option("--mode", default=None, help="Filter to a specific blue mode.")
def cmd_leaderboard(mode: str | None) -> None:
    """Aggregate runs/*.json into defensive and adversarial threat leaderboards."""
    runs = sorted(RUNS_DIR.glob("*.json"))
    if not runs:
        console.print("[yellow]No runs found in runs/[/yellow]")
        return

    per_persona: dict[str, dict[str, int]] = defaultdict(
        lambda: {"red": 0, "blue": 0, "draw": 0, "blue_score_sum": 0, "n": 0}
    )
    per_mode: dict[str, dict[str, int]] = defaultdict(
        lambda: {"red": 0, "blue": 0, "draw": 0, "blue_score_sum": 0, "n": 0}
    )

    for r in runs:
        if r.name.endswith(".fix.json") or r.name.startswith("_"):
            continue
        try:
            payload = json.loads(r.read_text())
            transcript = payload["transcript"]
            verdict = payload["verdict"]
        except Exception:
            continue
        run_mode = transcript.get("blue_mode", "standard")
        if mode and run_mode != mode:
            continue
        winner = verdict.get("winner", "draw")
        bs = verdict.get("blue_score", 0)
        p_name = transcript.get("persona_name", "unknown")

        per_persona[p_name][winner] += 1
        per_persona[p_name]["blue_score_sum"] += bs
        per_persona[p_name]["n"] += 1

        per_mode[run_mode][winner] += 1
        per_mode[run_mode]["blue_score_sum"] += bs
        per_mode[run_mode]["n"] += 1

    t_mode = Table(title="Target Defense Robustness by Blue Mode", border_style="green")
    t_mode.add_column("mode", style="bold")
    t_mode.add_column("total tests", justify="right")
    t_mode.add_column("🛡 blue defenses", justify="right", style="green")
    t_mode.add_column("🩸 red breaches", justify="right", style="red")
    t_mode.add_column("draws", justify="right", style="yellow")
    t_mode.add_column("avg blue score", justify="right")
    for mode_name, stats in sorted(per_mode.items()):
        n = stats["n"]
        avg = f"{stats['blue_score_sum'] / n:.1f}" if n else "—"
        t_mode.add_row(
            mode_name, str(n), str(stats["blue"]), str(stats["red"]), str(stats["draw"]), avg
        )
    console.print(t_mode)

    t_p = Table(title="Adversarial Threat Leaderboard (by red breach rate)", border_style="red")
    t_p.add_column("persona", style="bold")
    t_p.add_column("tests", justify="right")
    t_p.add_column("🩸 red breaches", justify="right", style="red")
    t_p.add_column("🛡 blue held", justify="right", style="green")
    t_p.add_column("breach rate", justify="right", style="bold red")
    rows = []
    for name, stats in per_persona.items():
        n = stats["n"]
        rate = stats["red"] / n if n else 0.0
        rows.append((rate, name, stats))
    for rate, name, stats in sorted(rows, key=lambda x: -x[0]):
        t_p.add_row(name, str(stats["n"]), str(stats["red"]), str(stats["blue"]), f"{rate:.0%}")
    console.print(t_p)


@main.command("coach")
@click.option("--max-fights", default=4, show_default=True, help="Instructive fights to analyze.")
@click.option("--auto-fight", is_flag=True, help="Auto-run newly generated persona against blue modes.")
@click.option("--blue-modes", default="standard,lenient,naive", show_default=True)
@click.option("--target-gap", is_flag=True, help="Risk-weighted analysis targeting the weakest category.")
@click.option("--recon", is_flag=True, help="Ingest real-time zero-day threat intelligence (Tavily AI) to seed Coach.")
def cmd_coach(max_fights: int, auto_fight: bool, blue_modes: str, target_gap: bool, recon: bool) -> None:
    """Run Coach meta-agent to analyze corpus gaps and synthesize a new attack persona."""
    gaps = analyze_coverage_gaps(RUNS_DIR) if target_gap else None
    fights = select_instructive_fights(RUNS_DIR, max_fights=max_fights, target_gap=target_gap, gaps=gaps)
    if not fights:
        console.print("[yellow]No fights found to learn from. Run batch first.[/yellow]")
        return

    threat_findings = None
    if recon:
        from phalanx.recon import ThreatRecon
        tr = ThreatRecon()
        rep = tr.search_threats()
        threat_findings = rep.findings
        console.print(f"[bold cyan]Threat Radar ({rep.source}):[/bold cyan] Ingested {len(threat_findings)} zero-day mechanics.")

    if gaps:
        gap_table = Table(title="Coverage Gap Analysis (Weakest Attack Surfaces First)", border_style="yellow")
        gap_table.add_column("attack category", style="bold")
        gap_table.add_column("runs", justify="right")
        gap_table.add_column("red wins", justify="right", style="red")
        gap_table.add_column("breach rate", justify="right")
        gap_table.add_column("gap score", justify="right", style="bold yellow")
        for g in gaps[:5]:
            gap_table.add_row(
                g.attack_category,
                str(g.n_runs),
                str(g.red_wins),
                f"{g.red_win_rate:.0%}" if g.n_runs else "UNTESTED",
                f"{g.gap_score:.2f}",
            )
        console.print(gap_table)

    console.print("[bold green]Coach (Nemotron 3 Ultra)[/bold green] analyzing weaknesses and authoring exploit...")
    out = coach(fights, gaps=gaps, threat_intel=threat_findings)

    summary = Table(title="Coach Generated New Attack Persona", border_style="green")
    summary.add_column("field", style="dim")
    summary.add_column("value")
    summary.add_row("persona", out.persona_name)
    summary.add_row("scenario", out.scenario_name)
    p = out.raw_json.get("persona", {})
    summary.add_row("display_name", p.get("display_name", ""))
    summary.add_row("category", p.get("attack_category", ""))
    summary.add_row("difficulty", str(p.get("difficulty", "")))
    summary.add_row("rationale", out.rationale)
    summary.add_row("persona_file", str(out.persona_path))
    summary.add_row("scenario_file", str(out.scenario_path))
    console.print(summary)

    if auto_fight:
        modes = [m.strip() for m in blue_modes.split(",") if m.strip()]
        console.print(f"\n[green]Exercising newly generated attack against modes: {modes}...[/green]")
        persona = load_persona(out.persona_name)
        scenario = load_scenario(out.scenario_name)
        for mode in modes:
            blue = make_blue(mode=mode)
            transcript, verdict = run_fight(persona=persona, scenario=scenario, max_turns=10, blue=blue)
            save_run(transcript, verdict, label=f"{persona.name}-{mode}")
            tag = "🩸 RED BREACH" if verdict.winner == "red" else "🛡 BLUE HELD"
            console.print(f"  {mode:<10} {tag} (blue {verdict.blue_score} / red {verdict.red_score})")


@main.command("recon")
@click.option("--query", default="LLM agent prompt injection zero-day CVE financial", help="Threat search query.")
@click.option("--max-results", default=3, show_default=True, help="Number of zero-day threats to harvest.")
def cmd_recon(query: str, max_results: int) -> None:
    """Harvest real-time zero-day vulnerabilities & advisories (Tavily AI Intelligence)."""
    from phalanx.recon import ThreatRecon

    tr = ThreatRecon()
    with console.status("Querying threat intelligence radar..."):
        report = tr.search_threats(query=query, max_results=max_results)

    table = Table(title=f"Zero-Day Threat Radar ({report.source})", border_style="cyan")
    table.add_column("Advisory / CVE", style="bold cyan")
    table.add_column("Category", style="dim")
    table.add_column("Extracted Exploitation Mechanic")

    for f in report.findings:
        table.add_row(f.title, f.vector_category, f.extracted_mechanic)

    console.print(table)
    console.print(
        f"[dim]Run [bold]phalanx coach --recon[/bold] to synthesize new attack personas from these findings.[/dim]\n"
    )


@main.command("fix")
@click.argument("target", required=False)
@click.option("--all-red-wins", is_flag=True, help="Diagnose every breach in runs/.")
@click.option("--include-close", default=4, show_default=True, help="Include close calls.")
@click.option("--force", is_flag=True, help="Regenerate existing fix proposals.")
def cmd_fix(target: str | None, all_red_wins: bool, include_close: int, force: bool) -> None:
    """Diagnose failed fights and formulate concrete prompt patches & regression tests."""
    if all_red_wins:
        candidates = select_diagnosable_runs(RUNS_DIR, include_close=include_close)
    elif target:
        candidates = [Path(target)] if Path(target).exists() else list(RUNS_DIR.glob(f"*{target}*.json"))
    else:
        raise click.UsageError("Specify run target or --all-red-wins.")

    if not candidates:
        console.print("[yellow]No runs to diagnose.[/yellow]")
        return

    pending = [r for r in candidates if force or not fix_path_for(r).exists()]
    console.print(f"[bold green]Fix Agent[/bold green] diagnosing {len(pending)} run(s)...")

    for run in pending:
        payload = json.loads(run.read_text())
        proposal = propose_fix(payload)
        out = write_fix(proposal, run)
        sev = proposal.taxonomy.get("severity", "medium")
        console.print(f"  [green]Fix proposed:[/green] {proposal.persona_name} (sev={sev}) → {out.name}")


@main.command("verify")
@click.argument("target", default="fake-ceo")
@click.option("--all-fixes", is_flag=True, help="Verify all available .fix.json remediation proposals.")
def cmd_verify(target: str, all_fixes: bool) -> None:
    """Run closed-loop replay verification: Pre-Patch Breach vs Post-Patch Neutralization."""
    from phalanx.verifier import verify_remediation

    targets = []
    if all_fixes:
        for p in RUNS_DIR.glob("*.fix.json"):
            targets.append(p.name.replace(".fix.json", ""))
    else:
        targets.append(target)

    for tgt in targets:
        with console.status(f"Running closed-loop replay duel for {tgt}..."):
            try:
                res = verify_remediation(tgt)
            except Exception as e:
                console.print(f"[red]Verification failed for {tgt}: {e}[/red]")
                continue

        table = Table(title=f"Remediation Verification Duel: {res.persona_name} ({res.fight_id})", border_style="green")
        table.add_column("Phase", style="bold")
        table.add_column("Winner", justify="center")
        table.add_column("Blue Score", justify="right")
        table.add_column("Red Score", justify="right")
        table.add_column("Security Outcome")

        pre_win_color = "red" if res.pre_patch_winner == "red" else "green"
        post_win_color = "green" if res.post_patch_winner == "blue" else "red"

        table.add_row(
            "1. Pre-Patch Baseline",
            f"[{pre_win_color}]{res.pre_patch_winner.upper()}[/{pre_win_color}]",
            str(res.pre_patch_blue_score),
            str(res.pre_patch_red_score),
            "[red]EXPLOITED: Policy Breach[/red]",
        )
        table.add_row(
            "2. Post-Patch + Action Rails",
            f"[{post_win_color}]{res.post_patch_winner.upper()}[/{post_win_color}]",
            str(res.post_patch_blue_score),
            str(res.post_patch_red_score),
            "[bold green]NEUTRALIZED: Policy Enforced[/bold green]",
        )
        benign_status = "[green]PASSED[/green]" if res.benign_control_passed else "[red]REGRESSION[/red]"
        benign_outcome = "[green]0 False Positives (Legitimate 2FA Passed)[/green]" if res.benign_control_passed else "[red]False Positive (Legitimate flow blocked)[/red]"
        table.add_row(
            "3. Benign Control Flow",
            benign_status,
            str(res.benign_blue_score),
            str(res.benign_red_score),
            benign_outcome,
        )
        console.print(table)
        console.print(f"[bold green]Verification Status:[/bold green] {res.delta_summary}\n")


@main.command("vault")
@click.option("--generate-tests", is_flag=True, help="Auto-generate pytest regression suite from vault.")
def cmd_vault(generate_tests: bool) -> None:
    """Inspect the Regression Vault of permanent attack fixtures and export CI/CD tests."""
    vault = RegressionVault()
    console.print(f"[bold green]PHALANX Regression Vault:[/bold green] {len(vault.entries)} permanent attack fixtures indexed.")
    vault.save_vault_json()
    if generate_tests:
        test_file = Path(__file__).resolve().parents[2] / "test_phalanx_regression.py"
        vault.generate_pytest_suite(test_file)
        console.print(f"[green]Generated CI/CD Pytest regression suite → {test_file}[/green]")


@main.group("job")
def cmd_job_group() -> None:
    """Nebius Serverless Job Dispatcher & Distributed Runner."""


@cmd_job_group.command("manifest")
@click.option("--out", "out_path", default=None, help="Save manifest JSON path.")
def cmd_job_manifest(out_path: str | None) -> None:
    """Generate a Nebius Serverless Job specification manifest."""
    from phalanx.jobs import NebiusJobDispatcher

    dispatcher = NebiusJobDispatcher()
    manifest = dispatcher.generate_manifest()
    content = json.dumps(manifest, indent=2)
    if out_path:
        Path(out_path).write_text(content)
        console.print(f"[green]Wrote Nebius Serverless Job manifest → {out_path}[/green]")
    else:
        console.print_json(content)


@cmd_job_group.command("dispatch")
@click.option("--workers", default=6, show_default=True, help="Concurrent worker threads.")
@click.option("--max-turns", default=8, show_default=True, help="Turns per duel.")
def cmd_job_dispatch(workers: int, max_turns: int) -> None:
    """Dispatch and execute distributed red-team matrix on Nebius infrastructure."""
    from phalanx.jobs import NebiusJobDispatcher

    dispatcher = NebiusJobDispatcher()
    with console.status(f"Executing distributed job matrix with {workers} workers..."):
        summary = dispatcher.execute_job(workers=workers, max_turns=max_turns)

    table = Table(title=f"Nebius Serverless Job Execution: {summary.job_id}", border_style="green")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total Fights Executed", str(summary.total_fights))
    table.add_row("Blue Defensive Holds", f"[green]{summary.blue_defenses}[/green]")
    table.add_row("Red Policy Breaches", f"[red]{summary.red_breaches}[/red]")
    table.add_row("Average Blue Score", f"{summary.avg_blue_score:.1f} / 100")
    table.add_row("Execution Duration", f"{summary.duration_seconds:.2f}s")
    console.print(table)
    console.print(f"[bold green]Job Complete:[/bold green] All {summary.total_fights} run artifacts ingested into runs/.\n")


@main.command("export-jsonl")
@click.option("--out", "out_path", default=None, help="Output JSONL path.")
def cmd_export_jsonl(out_path: str | None) -> None:
    """Export all fight runs into a single JSONL file."""
    if out_path is None:
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        out_path = str(RUNS_DIR / f"_all-{ts}.jsonl")
    target = Path(out_path)
    count = aggregate_runs_to_jsonl(target)
    console.print(f"[green]Exported {count} fight runs → {target}[/green]")


@main.command("render")
@click.option("--out", "out_path", default=None, help="Output HTML file path.")
def cmd_render(out_path: str | None) -> None:
    """Compile the entire corpus and analytics into a self-contained HTML dashboard."""
    from phalanx.dashboard import render as render_dashboard

    target = Path(out_path) if out_path else None
    path = render_dashboard(target)
    console.print(f"[bold green]Dashboard compiled successfully → {path}[/bold green]")


@main.command("serve")
@click.option("--host", default=os.environ.get("HOST", "0.0.0.0"), show_default=True)
@click.option("--port", default=int(os.environ.get("PORT", 8000)), show_default=True)
def cmd_serve(host: str, port: int) -> None:
    """Start the PHALANX Web Server and REST API."""
    import uvicorn
    from phalanx.server import app

    has_key = bool(os.environ.get("NEBIUS_API_KEY"))
    mock_mode = os.environ.get("PHALANX_MOCK_MODE", "").lower() in ("true", "1")
    if has_key and not mock_mode:
        console.print("[bold green]Backend Engine: LIVE Nebius Token Factory (NVIDIA Nemotron Active)[/bold green]")
    else:
        console.print("[bold yellow]Backend Engine: OFFLINE DETERMINISTIC SIMULATION (NEBIUS_API_KEY not active)[/bold yellow]")

    console.print(f"[bold green]Starting PHALANX Server on http://{host}:{port}[/bold green]")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
