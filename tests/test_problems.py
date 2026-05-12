import numpy as np
import pytest

from aos.problems import BudgetExhausted, ProblemSpec, TrackedProblem


def test_budget_is_hard():
    p = TrackedProblem(ProblemSpec(1, 1, 5), budget=100)
    rng = np.random.default_rng(0)
    n = 0
    with pytest.raises(BudgetExhausted):
        while True:
            p(rng.uniform(p.lb, p.ub))
            n += 1
    assert n == 100
    assert p.evaluations == 100
    assert p.exhausted


def test_best_error_non_negative_and_monotone():
    p = TrackedProblem(ProblemSpec(8, 1, 5), budget=500)
    rng = np.random.default_rng(0)
    prev = np.inf
    for _ in range(500):
        p(rng.uniform(p.lb, p.ub))
        assert p.best_error >= 0.0
        assert p.best_error <= prev
        prev = p.best_error


def test_trace_is_monotone_and_padded():
    p = TrackedProblem(ProblemSpec(1, 1, 5), budget=2000, n_trace_points=50)
    rng = np.random.default_rng(0)
    for _ in range(20):  # stop far short of the budget
        p(rng.uniform(p.lb, p.ub))
    p.finalise()
    assert len(p.trace_error) == len(p.trace_evals)
    assert p.trace_evals[-1] == 2000, "finalise must pad to the full grid"
    assert all(a >= b for a, b in zip(p.trace_error, p.trace_error[1:]))


def test_remaining_counts_down():
    p = TrackedProblem(ProblemSpec(1, 1, 5), budget=10)
    assert p.remaining == 10
    p(np.zeros(5))
    assert p.remaining == 9


def test_error_is_relative_to_known_optimum():
    """BBOB gives f_opt exactly, so target error at the optimum is ~0."""
    p = TrackedProblem(ProblemSpec(1, 1, 5), budget=10)
    p(np.asarray(p._p.optimum.x))
    assert p.best_error < 1e-8
