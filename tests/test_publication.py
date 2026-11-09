"""Publication validates before writes and restores managed files on failure."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import nbformat
from PIL import Image
import pytest

from congress_scorecard.data import sha256

SPEC = importlib.util.spec_from_file_location(
    "publish_scorecard", Path(__file__).resolve().parents[1] / "scripts/publish_scorecard.py"
)
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def edit_json(path, change):
    value = publisher.read_json(path)
    change(value)
    write_json(path, value)


def publication_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in [root / publisher.NOTEBOOK, *(root / publisher.PUBLICATION).iterdir()]}


@pytest.fixture
def publication(tmp_path, monkeypatch):
    root = tmp_path / "release"
    for name in ["scripts", "src/congress_scorecard", "notebooks", "data", publisher.PUBLICATION]:
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "scripts/example.py").write_text("# source\n")
    (root / "pyproject.toml").write_text("# project\n")
    (root / "data/input.csv").write_text("frozen\n")
    snapshot = "test-real"
    snapshot_manifest = {"synthetic": False, "senate_timestamp": "2026-11-04T22:05:02-05:00",
                         "house_timestamp": "2026-11-04T22:20:52-05:00"}
    inputs = SimpleNamespace(snapshot_id=snapshot, manifest=snapshot_manifest,
                             hashes={"data/input.csv": sha256(root / "data/input.csv")},
                             diagnostics={"qualifications": ["Preliminary"]})
    monkeypatch.setattr(publisher, "load_inputs", lambda **kwargs: inputs)
    run = root / "outputs" / snapshot / "run-1"
    (run / "notebooks").mkdir(parents=True)
    cell = nbformat.v4.new_code_cell("print('coverage')")
    source = nbformat.v4.new_notebook(cells=[cell])
    nbformat.write(source, root / publisher.NOTEBOOK)
    cell.execution_count = 1
    cell.outputs = [nbformat.v4.new_output("stream", name="stdout", text="coverage\n")]
    nbformat.write(source, run / publisher.NOTEBOOK)
    tables = run / f"tables/{publisher.PART}"
    figures = run / f"figures/{publisher.PART}"
    tables.mkdir(parents=True)
    figures.mkdir(parents=True)
    image, data = "01-chart.png", "plot_01-chart.csv"
    Image.new("RGB", (1920, 1080), "navy").save(figures / image)
    (tables / data).write_text(f"value,snapshot,synthetic\n1,{snapshot},False\n")
    assets = {"logo": {"filename": "logo.png", "sha256": "a" * 64}}
    analysis = {"snapshot": snapshot, "synthetic": False, "input_hashes": inputs.hashes,
                "graphics_assets": assets, "editable_source": publisher.NOTEBOOK,
                "senate_timestamp": snapshot_manifest["senate_timestamp"],
                "house_timestamp": snapshot_manifest["house_timestamp"],
                "figures": [{"image": image, "data": data, "lint_passed": True}],
                "artifact_hashes": {image: sha256(figures / image), data: sha256(tables / data)}}
    analysis_path = tables / "analysis-provenance.json"
    write_json(analysis_path, analysis)
    manifest_path = run / "run.json"
    write_json(manifest_path, {"status": "succeeded", "synthetic": False, "snapshot": snapshot,
                              "snapshot_manifest": snapshot_manifest, "input_hashes": inputs.hashes,
                              "source_hashes": publisher.source_hashes(root), "graphics_assets": assets,
                              "dependencies": {}, "python_executable": "C:/private/python.exe",
                              "notebooks": [{"name": f"{publisher.PART}.ipynb", "status": "succeeded",
                                             "code_cells": 1}]})
    pub = root / publisher.PUBLICATION
    (pub / "old.png").write_bytes(b"old image")
    (pub / "plot_old.csv").write_bytes(b"old data")
    (pub / "keep.txt").write_bytes(b"unlisted supporting file")
    write_json(pub / "provenance.json", {"figures": [{"image": "old.png", "data": "plot_old.csv"}]})
    return SimpleNamespace(root=root, run=run, inputs=inputs, manifest=manifest_path,
                           analysis=analysis_path, tables=tables, figures=figures, pub=pub)


def test_promotion_publishes_one_run_and_preserves_unlisted_and_history(publication):
    f = publication
    original_run = {p.relative_to(f.run): p.read_bytes() for p in f.run.rglob('*') if p.is_file()}
    assert publisher.publish(f.root, f.run, reviewed=True) == 4
    assert not (f.pub / "old.png").exists() and not (f.pub / "plot_old.csv").exists()
    assert (f.pub / "keep.txt").read_bytes() == b"unlisted supporting file"
    assert (f.root / publisher.NOTEBOOK).read_bytes() == (f.run / publisher.NOTEBOOK).read_bytes()
    provenance = publisher.read_json(f.pub / "provenance.json")
    assert provenance["run_id"] == "run-1" and provenance["review"]["numerical_and_visual_review_confirmed"]
    assert "python_executable" not in provenance
    for name, digest in provenance["artifact_hashes"].items():
        assert sha256(f.pub / name) == digest
    assert original_run == {p.relative_to(f.run): p.read_bytes() for p in f.run.rglob('*') if p.is_file()}
    before = publication_bytes(f.root)
    publisher.publish(f.root, f.run, reviewed=True)
    assert publication_bytes(f.root) == before


@pytest.mark.parametrize("case", [
    "unreviewed", "failed", "synthetic", "input_synthetic", "snapshot", "snapshot_manifest",
    "input_hash", "input_file", "source_hash", "source_file", "notebook_source", "notebook_error",
    "unexecuted", "notebook_missing", "missing_artifact", "altered_png", "altered_csv",
    "csv_snapshot", "csv_synthetic", "analysis_snapshot", "timestamp", "lint", "duplicate",
    "path_traversal", "missing_hash", "portable_path", "portable_posix_path", "unlisted_collision",
])
def test_rejections_leave_publication_unchanged(publication, case):
    f = publication
    if case == "failed": edit_json(f.manifest, lambda m: m.update(status="failed"))
    elif case == "synthetic": edit_json(f.manifest, lambda m: m.update(synthetic=True))
    elif case == "input_synthetic": f.inputs.manifest["synthetic"] = True
    elif case == "snapshot": edit_json(f.manifest, lambda m: m.update(snapshot="other"))
    elif case == "snapshot_manifest": edit_json(f.manifest, lambda m: m["snapshot_manifest"].update(senate_timestamp="other"))
    elif case == "input_hash": edit_json(f.manifest, lambda m: m.update(input_hashes={}))
    elif case == "input_file": (f.root / "data/input.csv").write_text("changed")
    elif case == "source_hash": edit_json(f.manifest, lambda m: m.update(source_hashes={}))
    elif case == "source_file": (f.root / "scripts/example.py").write_text("changed")
    elif case == "notebook_source":
        n = nbformat.read(f.root / publisher.NOTEBOOK, 4)
        n.cells[0].source = "print('changed')"
        nbformat.write(n, f.root / publisher.NOTEBOOK)
    elif case in ("notebook_error", "unexecuted"):
        n = nbformat.read(f.run / publisher.NOTEBOOK, 4)
        if case == "notebook_error":
            n.cells[0].outputs = [nbformat.v4.new_output("error", ename="Error", evalue="failure", traceback=[])]
        else: n.cells[0].execution_count = None
        nbformat.write(n, f.run / publisher.NOTEBOOK)
    elif case == "notebook_missing": edit_json(f.manifest, lambda m: m.update(notebooks=[]))
    elif case == "missing_artifact": (f.figures / "01-chart.png").unlink()
    elif case == "altered_png": (f.figures / "01-chart.png").write_bytes(b"altered")
    elif case in ("altered_csv", "csv_snapshot", "csv_synthetic"):
        csv_path = f.tables / "plot_01-chart.csv"
        csv_path.write_text("value,snapshot,synthetic\n1,other,False\n" if case != "csv_synthetic"
                            else "value,snapshot,synthetic\n1,test-real,True\n")
        if case != "altered_csv":
            edit_json(f.analysis, lambda a: a["artifact_hashes"].update({csv_path.name: sha256(csv_path)}))
    elif case == "analysis_snapshot": edit_json(f.analysis, lambda a: a.update(snapshot="other"))
    elif case == "timestamp": edit_json(f.analysis, lambda a: a.update(house_timestamp="other"))
    elif case == "lint": edit_json(f.analysis, lambda a: a["figures"][0].update(lint_passed=False))
    elif case == "duplicate": edit_json(f.analysis, lambda a: a["figures"].append(a["figures"][0].copy()))
    elif case == "path_traversal": edit_json(f.analysis, lambda a: a["figures"][0].update(image="../other.png"))
    elif case == "missing_hash": edit_json(f.analysis, lambda a: a.pop("artifact_hashes"))
    elif case == "portable_path": edit_json(f.manifest, lambda m: m.update(dependencies={"bad": "C:/private/file"}))
    if case == "portable_posix_path":
        edit_json(f.manifest, lambda m: m.update(dependencies={"bad": "/private/file"}))
    if case == "unlisted_collision":
        (f.pub / "01-chart.png").write_bytes(b"unlisted work")
    before = publication_bytes(f.root)
    with pytest.raises((ValueError, KeyError, FileNotFoundError)):
        publisher.publish(f.root, f.run, reviewed=case != "unreviewed")
    assert publication_bytes(f.root) == before


@pytest.mark.parametrize("failure_at", [3, 4])
def test_replacement_failure_rolls_back_existing_and_new_files(publication, monkeypatch, failure_at):
    f = publication
    before = publication_bytes(f.root)
    real_replace = publisher.os.replace
    calls = 0

    def fail_after_changes(source, destination):
        nonlocal calls
        calls += 1
        if calls == failure_at:
            raise OSError("simulated replacement failure")
        return real_replace(source, destination)

    monkeypatch.setattr(publisher.os, "replace", fail_after_changes)
    with pytest.raises(OSError, match="simulated replacement failure"):
        publisher.publish(f.root, f.run, reviewed=True)
    assert calls == failure_at
    assert publication_bytes(f.root) == before


def test_cli_reports_failed_validation_without_changes(publication, monkeypatch, capsys):
    f = publication
    monkeypatch.setattr(publisher, "project_root", lambda: f.root)
    before = publication_bytes(f.root)
    assert publisher.main(["--run", str(f.run)]) == 1
    assert "--reviewed" in capsys.readouterr().err
    assert publication_bytes(f.root) == before
    assert publisher.main(["--run", str(f.run), "--reviewed"]) == 0


@pytest.fixture
def accuracy_publication(publication):
    import shutil
    from matplotlib import get_data_path
    from matplotlib.font_manager import FontProperties
    f = publication
    part = "02_forecast_accuracy"
    notebook = f"notebooks/{part}.ipynb"
    shutil.copyfile(f.root / publisher.NOTEBOOK, f.root / notebook)
    shutil.copyfile(f.run / publisher.NOTEBOOK, f.run / notebook)
    for directory in ("tables", "figures"):
        shutil.copytree(f.run / directory / publisher.PART, f.run / directory / part)
    analysis = f.run / "tables" / part / "analysis-provenance.json"
    font = Path(get_data_path()) / "fonts/ttf/DejaVuSans.ttf"
    symbols = [{"filename": font.name, "family": FontProperties(fname=str(font)).get_name(),
                "sha256": sha256(font), "characters": ["ρ"], "role": "rho_symbol"}]
    edit_json(analysis, lambda a: a.update(editable_source=notebook, settings={"simulation_seed": 20261105},
                                          primary={"n_planned": 15, "n_eligible": 13}, primary_sign_flip={"patterns": 8192},
                                          symbol_fonts=symbols))
    edit_json(f.manifest, lambda m: m["notebooks"].append(
        {"name": f"{part}.ipynb", "status": "succeeded", "code_cells": 1}))
    return f


def test_part_two_promotion_preserves_part_one(accuracy_publication, monkeypatch):
    f = accuracy_publication
    before = publication_bytes(f.root)
    monkeypatch.setattr(publisher, "project_root", lambda: f.root)
    assert publisher.main(["--run", str(f.run), "--reviewed", "--part", "02_forecast_accuracy"]) == 0
    assert publication_bytes(f.root) == before
    p = publisher.read_json(f.root / "figures/02_forecast_accuracy/provenance.json")
    assert p["editable_source"] == "notebooks/02_forecast_accuracy.ipynb"
    assert p["settings"]["simulation_seed"] == 20261105
    # Promoting the default part must likewise preserve the accuracy publication.
    accuracy = {p: p.read_bytes() for p in (f.root / "figures/02_forecast_accuracy").iterdir()}
    publisher.publish(f.root, f.run, reviewed=True)
    assert all(p.read_bytes() == value for p, value in accuracy.items())


@pytest.mark.parametrize("case", ["synthetic", "stale", "lint", "unknown", "rollback",
                                  "missing_symbol", "altered_symbol", "wrong_symbol_character", "wrong_symbol_role",
                                  "wrong_symbol_font"])
def test_part_two_rejections_and_rollback(accuracy_publication, monkeypatch, case):
    f = accuracy_publication
    before = {p.relative_to(f.root): p.read_bytes() for p in f.root.rglob("*") if p.is_file()}
    part = "02_forecast_accuracy"
    if case == "synthetic":
        edit_json(f.manifest, lambda m: m.update(synthetic=True))
    elif case == "stale":
        edit_json(f.manifest, lambda m: m.update(source_hashes={}))
    elif case == "lint":
        edit_json(f.run / "tables" / part / "analysis-provenance.json",
                  lambda a: a["figures"][0].update(lint_passed=False))
    elif case == "unknown":
        part = "04_unknown"
    elif case.startswith("missing_symbol"):
        edit_json(f.run / "tables" / part / "analysis-provenance.json", lambda a: a.pop("symbol_fonts"))
    elif case in ("altered_symbol", "wrong_symbol_character", "wrong_symbol_role", "wrong_symbol_font"):
        key, value = {"altered_symbol": ("sha256", "0" * 64),
                      "wrong_symbol_character": ("characters", ["x"]),
                      "wrong_symbol_role": ("role", "all_text"),
                      "wrong_symbol_font": ("filename", "Other.ttf")}[case]
        edit_json(f.run / "tables" / part / "analysis-provenance.json",
                  lambda a: a["symbol_fonts"][0].update({key: value}))
    else:
        replace = publisher.os.replace
        calls = 0

        def fail(source, destination):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("accuracy rollback")
            return replace(source, destination)
        monkeypatch.setattr(publisher.os, "replace", fail)
    with pytest.raises((ValueError, OSError)):
        publisher.publish(f.root, f.run, reviewed=True, part=part)
    for name, value in before.items():
        if not str(name).startswith("outputs"):
            assert (f.root / name).read_bytes() == value
    assert not any((f.root / "figures/02_forecast_accuracy").glob("*"))


def test_volume_promotion_preserves_previous_parts(accuracy_publication):
    import shutil

    f = accuracy_publication
    publisher.publish(f.root, f.run, reviewed=True, part="02_forecast_accuracy")
    before = {
        p: p.read_bytes() for p in (
            f.root / publisher.NOTEBOOK, f.root / "notebooks/02_forecast_accuracy.ipynb",
            *(f.root / publisher.PUBLICATION).iterdir(),
            *(f.root / "figures/02_forecast_accuracy").iterdir(),
        )
    }
    part = "03_kalshi_trading_volume"
    notebook = f"notebooks/{part}.ipynb"
    shutil.copyfile(f.root / publisher.NOTEBOOK, f.root / notebook)
    shutil.copyfile(f.run / publisher.NOTEBOOK, f.run / notebook)
    for directory in ("tables", "figures"):
        shutil.copytree(f.run / directory / publisher.PART, f.run / directory / part)
    edit_json(f.run / "tables" / part / "analysis-provenance.json",
              lambda a: a.update(editable_source=notebook))
    edit_json(f.manifest, lambda m: m["notebooks"].append(
        {"name": f"{part}.ipynb", "status": "succeeded", "code_cells": 1}))
    assert publisher.publish(f.root, f.run, reviewed=True, part=part) == 4
    assert all(p.read_bytes() == content for p, content in before.items())
    proof = publisher.read_json(f.root / f"figures/{part}/provenance.json")
    assert proof["editable_source"] == notebook
