from pathlib import Path

import pytest

from sikuli.config import muat_config
from sikuli.rules import muat_rules

ROOT = Path(__file__).resolve().parents[1]


FIXTURE = ROOT / "tests" / "fixtures"


@pytest.fixture
def cfg():
    # Konfigurasi dan rules contoh khusus tes, terpisah dari rules produksi di rules/.
    return muat_config(FIXTURE / "pipeline.yaml")


@pytest.fixture
def rules():
    return muat_rules(FIXTURE / "rules")
