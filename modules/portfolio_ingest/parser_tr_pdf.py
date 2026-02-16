from __future__ import annotations

import re
from pathlib import Path

from pdfminer.high_level import extract_text

from modules.common.utils import parse_de_number

ISIN_RE = re.compile(r"[A-Z]{2}[A-Z0-9]{10}")
QTY_RE = re.compile(r"^\d[\d\.,]*\s*Stk\.$")
DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
NUMBER_RE = re.compile(r"^\d[\d\.,]*$")
TOTAL_RE = re.compile(r"^([\d\.,]+)\s*EUR$")


def _clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _extract_asof(text: str) -> str | None:
    match = re.search(r"zum\s+(\d{2}\.\d{2}\.\d{4})", text)
    return match.group(1) if match else None


def _noise_name_line(line: str) -> bool:
    lowered = line.lower()
    noise_prefixes = ("lagerland:", "wertpapierrechnung", "aufstellung über")
    return lowered.startswith(noise_prefixes)


def _find_indices(lines: list[str]) -> tuple[int, int]:
    header_idx = -1
    footer_idx = -1

    for idx, line in enumerate(lines):
        if line == "KURSWERT IN EUR":
            header_idx = idx
        if line.startswith("ANZAHL POSITIONEN:"):
            footer_idx = idx
            break

    if header_idx == -1:
        header_idx = 0
    if footer_idx == -1:
        footer_idx = len(lines)

    return header_idx, footer_idx


def _extract_rows(section_lines: list[str]) -> list[dict]:
    quantities = [line for line in section_lines if QTY_RE.match(line)]
    isin_idxs = [idx for idx, line in enumerate(section_lines) if ISIN_RE.search(line)]
    rows: list[dict] = []

    for row_idx, isin_idx in enumerate(isin_idxs):
        isin_line = section_lines[isin_idx]
        isin_match = ISIN_RE.search(isin_line)
        if not isin_match:
            continue

        name_lines: list[str] = []
        scan_idx = isin_idx - 1
        while scan_idx >= 0:
            line = section_lines[scan_idx]
            if ISIN_RE.search(line) or QTY_RE.match(line):
                break
            if _noise_name_line(line):
                scan_idx -= 1
                continue
            name_lines.insert(0, line)
            scan_idx -= 1

        row = {
            "qty_text": quantities[row_idx] if row_idx < len(quantities) else None,
            "name_lines": name_lines,
            "isin": isin_match.group(0),
            "price_text": None,
            "value_text": None,
        }
        rows.append(row)

    return rows


def _extract_prices_values(lines_after_footer: list[str]) -> tuple[list[str], list[str], float | None]:
    prices: list[str] = []
    values: list[str] = []
    total_value = None

    idx = 0
    while idx < len(lines_after_footer):
        line = lines_after_footer[idx]

        if line.startswith("Achtung:"):
            break

        total_match = TOTAL_RE.match(line)
        if total_match:
            try:
                total_value = parse_de_number(total_match.group(1))
            except ValueError:
                total_value = None
            idx += 1
            continue

        if DATE_RE.match(line):
            idx += 1
            continue

        if NUMBER_RE.match(line):
            next_line = lines_after_footer[idx + 1] if idx + 1 < len(lines_after_footer) else ""
            if DATE_RE.match(next_line):
                prices.append(line)
                idx += 2
                continue
            values.append(line)

        idx += 1

    return prices, values, total_value


def parse_tr_depotauszug(pdf_path: str | Path) -> dict:
    text = extract_text(str(pdf_path))
    lines = _clean_lines(text)

    header_idx, footer_idx = _find_indices(lines)
    section_lines = lines[header_idx + 1 : footer_idx]
    rows = _extract_rows(section_lines)

    footer_line = lines[footer_idx] if footer_idx < len(lines) else ""
    footer_count_match = re.search(r"ANZAHL POSITIONEN:\s*(\d+)", footer_line)
    positions_count = int(footer_count_match.group(1)) if footer_count_match else None

    prices, values, total_value = _extract_prices_values(lines[footer_idx + 1 :])
    for idx, row in enumerate(rows):
        row["price_text"] = prices[idx] if idx < len(prices) else None
        row["value_text"] = values[idx] if idx < len(values) else None

    status = "ok"
    if positions_count is None or total_value is None:
        status = "degraded_parse_footer"

    return {
        "asof": _extract_asof(text),
        "rows": rows,
        "footer": {
            "positions_count": positions_count,
            "total_value_eur": total_value,
        },
        "status": status,
    }
