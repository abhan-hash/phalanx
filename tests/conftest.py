"""Pytest configuration for PHALANX.

Default to offline mock mode for fast, deterministic unit testing
unless PHALANX_LIVE_TESTS is explicitly enabled.
"""

import os
import pytest

if os.environ.get("PHALANX_LIVE_TESTS", "").lower() not in ("true", "1"):
    os.environ["PHALANX_MOCK_MODE"] = "true"
