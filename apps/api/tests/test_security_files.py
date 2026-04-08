from pathlib import Path

import pytest

from app.utils.files import safe_join, sanitize_filename


def test_sanitize_filename():
    assert sanitize_filename('../../x?.txt') == 'x_.txt'


def test_safe_join_blocks_traversal(tmp_path: Path):
    with pytest.raises(ValueError):
        safe_join(tmp_path, '..', 'evil.txt')
