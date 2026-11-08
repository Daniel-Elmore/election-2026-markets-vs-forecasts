"""Snapshot selection shared by independent notebooks and the batch runner."""
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import uuid

from .data import Inputs, load_inputs, project_root


def dependency_versions():
    names = ("congress-scorecard", "numpy", "pandas", "nbclient", "nbformat", "ipykernel",
             "matplotlib", "Pillow")
    versions = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def new_run_directory(snapshot_id, output_root=None):
    root = Path(output_root).resolve() if output_root else project_root() / "outputs"
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    directory = root / snapshot_id / identifier
    directory.mkdir(parents=True, exist_ok=False)
    return directory


def write_manifest(path, manifest):
    # Replace only this run's manifest. Prior runs have their own unique directories.
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_metadata(inputs):
    root = project_root()
    from .data import sha256
    from .plotting import graphics_assets
    source_files = [*root.glob("src/congress_scorecard/*.py"), *root.glob("scripts/*.py"), root / "pyproject.toml"]
    return {
        "snapshot": inputs.snapshot_id, "synthetic": inputs.manifest["synthetic"],
        "input_hashes": inputs.hashes, "snapshot_manifest": inputs.manifest,
        "source_hashes": {str(p.relative_to(root)).replace("\\", "/"): sha256(p) for p in source_files},
        "dependencies": dependency_versions(), "diagnostics": inputs.diagnostics,
        "graphics_assets": graphics_assets(),
        "python_executable": __import__("sys").executable,
    }


@dataclass
class NotebookContext:
    inputs: Inputs
    output_dir: Path
    figures_dir: Path
    tables_dir: Path


def load_context(part, *, snapshot=None, output_dir=None):
    if part not in ("01_congress_scorecard", "02_forecast_accuracy", "03_kalshi_trading_volume"):
        raise ValueError("Unknown notebook part identifier")
    inputs = load_inputs(snapshot=snapshot)
    selected_output = output_dir or os.environ.get("CONGRESS_SCORECARD_OUTPUT_DIR")
    directory = Path(selected_output).resolve() if selected_output else new_run_directory(inputs.snapshot_id)
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "run.json"
    if manifest_path.exists():
        from .data import read_json
        existing = read_json(manifest_path)
        if existing["snapshot"] != inputs.snapshot_id or existing["input_hashes"] != inputs.hashes:
            raise ValueError("Output directory belongs to different snapshot inputs")
    else:
        write_manifest(manifest_path, run_metadata(inputs) | {"status": "independent_notebook"})
    figures = directory / "figures" / part
    tables = directory / "tables" / part
    figures.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    return NotebookContext(inputs, directory, figures, tables)
