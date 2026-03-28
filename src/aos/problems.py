"""BBOB problem adapter.

Wraps an ``ioh`` BBOB problem with three things the raw problem does not give us:

1. a **hard** evaluation budget -- overspending is impossible, not merely discouraged
2. a best-so-far trace on a geometric grid, for convergence and ECDF plots
3. target error (``f - f_opt``) rather than raw fitness, so results are comparable
   across functions

The budget is enforced by raising, not by returning ``inf``. A silently inflated
budget is the single easiest way to manufacture a win, so the failure is made loud.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from ioh import ProblemClass, get_problem

#: BBOB's own convention: target error below this counts as solved. Also the floor
#: for log-scale plotting, since exact zeros cannot be drawn on a log axis.
PRECISION_FLOOR: float = 1e-8

#: The 24 noiseless BBOB functions.
BBOB_FIDS: tuple[int, ...] = tuple(range(1, 25))


class BudgetExhausted(Exception):
    """Raised when an evaluation is attempted past the budget."""


@dataclass(frozen=True)
class ProblemSpec:
    fid: int
    instance: int
    dim: int

    @property
    def key(self) -> str:
        return f"f{self.fid:02d}_i{self.instance}_d{self.dim}"


def _geometric_grid(budget: int, n_points: int) -> np.ndarray:
    """Evaluation indices to record at, geometrically spaced.

    Geometric rather than linear because convergence is read on a log-x axis; a
    linear grid spends almost all its points on the flat tail.
    """
    pts = np.unique(
        np.geomspace(1, budget, num=n_points).round().astype(np.int64)
    )
    return pts


class TrackedProblem:
    """A BBOB function with a hard budget and a best-so-far trace."""

    def __init__(self, spec: ProblemSpec, budget: int, n_trace_points: int = 200):
        self.spec = spec
        self.budget = int(budget)
        self._p = get_problem(spec.fid, spec.instance, spec.dim, ProblemClass.BBOB)
        self._fopt = float(self._p.optimum.y)
        self.lb = np.asarray(self._p.bounds.lb, dtype=float)
        self.ub = np.asarray(self._p.bounds.ub, dtype=float)
        self.dim = spec.dim

        self._grid = _geometric_grid(self.budget, n_trace_points)
        self._grid_pos = 0
        self.evaluations = 0
        self.best_error = np.inf
        self.trace_evals: list[int] = []
        self.trace_error: list[float] = []

    def __call__(self, x: np.ndarray) -> float:
        if self.evaluations >= self.budget:
            raise BudgetExhausted(
                f"{self.spec.key}: budget {self.budget} exhausted"
            )
        y = float(self._p(np.asarray(x, dtype=float)))
        self.evaluations += 1
        err = max(y - self._fopt, 0.0)  # BBOB f_opt is exact; negatives are float noise
        if err < self.best_error:
            self.best_error = err
        while (
            self._grid_pos < len(self._grid)
            and self._grid[self._grid_pos] <= self.evaluations
        ):
            self.trace_evals.append(int(self._grid[self._grid_pos]))
            self.trace_error.append(self.best_error)
            self._grid_pos += 1
        return y

    @property
    def exhausted(self) -> bool:
        return self.evaluations >= self.budget

    @property
    def remaining(self) -> int:
        return max(0, self.budget - self.evaluations)

    def finalise(self) -> None:
        """Pad the trace to the full grid.

        A run that converges and stops early still needs a full-length trace, or the
        ECDF silently treats "finished" as "missing".
        """
        while self._grid_pos < len(self._grid):
            self.trace_evals.append(int(self._grid[self._grid_pos]))
            self.trace_error.append(self.best_error)
            self._grid_pos += 1


def default_suite(dim: int, instance: int = 1) -> list[ProblemSpec]:
    """All 24 noiseless BBOB functions at one dimension and instance."""
    return [ProblemSpec(fid=f, instance=instance, dim=dim) for f in BBOB_FIDS]
