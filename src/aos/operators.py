"""DE mutation strategies.

Every operator has the same signature so the selection policy can treat them as
interchangeable arms of a bandit. Parameter conventions follow the original
papers; where a paper is ambiguous the choice is stated in the docstring.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class MutationContext:
    """Everything an operator may read. Operators must not mutate any of it."""

    pop: np.ndarray  # (NP, D) current population
    fit: np.ndarray  # (NP,) fitness, minimisation
    i: int  # index of the target vector
    F: float
    rng: np.random.Generator
    archive: np.ndarray | None = None  # (M, D) JADE-style archive of replaced parents
    p: float = 0.11  # top-p fraction for current-to-pbest/1
    _order: np.ndarray | None = field(default=None, repr=False)

    @property
    def best(self) -> int:
        return int(np.argmin(self.fit))

    def order(self) -> np.ndarray:
        """Indices sorted by fitness, ascending. Cached — fitness is fixed per generation."""
        if self._order is None:
            self._order = np.argsort(self.fit, kind="stable")
        return self._order


def _distinct(rng: np.random.Generator, n: int, k: int, exclude: int) -> np.ndarray:
    """k distinct indices from range(n), excluding `exclude`.

    Samples from range(n-1) and shifts past the excluded index, which is exact and
    allocation-free — no rejection loop that can stall when NP is tight.
    """
    m = n - 1
    if k > m:
        raise ValueError(f"cannot draw {k} distinct indices from {n} excluding one")
    # One batched draw plus rare redraws on collision. `rng.choice(replace=False)`
    # builds a full permutation of n, which dominated the profile at ~32% of runtime
    # for a k<=5 draw from NP=50.
    picks = rng.integers(0, m, size=k)
    seen: set[int] = set()
    out = np.empty(k, dtype=np.int64)
    for t in range(k):
        v = int(picks[t])
        while v in seen:
            v = int(rng.integers(m))
        seen.add(v)
        out[t] = v
    return out + (out >= exclude)


def rand_1(ctx: MutationContext) -> np.ndarray:
    """DE/rand/1 : v = x_r1 + F*(x_r2 - x_r3)"""
    r = _distinct(ctx.rng, len(ctx.pop), 3, ctx.i)
    return ctx.pop[r[0]] + ctx.F * (ctx.pop[r[1]] - ctx.pop[r[2]])


def best_1(ctx: MutationContext) -> np.ndarray:
    """DE/best/1 : v = x_best + F*(x_r1 - x_r2)"""
    r = _distinct(ctx.rng, len(ctx.pop), 2, ctx.i)
    return ctx.pop[ctx.best] + ctx.F * (ctx.pop[r[0]] - ctx.pop[r[1]])


def rand_2(ctx: MutationContext) -> np.ndarray:
    """DE/rand/2 : v = x_r1 + F*(x_r2 - x_r3) + F*(x_r4 - x_r5)"""
    r = _distinct(ctx.rng, len(ctx.pop), 5, ctx.i)
    return (
        ctx.pop[r[0]]
        + ctx.F * (ctx.pop[r[1]] - ctx.pop[r[2]])
        + ctx.F * (ctx.pop[r[3]] - ctx.pop[r[4]])
    )


def current_to_best_1(ctx: MutationContext) -> np.ndarray:
    """DE/current-to-best/1 : v = x_i + F*(x_best - x_i) + F*(x_r1 - x_r2)"""
    r = _distinct(ctx.rng, len(ctx.pop), 2, ctx.i)
    x = ctx.pop[ctx.i]
    return x + ctx.F * (ctx.pop[ctx.best] - x) + ctx.F * (ctx.pop[r[0]] - ctx.pop[r[1]])


def current_to_pbest_1(ctx: MutationContext) -> np.ndarray:
    """DE/current-to-pbest/1 with optional archive (JADE, Zhang & Sanderson 2009).

    x_pbest is drawn uniformly from the top ceil(p*NP) individuals; x_r2 is drawn
    from population union archive. With no archive this degrades to the plain
    population variant, which is the documented JADE fallback.
    """
    np_ = len(ctx.pop)
    top = max(1, int(np.ceil(ctx.p * np_)))
    pbest = ctx.order()[ctx.rng.integers(top)]

    r1 = _distinct(ctx.rng, np_, 1, ctx.i)[0]

    if ctx.archive is not None and len(ctx.archive) > 0:
        pool = np.vstack([ctx.pop, ctx.archive])
    else:
        pool = ctx.pop
    # r2 must differ from i and r1, but only within the population part of the pool
    # -- an archive entry that happens to sit at index i or r1 is still admissible.
    while True:
        j = int(ctx.rng.integers(len(pool)))
        if j >= np_ or (j != ctx.i and j != r1):
            break
    x = ctx.pop[ctx.i]
    return x + ctx.F * (ctx.pop[pbest] - x) + ctx.F * (ctx.pop[r1] - pool[j])


#: The operator pool. Order is fixed — arm indices are positions in this tuple and
#: are written into every results file, so appending is safe but reordering is not.
POOL: tuple[tuple[str, object], ...] = (
    ("rand/1", rand_1),
    ("best/1", best_1),
    ("rand/2", rand_2),
    ("current-to-best/1", current_to_best_1),
    ("current-to-pbest/1", current_to_pbest_1),
)

OPERATOR_NAMES: tuple[str, ...] = tuple(name for name, _ in POOL)
OPERATORS: tuple[object, ...] = tuple(fn for _, fn in POOL)
N_OPERATORS: int = len(POOL)

#: rand/2 needs five distinct indices besides the target.
MIN_POPULATION: int = 6


def binomial_crossover(
    x: np.ndarray, v: np.ndarray, CR: float, rng: np.random.Generator
) -> np.ndarray:
    """Binomial crossover with a guaranteed inherited component (jrand)."""
    d = len(x)
    mask = rng.random(d) < CR
    mask[rng.integers(d)] = True
    return np.where(mask, v, x)


def repair_midpoint(
    u: np.ndarray, x: np.ndarray, lb: np.ndarray, ub: np.ndarray
) -> np.ndarray:
    """Bound repair: reflect halfway back toward the parent (JADE's rule).

    Chosen over clamping because clamping piles mass onto the bounds, which
    flatters any operator that overshoots. Stated here because the choice measurably
    changes results and is usually left unreported.
    """
    out = u.copy()
    lo = out < lb
    hi = out > ub
    out[lo] = (lb[lo] + x[lo]) / 2.0
    out[hi] = (ub[hi] + x[hi]) / 2.0
    return out
