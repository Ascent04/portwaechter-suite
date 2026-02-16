from pathlib import Path

import pytest

from modules.portfolio_ingest.parser_tr_pdf import parse_tr_depotauszug


FIXTURE = Path("tests/fixtures/Depotauszug.pdf")


@pytest.mark.skipif(not FIXTURE.exists(), reason="Fixture PDF missing")
def test_parse_footer_values() -> None:
    parsed = parse_tr_depotauszug(FIXTURE)
    footer = parsed["footer"]

    assert footer["positions_count"] == 12
    assert footer["total_value_eur"] == pytest.approx(34919.05, abs=0.01)
