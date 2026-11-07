import json
from pathlib import Path
import nbformat
import pytest

from congress_scorecard.runner import NotebookRunError, execute_notebooks


def notebook(path, source):
    nbformat.write(nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source)]), path)
    return path


@pytest.mark.parametrize("snapshot,expected", [("current-partial", 33), ("synthetic-complete", 35)])
def test_fresh_kernels_snapshot_switching_and_output_preservation(tmp_path, snapshot, expected):
    first = notebook(tmp_path / "first.ipynb", "marker = 'first kernel'\nprint('first')")
    second = notebook(tmp_path / "second.ipynb", """
assert 'marker' not in globals()
import os, sys
from congress_scorecard.runtime import load_context
ctx = load_context('02_forecast_accuracy')
print(ctx.inputs.snapshot_id)
print(ctx.inputs.diagnostics['verified_calls'])
assert str(ctx.output_dir) == os.environ['CONGRESS_SCORECARD_OUTPUT_DIR']
(ctx.tables_dir / 'coverage.txt').write_text(str(ctx.inputs.diagnostics['verified_calls']))
print(sys.executable)
""")
    before = first.read_bytes(), second.read_bytes()
    directory = execute_notebooks(snapshot=snapshot, notebooks=[first, second], output_root=tmp_path / "outputs")
    manifest = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "succeeded"
    assert len(manifest["graphics_assets"]["logo"]["sha256"]) == 64
    assert set(manifest["graphics_assets"]["fonts"]) == {"headline", "body", "emphasis"}
    assert [r["status"] for r in manifest["notebooks"]] == ["succeeded", "succeeded"]
    assert (directory / "tables/02_forecast_accuracy/coverage.txt").read_text() == str(expected)
    assert (first.read_bytes(), second.read_bytes()) == before
    next_run = execute_notebooks(snapshot=snapshot, notebooks=[first], output_root=tmp_path / "outputs")
    assert next_run != directory and (directory / "run.json").is_file()


def test_runner_failure_is_saved_and_reported(tmp_path):
    path = notebook(tmp_path / "failure.ipynb", "raise RuntimeError('known failure control')")
    with pytest.raises(NotebookRunError) as caught:
        execute_notebooks(snapshot="current-partial", notebooks=[path], output_root=tmp_path / "outputs")
    directory = caught.value.run_dir
    manifest = json.loads((directory / "run.json").read_text())
    assert manifest["status"] == "failed"
    assert manifest["notebooks"][0]["status"] == "failed"
    assert "known failure control" in (directory / "logs/failure.error.txt").read_text()
    assert (directory / "notebooks/failure.ipynb").is_file()


def test_runner_validates_before_creating_outputs(tmp_path):
    with pytest.raises((ValueError, FileNotFoundError)):
        execute_notebooks(snapshot="missing-snapshot", output_root=tmp_path / "outputs")
    assert not (tmp_path / "outputs").exists()


def test_invalid_notebook_is_rejected_before_output_creation(tmp_path):
    broken = tmp_path / "broken.ipynb"
    broken.write_text("invalid notebook JSON")
    with pytest.raises(Exception):
        execute_notebooks(snapshot="current-partial", notebooks=[broken], output_root=tmp_path / "outputs")
    assert not (tmp_path / "outputs").exists()
