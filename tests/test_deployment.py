from pathlib import Path


def test_systemd_service_uses_waitress_and_unprivileged_runtime():
    service_path = Path(__file__).parents[1] / "deployment" / "wat-the-flood.service"
    service = service_path.read_text(encoding="utf-8")

    assert "User=wat-the-flood" in service
    assert "Group=wat-the-flood" in service
    assert "waitress-serve" in service
    assert "--call" in service
    assert "--listen=0.0.0.0:8000" in service
    assert "Restart=on-failure" in service
    assert "WAT_THE_FLOOD_PROFILE" in service
    assert "WAT_THE_FLOOD_DATABASE" in service
    assert "NoNewPrivileges=true" in service


def test_runtime_environment_paths_are_supported(monkeypatch, tmp_path):
    from config import load_settings

    monkeypatch.setenv("WAT_THE_FLOOD_DATABASE", str(tmp_path / "runtime.sqlite3"))
    monkeypatch.setenv("WAT_THE_FLOOD_MODEL", str(tmp_path / "model.joblib"))
    monkeypatch.setenv(
        "WAT_THE_FLOOD_MODEL_METADATA", str(tmp_path / "model-metadata.json")
    )

    settings = load_settings()

    assert settings.database_path == tmp_path / "runtime.sqlite3"
    assert settings.ai_model_path == tmp_path / "model.joblib"
    assert settings.ai_metadata_path == tmp_path / "model-metadata.json"
