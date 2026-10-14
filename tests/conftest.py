from pathlib import Path

import pytest

from sikuli.config import muat_config
from sikuli.rules import muat_rules

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg():
    return muat_config(ROOT / "config" / "pipeline.yaml")


@pytest.fixture
def rules():
    return muat_rules(ROOT / "rules")
