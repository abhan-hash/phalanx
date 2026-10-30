"""Persona + Scenario YAML loaders and registry."""

from __future__ import annotations

from pathlib import Path
import yaml

from phalanx.models import Persona, Scenario

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONA_DIR = REPO_ROOT / "personas"
SCENARIO_DIR = REPO_ROOT / "scenarios"


def load_persona(name: str) -> Persona:
    path = PERSONA_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Persona YAML not found: {path}")
    data = yaml.safe_load(path.read_text())
    return Persona.model_validate(data)


def load_scenario(name: str) -> Scenario:
    path = SCENARIO_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Scenario YAML not found: {path}")
    data = yaml.safe_load(path.read_text())
    return Scenario.model_validate(data)


def list_personas() -> list[str]:
    if not PERSONA_DIR.exists():
        return []
    return sorted(p.stem for p in PERSONA_DIR.glob("*.yaml"))


def list_scenarios() -> list[str]:
    if not SCENARIO_DIR.exists():
        return []
    return sorted(p.stem for p in SCENARIO_DIR.glob("*.yaml"))


CANONICAL_PAIRS: list[tuple[str, str]] = [
    ("panicked-grandma", "grandma-bail-money"),
    ("aggressive-lawyer", "lawyer-trust-transfer"),
    ("executor-of-the-will", "will-executor-claim"),
    ("prompt-injector", "prompt-injection-probe"),
    ("fake-ceo", "acme-roofing-bec"),
    ("multi-turn-erosion", "long-con-erosion"),
]
