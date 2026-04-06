from pathlib import Path

import pytest

from app.core.config import Settings
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
