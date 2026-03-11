from pathlib import Path
import importlib.util

import pytest

from modules.portfolio_ingest.parser_tr_pdf import parse_tr_depotauszug


FIXTURE = Path("tests/fixtures/Depotauszug.pdf")
HAS_PDFMINER = importlib.util.find_spec("pdfminer") is not None


@pytest.mark.skipif(not FIXTURE.exists() or not HAS_PDFMINER, reason="Fixture PDF or pdfminer missing")
def test_parse_footer_values() -> None:
    parsed = parse_tr_depotauszug(FIXTURE)
    footer = parsed["footer"]

    assert footer["positions_count"] == 12
    assert footer["total_value_eur"] == pytest.approx(34919.05, abs=0.01)
