"""Unit tests for the Closed-Loop Replay & Verification Engine."""

from phalanx.verifier import verify_remediation


def test_verify_remediation_delta():
    result = verify_remediation("fake-ceo")
    assert result.fight_id is not None
    assert result.pre_patch_winner == "red"
    assert result.post_patch_winner == "blue"
    assert result.attack_neutralized is True
    assert result.benign_control_passed is True
    assert "Attack Neutralized: True" in result.delta_summary

    data = result.to_dict()
    assert "pre_patch" in data
    assert "post_patch" in data
    assert data["attack_neutralized"] is True
