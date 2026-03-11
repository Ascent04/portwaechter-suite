from pathlib import Path
import importlib.util

import pytest

from modules.portfolio_ingest.normalizer import normalize_snapshot
from modules.portfolio_ingest.parser_tr_pdf import parse_tr_depotauszug


FIXTURE = Path("tests/fixtures/Depotauszug.pdf")
HAS_PDFMINER = importlib.util.find_spec("pdfminer") is not None


@pytest.mark.skipif(not FIXTURE.exists() or not HAS_PDFMINER, reason="Fixture PDF or pdfminer missing")
def test_normalize_total_within_tolerance() -> None:
    parsed = parse_tr_depotauszug(FIXTURE)
    snapshot = normalize_snapshot(parsed)

    pdf_total = snapshot.get("pdf_total_value_eur")
    assert pdf_total is not None
    diff = abs(snapshot["computed_total_eur"] - pdf_total)
    assert diff <= 0.50
