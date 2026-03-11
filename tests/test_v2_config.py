from __future__ import annotations

from modules.v2.config import load_v2_config, resolve_env_value


def test_resolve_env_value_reads_env_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / "portwaechter.env"
    env_file.write_text("TWELVEDATA_API_KEY=test-key\n", encoding="utf-8")
    monkeypatch.delenv("TWELVEDATA_API_KEY", raising=False)

    cfg = load_v2_config()
    cfg["app"]["root_dir"] = str(tmp_path)
    cfg["v2"]["env_file"] = str(env_file)

    assert resolve_env_value(cfg, "TWELVEDATA_API_KEY") == "test-key"
