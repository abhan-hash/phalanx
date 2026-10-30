"""Unit tests for NeMo-style Action Rails & GuardrailRegistry."""

from phalanx.guardrails import (
    DualControlThresholdRail,
    GuardrailRegistry,
    Strict2FAActionRail,
    UntrustedCorrespondenceRail,
)
from phalanx.tools import ToolLedger


def test_strict_2fa_action_rail():
    rail = Strict2FAActionRail()

    # Unverified account should be blocked
    allowed, reason = rail.evaluate(
        tool_name="initiate_transfer",
        arguments={"from_account": "ACC-1001", "amount_usd": 500.0},
        verified_accounts=set(),
        ledger_state={},
    )
    assert not allowed
    assert "Strict2FAActionRail" in rail.name
    assert "blocked" in reason

    # Verified account should be allowed
    allowed_v, reason_v = rail.evaluate(
        tool_name="initiate_transfer",
        arguments={"from_account": "ACC-1001", "amount_usd": 500.0},
        verified_accounts={"ACC-1001"},
        ledger_state={},
    )
    assert allowed_v
    assert reason_v is None


def test_dual_control_threshold_rail():
    rail = DualControlThresholdRail()

    # Transfer >= $10k without prior escalation should be blocked
    allowed, reason = rail.evaluate(
        tool_name="initiate_transfer",
        arguments={"from_account": "ACC-1001", "amount_usd": 40000.0},
        verified_accounts={"ACC-1001"},
        ledger_state={"escalations_count": 0},
    )
    assert not allowed
    assert "exceeds single-operator limit" in reason

    # Transfer >= $10k with escalation ticket present should be allowed
    allowed_e, reason_e = rail.evaluate(
        tool_name="initiate_transfer",
        arguments={"from_account": "ACC-1001", "amount_usd": 40000.0},
        verified_accounts={"ACC-1001"},
        ledger_state={"escalations_count": 1},
    )
    assert allowed_e


def test_guardrail_registry_on_tool_ledger():
    registry = GuardrailRegistry()
    ledger = ToolLedger(guardrails=registry)

    # Calling transfer without 2FA should be intercepted by guardrail
    res = ledger.execute(
        "initiate_transfer",
        {"from_account": "ACC-1001", "to_account": "ACC-9999", "amount_usd": 40000.0},
    )
    assert res.get("error") == "GUARDRAIL_INTERCEPTED"
    assert "Strict2FAActionRail" in res.get("rail", "")
