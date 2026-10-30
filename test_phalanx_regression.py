"""Auto-generated Phalanx Regression Test Suite.

Ensures known adversarial attack vectors in regression_vault.json are continuously defended.
"""

import pytest

def test_regression_fight_2e2948ac():
    """Regression test for breach fight-2e2948ac (fake-ceo / acme-roofing-bec)"""
    from phalanx.personas import load_persona, load_scenario
    from phalanx.runner import run_fight
    from phalanx.blue_team import BlueAgent

    persona = load_persona("fake-ceo")
    scenario = load_scenario("acme-roofing-bec")
    # Run with standard hardened blue agent
    blue = BlueAgent(mode="standard")
    transcript, verdict = run_fight(persona=persona, scenario=scenario, blue=blue, max_turns=6)
    assert verdict.winner == "blue", f"Regression failed for fight-2e2948ac: {verdict.notes}"

def test_regression_fight_56fd302e():
    """Regression test for breach fight-56fd302e (multi-turn-erosion / long-con-erosion)"""
    from phalanx.personas import load_persona, load_scenario
    from phalanx.runner import run_fight
    from phalanx.blue_team import BlueAgent

    persona = load_persona("multi-turn-erosion")
    scenario = load_scenario("long-con-erosion")
    # Run with standard hardened blue agent
    blue = BlueAgent(mode="standard")
    transcript, verdict = run_fight(persona=persona, scenario=scenario, blue=blue, max_turns=6)
    assert verdict.winner == "blue", f"Regression failed for fight-56fd302e: {verdict.notes}"

def test_regression_fight_b0a8bf50():
    """Regression test for breach fight-b0a8bf50 (aggressive-lawyer / lawyer-arbitration-emergency-wire)"""
    from phalanx.personas import load_persona, load_scenario
    from phalanx.runner import run_fight
    from phalanx.blue_team import BlueAgent

    persona = load_persona("aggressive-lawyer")
    scenario = load_scenario("lawyer-arbitration-emergency-wire")
    # Run with standard hardened blue agent
    blue = BlueAgent(mode="standard")
    transcript, verdict = run_fight(persona=persona, scenario=scenario, blue=blue, max_turns=6)
    assert verdict.winner == "blue", f"Regression failed for fight-b0a8bf50: {verdict.notes}"

def test_regression_fight_279a44c0():
    """Regression test for breach fight-279a44c0 (indirect-injector / planted-note-skip-2fa)"""
    from phalanx.personas import load_persona, load_scenario
    from phalanx.runner import run_fight
    from phalanx.blue_team import BlueAgent

    persona = load_persona("indirect-injector")
    scenario = load_scenario("planted-note-skip-2fa")
    # Run with standard hardened blue agent
    blue = BlueAgent(mode="standard")
    transcript, verdict = run_fight(persona=persona, scenario=scenario, blue=blue, max_turns=6)
    assert verdict.winner == "blue", f"Regression failed for fight-279a44c0: {verdict.notes}"

def test_regression_fight_5fa08c43():
    """Regression test for breach fight-5fa08c43 (indirect-injector / planted-note-skip-2fa)"""
    from phalanx.personas import load_persona, load_scenario
    from phalanx.runner import run_fight
    from phalanx.blue_team import BlueAgent

    persona = load_persona("indirect-injector")
    scenario = load_scenario("planted-note-skip-2fa")
    # Run with standard hardened blue agent
    blue = BlueAgent(mode="standard")
    transcript, verdict = run_fight(persona=persona, scenario=scenario, blue=blue, max_turns=6)
    assert verdict.winner == "blue", f"Regression failed for fight-5fa08c43: {verdict.notes}"

def test_regression_fight_24f1765b():
    """Regression test for breach fight-24f1765b (fake-ceo / acme-roofing-bec)"""
    from phalanx.personas import load_persona, load_scenario
    from phalanx.runner import run_fight
    from phalanx.blue_team import BlueAgent

    persona = load_persona("fake-ceo")
    scenario = load_scenario("acme-roofing-bec")
    # Run with standard hardened blue agent
    blue = BlueAgent(mode="standard")
    transcript, verdict = run_fight(persona=persona, scenario=scenario, blue=blue, max_turns=6)
    assert verdict.winner == "blue", f"Regression failed for fight-24f1765b: {verdict.notes}"

def test_regression_fight_966c8647():
    """Regression test for breach fight-966c8647 (fake-ceo / acme-roofing-bec)"""
    from phalanx.personas import load_persona, load_scenario
    from phalanx.runner import run_fight
    from phalanx.blue_team import BlueAgent

    persona = load_persona("fake-ceo")
    scenario = load_scenario("acme-roofing-bec")
    # Run with standard hardened blue agent
    blue = BlueAgent(mode="standard")
    transcript, verdict = run_fight(persona=persona, scenario=scenario, blue=blue, max_turns=6)
    assert verdict.winner == "blue", f"Regression failed for fight-966c8647: {verdict.notes}"

