"""Round runner — orchestrates one adversarial fight end-to-end."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from phalanx.blue_team import BlueAgent
from phalanx.models import Persona, Scenario, Transcript, Utterance, Verdict
from phalanx.red_team import RedAgent
from phalanx.referee import judge
from phalanx.tools import ToolLedger

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO_ROOT / "runs"


def run_fight(
    persona: Persona,
    scenario: Scenario,
    *,
    max_turns: int = 14,
    blue: BlueAgent | None = None,
    on_utterance: Callable[[Utterance], None] | None = None,
    on_event: Callable[[str, Any], None] | None = None,
    guardrails: Any | None = None,
) -> tuple[Transcript, Verdict]:
    """Run one adversarial round. Returns (transcript, verdict)."""
    blue = blue or BlueAgent()
    red = RedAgent(persona=persona, scenario=scenario)
    planted = (
        [c.model_dump(mode="json") for c in scenario.planted_correspondence]
        if scenario.planted_correspondence
        else None
    )
    ledger = ToolLedger(planted_correspondence=planted, guardrails=guardrails)

    transcript = Transcript(
        fight_id=f"fight-{uuid.uuid4().hex[:8]}",
        persona_name=persona.name,
        scenario_name=scenario.name,
        blue_model=blue.model,
        blue_mode=blue.mode,
        red_model=red.model,
    )

    blue_view: list[dict[str, Any]] = []
    red_view: list[dict[str, Any]] = []

    def emit(u: Utterance) -> None:
        transcript.utterances.append(u)
        if on_event:
            on_event("utterance", u)
        if on_utterance:
            on_utterance(u)

    if on_event:
        on_event("status", {
            "phase": "red_opening",
            "speaker": "red",
            "message": f"{persona.display_name} is preparing opening adversarial scenario...",
        })

    # Red opens with its scripted opening line.
    opening = red.opening_line()
    emit(opening)
    blue_view.append({"role": "user", "content": opening.content})
    red_view.append({"role": "assistant", "content": opening.content})

    end_token = "<<END_CALL>>"

    for turn in range(max_turns):
        turn_num = turn + 1
        if on_event:
            on_event("status", {
                "phase": "blue_thinking",
                "turn": turn_num,
                "speaker": "blue",
                "message": f"MetroBank CSR ({blue.mode}) is analyzing intent & verifying security guardrails...",
            })

        # Blue responds.
        blue_utt = blue.respond(conversation=blue_view, ledger=ledger)
        emit(blue_utt)
        red_view.append({"role": "user", "content": blue_utt.content})

        if ledger.escalations:
            transcript.end_reason = "escalated"
            break

        if on_event:
            on_event("status", {
                "phase": "red_thinking",
                "turn": turn_num,
                "speaker": "red",
                "message": f"{persona.display_name} is calculating adversarial counter-tactic...",
            })

        # Red speaks again.
        red_utt = red.speak(red_view)

        # Strip the END_CALL token from the visible content but use it as a termination signal.
        if end_token in red_utt.content:
            red_utt.content = red_utt.content.replace(end_token, "").strip()
            if red_utt.content:
                emit(red_utt)
                blue_view.append({"role": "user", "content": red_utt.content})
            transcript.end_reason = "red_ended_call"
            break

        emit(red_utt)
        blue_view.append({"role": "user", "content": red_utt.content})
        red_view.append({"role": "assistant", "content": red_utt.content})

        # Early exit check if blue clearly broke policy this turn.
        if ledger.transfers_initiated or ledger.balances_disclosed:
            if turn >= max_turns - 2:
                transcript.end_reason = "policy_breach"
                break
    else:
        transcript.end_reason = "max_turns"

    transcript.ended_at = datetime.utcnow()

    if on_event:
        on_event("status", {
            "phase": "referee_judging",
            "message": "Nemotron 3 Super (120B) Referee is adjudicating duel against OWASP & SOC2 security taxonomy...",
        })

    verdict = judge(persona=persona, transcript=transcript, ledger=ledger)
    if on_event:
        on_event("verdict", {"transcript": transcript, "verdict": verdict})

    return transcript, verdict


def save_run(transcript: Transcript, verdict: Verdict, label: str = "") -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{transcript.started_at.strftime('%Y%m%d-%H%M%S')}-{transcript.fight_id}"
    if label:
        name = f"{name}-{label}"
    path = RUNS_DIR / f"{name}.json"
    payload = {
        "transcript": transcript.model_dump(mode="json"),
        "verdict": verdict.model_dump(mode="json"),
    }
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def aggregate_runs_to_jsonl(out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w") as fh:
        for run_file in sorted(RUNS_DIR.glob("*.json")):
            if run_file.name.endswith(".fix.json"):
                continue
            payload = json.loads(run_file.read_text())
            fh.write(json.dumps(payload, default=str) + "\n")
            count += 1
    return count
