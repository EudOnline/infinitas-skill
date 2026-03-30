from pathlib import Path

from tests.helpers.repo_copy import copy_repo_without_local_state


def test_repo_copy_omits_local_virtualenv_and_git_metadata(tmp_path: Path):
    repo = copy_repo_without_local_state(tmp_path)
    assert not (repo / ".git").exists()
    assert not (repo / ".venv").exists()
