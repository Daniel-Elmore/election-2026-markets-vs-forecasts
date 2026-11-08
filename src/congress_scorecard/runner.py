"""Sequential fresh-kernel execution with per-run manifests and diagnostics."""
import asyncio
import os
from pathlib import Path
import sys
import traceback

from .data import load_inputs, project_root, sha256
from .runtime import new_run_directory, run_metadata, write_manifest

NOTEBOOKS = ("01_congress_scorecard.ipynb", "02_forecast_accuracy.ipynb", "03_kalshi_trading_volume.ipynb")


class NotebookRunError(RuntimeError):
    def __init__(self, run_dir, message):
        self.run_dir = run_dir
        super().__init__(f"{message}. Diagnostics: {run_dir}")


def execute_notebooks(*, snapshot, notebooks=None, output_root=None, timeout=600):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    import nbformat
    from nbclient import NotebookClient

    inputs = load_inputs(snapshot=snapshot)
    paths = [Path(p).resolve() for p in notebooks] if notebooks is not None else [
        project_root() / "notebooks" / name for name in NOTEBOOKS]
    if not paths or len({p.name for p in paths}) != len(paths):
        raise ValueError("Supply at least one notebook with unique output names")
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Notebook missing: {path}")
    prepared = [(path, nbformat.read(path, as_version=4)) for path in paths]
    directory = new_run_directory(inputs.snapshot_id, output_root)
    (directory / "notebooks").mkdir()
    (directory / "logs").mkdir()
    metadata = run_metadata(inputs) | {"status": "running", "notebooks": []}
    write_manifest(directory / "run.json", metadata)
    environment = dict(os.environ, CONGRESS_SCORECARD_SNAPSHOT=inputs.snapshot_id,
                       CONGRESS_SCORECARD_OUTPUT_DIR=str(directory))
    # Kernels and their temporary connection files stay inside Part 1 scratch.
    scratch = project_root().parent / "_scratch" / "part-1" / "jupyter"
    scratch.mkdir(parents=True, exist_ok=True)
    environment.update(TEMP=str(scratch), TMP=str(scratch), JUPYTER_PLATFORM_DIRS="1",
                       JUPYTER_RUNTIME_DIR=str(scratch))
    for path, notebook in prepared:
        code_count = sum(cell.cell_type == "code" and bool(cell.source.strip()) for cell in notebook.cells)
        record = {"name": path.name, "sha256": sha256(path), "code_cells": code_count,
                  "implementation": "analysis_present" if code_count else "outline_only", "status": "running"}
        metadata["notebooks"].append(record)
        write_manifest(directory / "run.json", metadata)
        client = NotebookClient(notebook, timeout=timeout, kernel_name="python3", allow_errors=False,
                                resources={"metadata": {"path": str(project_root())}})
        try:
            manager = client.create_kernel_manager()
            # Use the current Python interpreter, independent of the default
            # system kernelspec's Python installation.
            manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
            with (directory / "logs" / f"{path.stem}.kernel.txt").open("w", encoding="utf-8") as kernel_log:
                client.execute(env=environment, stdout=kernel_log, stderr=kernel_log)
            record["status"] = "succeeded"
        except Exception as error:
            record["status"] = "failed"
            record["error"] = str(error)
            metadata["status"] = "failed"
            (directory / "logs" / f"{path.stem}.error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            raise NotebookRunError(directory, f"Notebook failed: {path.name}") from error
        finally:
            nbformat.write(notebook, directory / "notebooks" / path.name)
            cell_output = []
            for cell in notebook.cells:
                for output in cell.get("outputs", []):
                    cell_output.append(output.get("text", output.get("ename", "")))
            (directory / "logs" / f"{path.stem}.txt").write_text("\n".join(cell_output), encoding="utf-8")
            write_manifest(directory / "run.json", metadata)
    metadata["status"] = "succeeded"
    metadata["integration_status"] = "outlines_only" if all(r["code_cells"] == 0 for r in metadata["notebooks"]) else "executed"
    write_manifest(directory / "run.json", metadata)
    return directory
