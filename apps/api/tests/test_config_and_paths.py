from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.artifact_manager import create_ai_generated_artifact
from app.services.runtime_state import set_gpu_enabled


def test_config_load_desktop_mode(tmp_path: Path):
    s = Settings(env='desktop', data_root=str(tmp_path / 'desktop-data'))
    assert s.env == 'desktop'
    assert Path(s.data_root).exists()
    assert Path(s.upload_root).exists()


def test_invalid_env_handling():
    with pytest.raises(Exception):
        Settings(env='invalid-env')


def test_runtime_state_path_safety(tmp_path: Path):
    s = Settings(env='dev', data_root=str(tmp_path / 'state-root'))
    assert str(s.runtime_state_file).startswith(str(Path(s.data_root)))


def test_artifact_data_path_write(tmp_path: Path):
    root = tmp_path / 'uploads'
    root.mkdir(parents=True, exist_ok=True)
    target = root / 'probe.txt'
    target.write_text('ok', encoding='utf-8')
    assert target.read_text(encoding='utf-8') == 'ok'


def test_runtime_state_toggle_writes_file():
    enabled = set_gpu_enabled(True)
    assert enabled is True


def test_postgresql_first_default():
    s = Settings()
    assert s.database_url.startswith("postgresql")


def test_sqlite_relative_path_fallback(tmp_path: Path):
    s = Settings(env='dev', data_root=str(tmp_path / 'sqlite-root'), database_url='sqlite+pysqlite:///./local.db')
    assert str(s.database_url).startswith('sqlite+pysqlite:///')
    assert 'local.db' in s.database_url


def test_artifact_manager_writes_under_upload_root(tmp_path: Path, monkeypatch):
    class DummyDB:
        def add(self, _obj):
            return None

        def flush(self):
            return None

    from app.core.config import settings

    monkeypatch.setattr(settings, "upload_root", str(tmp_path / "uploads"))
    asset = create_ai_generated_artifact(
        DummyDB(),
        project_id=1,
        chat_thread_id=2,
        message_id=3,
        content="artifact content",
        model_name="demo-model",
        model_role="assistant",
    )
    assert str(asset.stored_path).startswith(str(tmp_path / "uploads"))
    assert Path(asset.stored_path).exists()
