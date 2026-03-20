"""Credit assignment: turning a fitness improvement into a bandit reward.

Two decisions live here, and the AOS literature disagrees about both:

1. **What counts as credit** for a single application of an operator.
2. **How credits are aggregated** over recent history into the value the selection
   policy actually sees.

Fialho et al. found that *extreme* aggregation (the best recent outcome) dominates
*average* aggregation, because rare large improvements matter more than frequent
small ones. Extreme is the default here; average is kept so the claim is testable
rather than inherited.
"""

from __future__ import annotations

from collections import deque

import numpy as np

CREDIT_SCHEMES = ("improvement", "relative", "binary")
AGGREGATIONS = ("extreme", "average", "sum")

_EPS = 1e-30


def raw_credit(f_parent: float, f_child: float, scheme: str = "improvement") -> float:
    """Credit for one operator application. Minimisation: lower fitness is better.

    Always non-negative -- a failed application earns zero, never a penalty. Negative
    rewards break the [0, 1] normalisation that UCB's confidence term assumes.
    """
    delta = f_parent - f_child
    if scheme == "improvement":
        return max(0.0, delta)
    if scheme == "relative":
        return max(0.0, delta / (abs(f_parent) + _EPS))
    if scheme == "binary":
        return 1.0 if delta > 0.0 else 0.0
    raise ValueError(f"unknown credit scheme {scheme!r}; expected one of {CREDIT_SCHEMES}")


class CreditWindow:
    """Sliding window of recent (operator, credit) pairs.

    A *global* window of the last W applications, not W per operator. This is the
    formulation that makes the bandit non-stationary in the right way: an operator
    that stops being chosen also stops being credited, and its value decays out of
    the window rather than being frozen at its historical best.
    """

    def __init__(self, n_operators: int, window: int = 50, aggregate: str = "extreme"):
        if aggregate not in AGGREGATIONS:
            raise ValueError(f"unknown aggregation {aggregate!r}; expected {AGGREGATIONS}")
        self.n = n_operators
        self.window = int(window)
        self.aggregate = aggregate
        self._buf: deque[tuple[int, float]] = deque(maxlen=self.window)

    def push(self, k: int, credit: float) -> None:
        self._buf.append((int(k), float(credit)))

    def counts(self) -> np.ndarray:
        """Applications of each operator currently inside the window."""
        c = np.zeros(self.n, dtype=np.int64)
        for k, _ in self._buf:
            c[k] += 1
        return c

    def values(self) -> np.ndarray:
        """Aggregated credit per operator over the window. Zero if never applied."""
        buckets: list[list[float]] = [[] for _ in range(self.n)]
        for k, c in self._buf:
            buckets[k].append(c)
        out = np.zeros(self.n, dtype=float)
        for k, vals in enumerate(buckets):
            if not vals:
                continue
            if self.aggregate == "extreme":
                out[k] = max(vals)
            elif self.aggregate == "average":
                out[k] = sum(vals) / len(vals)
            else:
                out[k] = sum(vals)
        return out

    def normalised_values(self) -> np.ndarray:
        """Aggregated credit rescaled to [0, 1] by the current maximum.

        Rescaling is per-decision rather than global because fitness improvements
        shrink by orders of magnitude over a run; a fixed scale would make the
        exploration term dominate completely in late generations.
        """
        v = self.values()
        top = v.max()
        return v / top if top > 0 else v

    def __len__(self) -> int:
        return len(self._buf)
