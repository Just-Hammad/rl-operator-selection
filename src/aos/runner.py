"""Experiment runner: builds the grid, seeds it reproducibly, executes in parallel.

**Seeding.** Every cell's seed is derived from
``SeedSequence([master, algorithm_index, fid, instance, dim, run])``. This is
order-independent and parallelism-independent: cell (ucb, f7, run 12) gets the same
stream whether it runs first, last, or on another machine. Re-running a single cell to
debug it reproduces it exactly. The realised seed is written into the results, because
a config-level seed alone is not reproducibility.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .baselines import run_jade
from .de import DEConfig, run_de
from .problems import BBOB_FIDS, ProblemSpec, TrackedProblem
from .registry import ALGORITHM_NAMES, POLICY_FACTORIES, algorithm_index


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    dims: tuple[int, ...]
    fids: tuple[int, ...]
    instance: int
    runs: int
    budget_multiplier: int
    master_seed: int
    algorithms: tuple[str, ...]
    de: DEConfig

    @staticmethod
    def load(path: str | Path) -> ExperimentConfig:
        raw = yaml.safe_load(Path(path).read_text())
        de = DEConfig(**raw.pop("de", {}))
        algos = tuple(raw.pop("algorithms", ALGORITHM_NAMES))
        unknown = set(algos) - set(ALGORITHM_NAMES)
        if unknown:
            raise ValueError(f"unknown algorithms in config: {sorted(unknown)}")
        return ExperimentConfig(
            name=raw["name"],
            dims=tuple(raw["dims"]),
            fids=tuple(raw.get("fids", BBOB_FIDS)),
            instance=int(raw.get("instance", 1)),
            runs=int(raw["runs"]),
            budget_multiplier=int(raw["budget_multiplier"]),
            master_seed=int(raw["master_seed"]),
            algorithms=algos,
            de=de,
        )

    def budget(self, dim: int) -> int:
        return self.budget_multiplier * dim

    def to_dict(self) -> dict:
        d = asdict(self)
        d["de"] = asdict(self.de)
        return d


@dataclass(frozen=True)
class Task:
    algorithm: str
    fid: int
    instance: int
    dim: int
    run: int
    budget: int


def cell_seed(master: int, algorithm: str, fid: int, instance: int, dim: int, run: int) -> int:
    """Deterministic, order-independent seed for one grid cell."""
    ss = np.random.SeedSequence(
        [master, algorithm_index(algorithm), fid, instance, dim, run]
    )
    return int(ss.generate_state(1, dtype=np.uint64)[0])


_CFG: DEConfig | None = None
_MASTER: int = 0


def _init_worker(de_cfg: dict, master: int) -> None:
    global _CFG, _MASTER
    _CFG = DEConfig(**de_cfg)
    _MASTER = master


def _run_task(task: Task) -> dict:
    assert _CFG is not None
    seed = cell_seed(_MASTER, task.algorithm, task.fid, task.instance, task.dim, task.run)
    rng = np.random.default_rng(seed)
    problem = TrackedProblem(
        ProblemSpec(task.fid, task.instance, task.dim), budget=task.budget
    )
    if task.algorithm == "jade":
        res = run_jade(problem, _CFG, rng)
    else:
        res = run_de(problem, POLICY_FACTORIES[task.algorithm](), _CFG, rng)

    return {
        "algorithm": task.algorithm,
        "fid": task.fid,
        "instance": task.instance,
        "dim": task.dim,
        "run": task.run,
        "seed": seed,
        "best_error": res.best_error,
        "evaluations": res.evaluations,
        "generations": res.generations,
        "wall_time": res.wall_time,
        "_trace": np.asarray(res.trace_error, dtype=np.float64),
        "_trace_evals": np.asarray(res.trace_evals, dtype=np.int64),
        "_sel": res.selection_hist,
        "_suc": res.success_hist,
    }


def build_tasks(cfg: ExperimentConfig) -> list[Task]:
    return [
        Task(alg, fid, cfg.instance, dim, run, cfg.budget(dim))
        for dim in cfg.dims
        for alg in cfg.algorithms
        for fid in cfg.fids
        for run in range(cfg.runs)
    ]


def run_experiment(
    cfg: ExperimentConfig, out_dir: str | Path, workers: int | None = None
) -> pd.DataFrame:
    """Execute the full grid and write results. Returns the per-run table."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tasks = build_tasks(cfg)
    workers = workers or max(1, (os.cpu_count() or 2) - 1)

    print(f"[{cfg.name}] {len(tasks)} runs on {workers} workers", flush=True)
    rows: list[dict] = []
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_worker,
        initargs=(asdict(cfg.de), cfg.master_seed),
    ) as pool:
        for i, row in enumerate(pool.map(_run_task, tasks, chunksize=8), 1):
            rows.append(row)
            if i % 250 == 0 or i == len(tasks):
                print(f"  {i}/{len(tasks)}", flush=True)

    runs = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows])
    runs.index.name = "row_id"
    runs.to_csv(out / "runs.csv")

    # Traces are equal-length within a dimension (same budget -> same geometric grid).
    for dim in cfg.dims:
        idx = [i for i, r in enumerate(rows) if r["dim"] == dim]
        if not idx:
            continue
        np.savez_compressed(
            out / f"traces_d{dim}.npz",
            row_id=np.asarray(idx, dtype=np.int64),
            evals=rows[idx[0]]["_trace_evals"],
            error=np.vstack([rows[i]["_trace"] for i in idx]),
        )

    pol = [i for i, r in enumerate(rows) if r["_sel"] is not None]
    if pol:
        np.savez_compressed(
            out / "selection.npz",
            row_id=np.asarray(pol, dtype=np.int64),
            selection=np.stack([rows[i]["_sel"] for i in pol]),
            success=np.stack([rows[i]["_suc"] for i in pol]),
        )

    (out / "config.used.yaml").write_text(yaml.safe_dump(cfg.to_dict(), sort_keys=False))
    print(f"[{cfg.name}] wrote {out}/runs.csv ({len(runs)} rows)", flush=True)
    return runs
