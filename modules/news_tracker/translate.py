from __future__ import annotations


def translate_stub(item: dict) -> dict:
    translated = dict(item)
    title = item.get("title", "")

    if item.get("lang") == "en":
        translated["title_de"] = "[EN] " + title
        translated["summary_de"] = ["(Übersetzung ausstehend)"]
    else:
        translated["title_de"] = title
        translated["summary_de"] = []

    return translated
