"""Promote one reviewed scorecard run into the release publication."""
import argparse
import csv
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import sys
import tempfile

import nbformat
from PIL import Image

from congress_scorecard.data import load_inputs, project_root, sha256
from congress_scorecard.plotting import source_colors

PART = "01_congress_scorecard"
NOTEBOOK = f"notebooks/{PART}.ipynb"
PUBLICATION = f"figures/{PART}"
PARTS = (PART, "02_forecast_accuracy")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def figure_names(records):
    names = []
    require(bool(records), "No figures listed")
    for record in records:
        image, data = record["image"], record["data"]
        require(Path(image).name == image and Path(data).name == data,
                "Figure records must use portable basenames")
        require(image.endswith(".png") and data == f"plot_{Path(image).stem}.csv",
                "Invalid figure/data pairing")
        names.extend((image, data))
    require(len(names) == len(set(names)), "Duplicate figure artifacts")
    return set(names)


def source_hashes(root):
    paths = [*root.glob("src/congress_scorecard/*.py"),
             *root.glob("scripts/*.py"), root / "pyproject.toml"]
    return {p.relative_to(root).as_posix(): sha256(p) for p in paths}


def prepare_publication(root, run, *, part=PART):
    require(part in PARTS, "Unsupported publication part")
    notebook_name = f"notebooks/{part}.ipynb"
    publication = f"figures/{part}"
    manifest = read_json(run / "run.json")
    require(manifest["status"] == "succeeded", "Run did not succeed")
    require(manifest["synthetic"] is False, "Synthetic runs cannot be published")
    inputs = load_inputs(snapshot=manifest["snapshot"])
    require(inputs.manifest["synthetic"] is False, "Selected inputs are synthetic")
    require(manifest["snapshot"] == inputs.snapshot_id, "Snapshot mismatch")
    require(manifest["snapshot_manifest"] == inputs.manifest, "Snapshot manifest mismatch")
    require(manifest["input_hashes"] == inputs.hashes, "Stale input hashes")
    for name, digest in inputs.hashes.items():
        require(sha256(root / name) == digest, f"Input changed: {name}")
    require(manifest["source_hashes"] == source_hashes(root), "Stale source hashes; rerun first")
    records = [r for r in manifest["notebooks"] if r["name"] == f"{part}.ipynb"]
    require(len(records) == 1 and records[0]["status"] == "succeeded",
            "Successful scorecard notebook missing")
    notebook_path = run / notebook_name
    notebook = nbformat.read(notebook_path, as_version=4)
    nbformat.validate(notebook)
    current = nbformat.read(root / notebook_name, as_version=4)
    require([(c.cell_type, c.source) for c in notebook.cells] ==
            [(c.cell_type, c.source) for c in current.cells], "Notebook source changed; rerun first")
    code = [c for c in notebook.cells if c.cell_type == "code" and c.source.strip()]
    require(bool(code) and len(code) == records[0]["code_cells"], "Notebook code count mismatch")
    require(all(isinstance(c.execution_count, int) and c.execution_count > 0 for c in code),
            "Notebook contains unexecuted code")
    require(not any(o.output_type == "error" for c in code for o in c.outputs),
            "Notebook contains error outputs")
    analysis = read_json(run / f"tables/{part}/analysis-provenance.json")
    require(analysis["snapshot"] == inputs.snapshot_id and analysis["synthetic"] is False,
            "Analysis snapshot mismatch")
    require(analysis["input_hashes"] == inputs.hashes, "Analysis input mismatch")
    require(analysis["graphics_assets"] == manifest["graphics_assets"], "Graphics asset mismatch")
    require(analysis["editable_source"] == notebook_name, "Unexpected editable source")
    for chamber in ("senate", "house"):
        key = f"{chamber}_timestamp"
        require(analysis[key] == inputs.manifest[key], f"{chamber} timestamp mismatch")
    figures = analysis["figures"]
    names = figure_names(figures)
    require(all(r["lint_passed"] is True for r in figures), "A chart did not pass lint")
    require(set(analysis["artifact_hashes"]) == names, "Artifact hash list mismatch")
    files = {notebook_name: notebook_path.read_bytes()}
    for name in sorted(names):
        directory = "figures" if name.endswith(".png") else "tables"
        path = run / directory / part / name
        require(sha256(path) == analysis["artifact_hashes"][name], f"Artifact changed: {name}")
        if directory == "figures":
            with Image.open(path) as image:
                require(image.format == "PNG" and image.size == (1920, 1080),
                        f"Unexpected image format or dimensions: {name}")
                image.verify()
        else:
            reader = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")))
            require({"snapshot", "synthetic"} <= set(reader.fieldnames or []),
                    f"CSV snapshot columns missing: {name}")
            for row in reader:
                require(row["snapshot"] == inputs.snapshot_id and row["synthetic"] == "False",
                        f"CSV snapshot mismatch: {name}")
        files[f"{publication}/{name}"] = path.read_bytes()
    provenance = {
        "snapshot": inputs.snapshot_id, "synthetic": False,
        "structural_baseline": "29d4965", "run_id": run.name,
        "review": {"numerical_and_visual_review_confirmed": True,
                   "method": "Explicit --reviewed operator attestation; not automated visual approval"},
        "senate_timestamp": analysis["senate_timestamp"],
        "house_timestamp": analysis["house_timestamp"],
        "snapshot_manifest": inputs.manifest, "input_hashes": inputs.hashes,
        "qualifications": inputs.diagnostics["qualifications"],
        "source_colors": source_colors(), "neutral_color": "#80C2FC", "highlight_color": "#EEEAAC",
        "graphics_assets": manifest["graphics_assets"], "source_hashes": manifest["source_hashes"],
        "dependencies": manifest["dependencies"], "editable_source": notebook_name,
        "notebook_sha256": sha256(notebook_path), "figures": figures,
        "artifact_hashes": analysis["artifact_hashes"],
    }
    if part == "02_forecast_accuracy":
        provenance["settings"] = analysis["settings"]
        provenance["primary"] = analysis["primary"]
        provenance["primary_sign_flip"] = analysis["primary_sign_flip"]
        symbols = analysis.get("symbol_fonts")
        from matplotlib import get_data_path
        from matplotlib.font_manager import FontProperties
        symbol_path = Path(get_data_path()) / "fonts/ttf/DejaVuSans.ttf"
        expected = [{"filename": symbol_path.name,
                     "family": FontProperties(fname=str(symbol_path)).get_name(),
                     "sha256": sha256(symbol_path), "characters": ["ρ"], "role": "rho_symbol"}]
        require(symbols == expected, "Unexpected symbol font provenance")
        provenance["symbol_fonts"] = symbols
    # Omit machine-specific execution fields; every published reference is portable.
    portable = json.dumps(provenance, indent=2, ensure_ascii=False) + "\n"
    def local_path(value):
        if isinstance(value, dict):
            return any(local_path(v) for v in value.values())
        if isinstance(value, list):
            return any(local_path(v) for v in value)
        return isinstance(value, str) and (
            PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()
        )

    require(not local_path(provenance), "Provenance contains a machine-specific path")
    files[f"{publication}/provenance.json"] = portable.encode("utf-8")
    return files


