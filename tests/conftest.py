import json
import shutil
from pathlib import Path
import pytest
from congress_scorecard import load_inputs, project_root
from congress_scorecard.data import sha256


def pytest_configure(config):
    # Pytest creates basetemp itself, but its parent may not exist on a fresh checkout.
    if config.option.basetemp:
        Path(config.option.basetemp).resolve().parent.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def partial():
    return load_inputs(snapshot="current-partial")


@pytest.fixture
def complete():
    return load_inputs(snapshot="synthetic-complete")


@pytest.fixture
def copied_root(tmp_path):
    shutil.copytree(project_root() / "data", tmp_path / "data")
    return tmp_path


def rehash_snapshot(root, snapshot="synthetic-complete"):
    path = root / "data/results" / snapshot / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    manifest["hashes"] = {relative: sha256(root / relative) for relative in manifest["hashes"]}
    path.write_text(json.dumps(manifest), encoding="utf-8")
