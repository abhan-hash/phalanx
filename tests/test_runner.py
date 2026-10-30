"""Tests for Phalanx runner and referee."""

from phalanx.blue_team import BlueAgent
from phalanx.personas import load_persona, load_scenario
from phalanx.runner import run_fight


def test_run_fight_standard_defense():
    persona = load_persona("fake-ceo")
    scenario = load_scenario("acme-roofing-bec")
    blue = BlueAgent(mode="standard")

    transcript, verdict = run_fight(
        persona=persona,
        scenario=scenario,
        blue=blue,
        max_turns=6,
    )

    assert transcript.persona_name == "fake-ceo"
    assert transcript.scenario_name == "acme-roofing-bec"
    assert len(transcript.utterances) >= 2
    assert verdict.winner in ("blue", "red", "draw")
    assert verdict.blue_score >= 0


def test_run_fight_naive_breach():
    persona = load_persona("fake-ceo")
    scenario = load_scenario("acme-roofing-bec")
    blue = BlueAgent(mode="naive")

    transcript, verdict = run_fight(
        persona=persona,
        scenario=scenario,
        blue=blue,
        max_turns=6,
    )

    assert verdict.winner == "red"
    assert verdict.red_score >= 80
    assert len(verdict.deterministic_findings) > 0
