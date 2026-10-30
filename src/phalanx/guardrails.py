"""Programmable Action Rails & Tool Execution Guardrails (NeMo Guardrails-inspired).

Provides deterministic, execution-time safety interlocks that evaluate tool calls
BEFORE they are executed against stateful backend banking infrastructure.
When an adversarial prompt injection manages to sway the LLM, the Action Rail
acts as a non-bypassable programmatic boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ActionRail(Protocol):
    name: str
    description: str

    def evaluate(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        verified_accounts: set[str],
        ledger_state: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """Returns (allowed: bool, rejection_reason: str | None)."""
        ...


@dataclass
class Strict2FAActionRail:
    """Blocks fund movement and sensitive PII disclosure without confirmed in-session 2FA."""

    name: str = "Strict2FAActionRail"
    description: str = "Enforces non-bypassable in-session SMS 2FA before any money movement or balance disclosure."

    def evaluate(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        verified_accounts: set[str],
        ledger_state: dict[str, Any],
    ) -> tuple[bool, str | None]:
        if tool_name == "disclose_balance":
            acc = arguments.get("account_id")
            if acc not in verified_accounts:
                return (
                    False,
                    f"Action rail violation: disclose_balance on {acc} blocked. Caller identity is not verified in current session.",
                )

        if tool_name == "initiate_transfer":
            from_acc = arguments.get("from_account")
            if from_acc not in verified_accounts:
                return (
                    False,
                    f"Action rail violation: initiate_transfer from {from_acc} blocked. Mandatory in-session 2FA required.",
                )

        return True, None


@dataclass
class DualControlThresholdRail:
    """Enforces dual-control human escalation for high-value transactions (>= $10,000)."""

    name: str = "DualControlThresholdRail"
    description: str = "Enforces regulatory dual-control authorization for transactions >= $10,000 USD."

    def evaluate(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        verified_accounts: set[str],
        ledger_state: dict[str, Any],
    ) -> tuple[bool, str | None]:
        if tool_name == "initiate_transfer":
            amount = float(arguments.get("amount_usd", 0))
            if amount >= 10_000:
                has_escalation = ledger_state.get("escalations_count", 0) > 0
                if not has_escalation:
                    return (
                        False,
                        f"Action rail violation: Transfer of ${amount:,.2f} exceeds single-operator limit ($10,000). Must call escalate_to_human first.",
                    )
        return True, None


@dataclass
class UntrustedCorrespondenceRail:
    """Treats customer correspondence as tainted user input, preventing indirect prompt injection."""

    name: str = "UntrustedCorrespondenceRail"
    description: str = "Validates that tool outputs from fetch_customer_correspondence are treated as untrusted data."

    def evaluate(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        verified_accounts: set[str],
        ledger_state: dict[str, Any],
    ) -> tuple[bool, str | None]:
        # Tainted data interlock: If correspondence has been read, ensure subsequent actions re-verify authentication
        if ledger_state.get("correspondence_read", False):
            if tool_name in ("initiate_transfer", "disclose_balance"):
                acc = arguments.get("from_account") or arguments.get("account_id")
                if acc not in verified_accounts:
                    return (
                        False,
                        f"Action rail violation: Potential indirect prompt injection. Operation on {acc} blocked pending independent 2FA.",
                    )
        return True, None


class GuardrailRegistry:
    def __init__(self, rails: list[ActionRail] | None = None) -> None:
        self.rails: list[ActionRail] = rails or [
            Strict2FAActionRail(),
            DualControlThresholdRail(),
            UntrustedCorrespondenceRail(),
        ]

    def validate_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        verified_accounts: set[str],
        ledger_state: dict[str, Any],
    ) -> tuple[bool, str | None, str | None]:
        """Runs tool arguments through all registered action rails.

        Returns: (allowed: bool, failing_rail_name: str | None, rejection_reason: str | None)
        """
        for rail in self.rails:
            allowed, reason = rail.evaluate(
                tool_name=tool_name,
                arguments=arguments,
                verified_accounts=verified_accounts,
                ledger_state=ledger_state,
            )
            if not allowed:
                return False, rail.name, reason
        return True, None, None
