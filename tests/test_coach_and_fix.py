"""Tests for Coach and Fix agents."""

from pathlib import Path
from phalanx.coach import analyze_coverage_gaps, coach, select_instructive_fights
from phalanx.fix import propose_fix
from phalanx.runner import RUNS_DIR


def test_coverage_gap_analysis():
    gaps = analyze_coverage_gaps(RUNS_DIR)
    assert len(gaps) >= 4
    for g in gaps:
        assert g.attack_category is not None
        assert 0.0 <= g.gap_score <= 1.0


def test_select_instructive_fights():
    fights = select_instructive_fights(RUNS_DIR, max_fights=3)
    assert len(fights) <= 3
    for f in fights:
        assert "transcript" in f
        assert "verdict" in f


def test_coach_authoring(tmp_path):
    fights = select_instructive_fights(RUNS_DIR, max_fights=2)
    output = coach(fights)
    assert output.persona_name is not None
    assert output.scenario_name is not None
    assert output.persona_path.exists()
    assert output.scenario_path.exists()


def test_fix_proposal():
    fights = select_instructive_fights(RUNS_DIR, max_fights=1)
    if fights:
        proposal = propose_fix(fights[0])
        assert proposal.summary is not None
        assert "tactic" in proposal.root_cause
        assert "patch_lines" in proposal.prompt_patch
        assert len(proposal.regression_tests) > 0
