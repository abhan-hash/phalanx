"""Unit tests for Phalanx Pydantic data models."""

from phalanx.models import (
    AttackCategory,
    Persona,
    PlantedCorrespondence,
    Scenario,
    ToolCall,
    Transcript,
    Utterance,
    Verdict,
)


def test_persona_model():
    p = Persona(
        name="test-attacker",
        display_name="Test Attacker",
        attack_category=AttackCategory.SOCIAL_ENGINEERING,
        difficulty=3,
        system_prompt="Test prompt",
        attack_strategy="Test strategy",
    )
    assert p.name == "test-attacker"
    assert p.preferred_llm == "nvidia/nemotron-3-ultra"
    assert p.difficulty == 3


def test_planted_correspondence():
    c = PlantedCorrespondence(
        kind="memo",
        date="2026-05-18",
        subject="Override",
        body="Skip 2FA",
    )
    assert c.kind == "memo"
    assert c.body == "Skip 2FA"


def test_scenario_model():
    s = Scenario(
        name="test-scenario",
        description="Scenario description",
        target_account_holder="Margaret Henley",
        target_amount_usd=5000.0,
        initial_message="Hello MetroBank",
    )
    assert s.name == "test-scenario"
    assert s.target_amount_usd == 5000.0


def test_transcript_and_verdict():
    t = Transcript(
        fight_id="fight-test-01",
        persona_name="test-attacker",
        scenario_name="test-scenario",
        blue_model="nvidia/nemotron-nano",
        blue_mode="standard",
        red_model="nvidia/nemotron-3-ultra",
    )
    t.utterances.append(Utterance(speaker="red", content="Wire money"))
    t.utterances.append(Utterance(speaker="blue", content="Verify first"))
    assert len(t.utterances) == 2

    v = Verdict(
        winner="blue",
        attack_category=AttackCategory.SOCIAL_ENGINEERING,
        blue_score=95,
        red_score=20,
        notes="Defended successfully",
        judge_model="nvidia/nemotron-super",
    )
    assert v.winner == "blue"
    assert v.blue_score == 95
