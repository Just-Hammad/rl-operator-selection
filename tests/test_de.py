import numpy as np
import pytest

from aos.baselines import run_jade
from aos.de import DEConfig, run_de
from aos.operators import N_OPERATORS
from aos.policies import Fixed, Uniform
from aos.problems import ProblemSpec, TrackedProblem
from aos.registry import POLICY_FACTORIES

CFG = DEConfig()


def _problem(fid=1, dim=5, budget=3000):
    return TrackedProblem(ProblemSpec(fid, 1, dim), budget=budget)


@pytest.mark.parametrize("alg", sorted(POLICY_FACTORIES))
def test_budget_never_exceeded(alg):
    """Silent budget inflation is the easiest way to manufacture a win."""
    p = _problem(budget=1234)
    r = run_de(p, POLICY_FACTORIES[alg](), CFG, np.random.default_rng(0))
    assert r.evaluations == 1234
    assert p.evaluations <= p.budget


def test_jade_respects_budget():
    p = _problem(budget=1234)
    r = run_jade(p, CFG, np.random.default_rng(0))
    assert r.evaluations == 1234


def test_same_seed_reproduces_exactly():
    out = [
        run_de(_problem(), Uniform(N_OPERATORS), CFG, np.random.default_rng(42)).best_error
        for _ in range(2)
    ]
    assert out[0] == out[1]


def test_different_seeds_differ():
    a = run_de(_problem(), Uniform(N_OPERATORS), CFG, np.random.default_rng(1)).best_error
    b = run_de(_problem(), Uniform(N_OPERATORS), CFG, np.random.default_rng(2)).best_error
    assert a != b


def test_selection_histogram_accounts_for_every_trial():
    """Every evaluation after the initial population is one operator application."""
    budget = 3000
    r = run_de(_problem(budget=budget), Uniform(N_OPERATORS), CFG, np.random.default_rng(0))
    assert r.selection_hist.sum() == budget - CFG.NP
    assert r.success_hist.sum() <= r.selection_hist.sum()


def test_fixed_policy_uses_only_its_operator():
    for k in range(N_OPERATORS):
        r = run_de(_problem(budget=1000), Fixed(N_OPERATORS, k), CFG, np.random.default_rng(0))
        used = r.selection_hist.sum(axis=0)
        assert used[k] == used.sum()


def test_de_beats_random_search_on_sphere():
    """A sanity floor: if DE cannot beat uniform sampling, nothing downstream means anything."""
    budget = 3000
    de = run_de(_problem(budget=budget), Uniform(N_OPERATORS), CFG, np.random.default_rng(0))

    p = _problem(budget=budget)
    rng = np.random.default_rng(0)
    try:
        while True:
            p(rng.uniform(p.lb, p.ub))
    except Exception:  # noqa: BLE001 -- BudgetExhausted ends the loop
        pass
    assert de.best_error < p.best_error / 100


def test_population_floor_enforced():
    with pytest.raises(ValueError):
        DEConfig(NP=5)  # DE/rand/2 needs six


def test_trace_reaches_full_budget():
    r = run_de(_problem(budget=2000), Uniform(N_OPERATORS), CFG, np.random.default_rng(0))
    assert r.trace_evals[-1] == 2000
    assert r.trace_error[-1] == pytest.approx(r.best_error)
