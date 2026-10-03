import pytest


@pytest.fixture()
def app(tmp_path):
    from app import create_app

    return create_app(
        {
            "TESTING": True,
            "DATABASE_PATH": str(tmp_path / "wat-the-flood.sqlite3"),
            "AI_MODEL_PATH": str(tmp_path / "missing-model.joblib"),
            "AI_MODEL_METADATA_PATH": str(tmp_path / "missing-model-metadata.json"),
        }
    )


@pytest.fixture()
def client(app):
    return app.test_client()
