"""PHALANX: Autonomous Adversarial Red-Teaming & Self-Hardening Harness for NVIDIA Nemotron Agents.

Natively powered by NVIDIA Nemotron models served on Nebius Token Factory.
"""

from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parents[2] / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

__version__ = "0.1.0"
