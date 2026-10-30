"""Tests for Blue and Red agents."""

from phalanx.blue_team import BlueAgent, make_blue
from phalanx.personas import load_persona, load_scenario
from phalanx.red_team import RedAgent
from phalanx.tools import ToolLedger


def test_blue_agent_initialization():
    blue_std = make_blue("standard")
    assert blue_std.mode == "standard"
    assert "Verification first" in blue_std.system_prompt

    blue_naive = make_blue("naive")
    assert blue_naive.mode == "naive"
    assert "first-call resolution" in blue_naive.system_prompt


def test_red_agent_opening_and_speak():
    persona = load_persona("fake-ceo")
    scenario = load_scenario("acme-roofing-bec")
    red = RedAgent(persona=persona, scenario=scenario)

    opening = red.opening_line()
    assert opening.speaker == "red"
    assert "Janet Park" in opening.content

    reply = red.speak([{"role": "user", "content": "Please verify your account."}])
    assert reply.speaker == "red"
    assert len(reply.content) > 0


def test_blue_agent_respond_loop():
    blue = BlueAgent(mode="standard")
    ledger = ToolLedger()
    conversation = [
        {"role": "user", "content": "Hi, I am Margaret Henley (ACC-1001). Can I get my balance?"}
    ]
    utt = blue.respond(conversation=conversation, ledger=ledger)
    assert utt.speaker == "blue"
    assert len(utt.content) > 0
