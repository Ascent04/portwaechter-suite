from modules.common.utils import parse_de_number


def test_parse_de_number_thousands() -> None:
    assert parse_de_number("34.919,05") == 34919.05


def test_parse_de_number_decimal() -> None:
    assert parse_de_number("0,27") == 0.27


def test_parse_de_number_with_suffix() -> None:
    assert parse_de_number("165,65524 Stk.") == 165.65524