def publish(root, run, *, reviewed=False, part=PART):
    require(part in PARTS, "Unsupported publication part")
    publication = f"figures/{part}"
    require(reviewed, "Pass --reviewed only after numerical and visual review")
    root, run = Path(root).resolve(), Path(run).resolve()
    files = prepare_publication(root, run, part=part)
    previous_path = root / publication / "provenance.json"
    previous_names = figure_names(read_json(previous_path)["figures"]) if previous_path.exists() else set()
    obsolete = {f"{publication}/{name}" for name in previous_names} - files.keys()
    for name in files:
        if name.startswith(publication + "/") and name != f"{publication}/provenance.json":
            require(not (root / name).exists() or Path(name).name in previous_names,
                    f"Publication would overwrite an unlisted file: {name}")
    affected = sorted(files.keys() | obsolete)
    scratch = root.parent / "_scratch" / ("part-2" if part == PART else "part-3")
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="publish-", dir=scratch) as temporary:
        staging = Path(temporary) / "staging"
        backups = Path(temporary) / "backups"
        existed = set()
        for name in affected:
            destination = root / name
            if destination.exists():
                backup = backups / name
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(destination, backup)
                existed.add(name)
            if name in files:
                staged = staging / name
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_bytes(files[name])
        touched = []
        try:
            for name in affected:
                destination = root / name
                # Identical artifacts need no replacement (including open image previews).
                if name in files and destination.exists() and destination.read_bytes() == files[name]:
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                touched.append(name)
                if name in files:
                    os.replace(staging / name, destination)
                elif destination.exists():
                    destination.unlink()
        except Exception:
            for name in reversed(touched):
                destination = root / name
                if name in existed:
                    shutil.copyfile(backups / name, destination)
                elif destination.exists():
                    destination.unlink()
            raise
    return len(files)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="One completed outputs/<snapshot>/<run-id> directory")
    parser.add_argument("--part", choices=PARTS, default=PART, help="Notebook publication to promote")
    parser.add_argument("--reviewed", action="store_true", help="Confirm numerical and visual review is complete")
    args = parser.parse_args(argv)
    try:
        count = publish(project_root(), args.run, reviewed=args.reviewed, part=args.part)
    except Exception as error:
        print(f"PUBLICATION FAILED: {error}", file=sys.stderr)
        return 1
    print(f"PUBLISHED: {args.run.name} ({count} files; reviewed attestation recorded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
