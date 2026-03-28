"""JADE -- a published adaptive DE, used as the external reference point.

Zhang & Sanderson (2009), "JADE: Adaptive Differential Evolution With Optional
External Archive", IEEE TEC 13(5).

This is *not* an operator-selection method: JADE uses a single mutation strategy
(current-to-pbest/1) and adapts F and CR instead. It is here because a comparison
restricted to variants of our own DE cannot say whether any of them is actually
competitive -- omitting a real published algorithm is how weak studies manufacture
wins. Where JADE beats every AOS variant, the honest reading is that parameter
adaptation matters more than operator selection on this suite.
"""

from __future__ import annotations

import time

import numpy as np

from .de import DEConfig, RunResult
from .operators import binomial_crossover, repair_midpoint
from .problems import BudgetExhausted, TrackedProblem


def _lehmer_mean(x: np.ndarray) -> float:
    """sum(x^2)/sum(x) -- JADE's specified mean for successful F values."""
    s = x.sum()
    return float((x**2).sum() / s) if s > 0 else 0.0


def run_jade(
    problem: TrackedProblem,
    cfg: DEConfig,
    rng: np.random.Generator,
    c: float = 0.1,
    p: float = 0.05,
) -> RunResult:
    """JADE with the optional external archive enabled."""
    t0 = time.perf_counter()
    d, lb, ub = problem.dim, problem.lb, problem.ub
    NP = cfg.NP

    pop = rng.uniform(lb, ub, size=(NP, d))
    fit = np.full(NP, np.inf)
    archive: list[np.ndarray] = []
    mu_CR, mu_F = 0.5, 0.5
    generations = 0

    try:
        for i in range(NP):
            fit[i] = problem(pop[i])

        while True:
            generations += 1
            S_CR: list[float] = []
            S_F: list[float] = []
            gen_pop, gen_fit = pop.copy(), fit.copy()
            order = np.argsort(gen_fit, kind="stable")
            top = max(1, int(np.ceil(p * NP)))
            pool = np.vstack([gen_pop, np.asarray(archive)]) if archive else gen_pop
            pending: list[tuple[int, np.ndarray, float]] = []

            for i in range(NP):
                CR_i = float(np.clip(rng.normal(mu_CR, 0.1), 0.0, 1.0))
                F_i = 0.0
                while F_i <= 0.0:  # JADE: redraw non-positive F, truncate above at 1
                    F_i = float(rng.standard_cauchy() * 0.1 + mu_F)
                F_i = min(F_i, 1.0)

                pbest = order[rng.integers(top)]
                r1 = int(rng.integers(NP))
                while r1 == i:
                    r1 = int(rng.integers(NP))
                # Exclusion applies to the population part of P u A only; an archive
                # entry sitting at index i or r1 is a different vector and is admissible.
                r2 = int(rng.integers(len(pool)))
                while r2 < NP and (r2 == i or r2 == r1):
                    r2 = int(rng.integers(len(pool)))

                x = gen_pop[i]
                v = x + F_i * (gen_pop[pbest] - x) + F_i * (gen_pop[r1] - pool[r2])
                u = repair_midpoint(binomial_crossover(x, v, CR_i, rng), x, lb, ub)

                f_u = problem(u)
                if f_u <= gen_fit[i]:
                    pending.append((i, u, f_u))
                    S_CR.append(CR_i)
                    S_F.append(F_i)

            for i, u, f_u in pending:
                archive.append(pop[i].copy())
                pop[i], fit[i] = u, f_u
            if len(archive) > NP:
                keep = rng.choice(len(archive), size=NP, replace=False)
                archive = [archive[j] for j in keep]

            if S_CR:
                mu_CR = (1 - c) * mu_CR + c * float(np.mean(S_CR))
                mu_F = (1 - c) * mu_F + c * _lehmer_mean(np.asarray(S_F))

    except BudgetExhausted:
        pass

    problem.finalise()
    return RunResult(
        best_error=float(problem.best_error),
        evaluations=problem.evaluations,
        wall_time=time.perf_counter() - t0,
        generations=generations,
        trace_evals=list(problem.trace_evals),
        trace_error=list(problem.trace_error),
    )
