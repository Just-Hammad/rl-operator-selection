import numpy as np
import pytest

from aos.credit import CreditWindow, raw_credit
from aos.operators import N_OPERATORS
from aos.policies import (
    AdaptivePursuit,
    Fixed,
    ProbabilityMatching,
    SlidingWindowUCB,
    SuccessRate,
    ThompsonGaussian,
    Uniform,
)

ADAPTIVE_FACTORIES = [
    lambda: SlidingWindowUCB(N_OPERATORS),
    lambda: ThompsonGaussian(N_OPERATORS),
    lambda: ProbabilityMatching(N_OPERATORS),
    lambda: AdaptivePursuit(N_OPERATORS),
    lambda: SuccessRate(N_OPERATORS),
]
ALL_FACTORIES = [*ADAPTIVE_FACTORIES, lambda: Uniform(N_OPERATORS)]


@pytest.mark.parametrize("make", ALL_FACTORIES)
def test_select_in_range(make):
    pol, rng = make(), np.random.default_rng(0)
    for _ in range(300):
        k = pol.select(rng)
        assert 0 <= k < N_OPERATORS
        pol.update(k, 0.5)


@pytest.mark.parametrize("make", ADAPTIVE_FACTORIES)
def test_adaptive_policies_concentrate_on_the_rewarding_arm(make):
    """The point of the whole project: a learning policy must actually learn."""
    pol, rng = make(), np.random.default_rng(0)
    good = 2
    sel = []
    for _ in range(3000):
        k = pol.select(rng)
        sel.append(k)
        pol.update(k, 1.0 if k == good else 0.0)
    share = np.bincount(sel, minlength=N_OPERATORS)[good] / len(sel)
    assert share > 0.5, f"{pol.name} only used the good arm {share:.2%} of the time"


def test_uniform_does_not_concentrate():
    """The ablation must stay flat -- it is the null this project tests against."""
    pol, rng = Uniform(N_OPERATORS), np.random.default_rng(0)
    sel = [pol.select(rng) for _ in range(20000)]
    share = np.bincount(sel, minlength=N_OPERATORS) / len(sel)
    assert np.allclose(share, 1 / N_OPERATORS, atol=0.02)


def test_uniform_ignores_credit():
    pol, rng = Uniform(N_OPERATORS), np.random.default_rng(0)
    for _ in range(2000):
        pol.update(0, 1000.0)
    sel = [pol.select(rng) for _ in range(20000)]
    share = np.bincount(sel, minlength=N_OPERATORS) / len(sel)
    assert np.allclose(share, 1 / N_OPERATORS, atol=0.02)


def test_fixed_is_fixed():
    rng = np.random.default_rng(0)
    for k in range(N_OPERATORS):
        pol = Fixed(N_OPERATORS, k)
        assert {pol.select(rng) for _ in range(200)} == {k}
        assert pol.distribution()[k] == 1.0


@pytest.mark.parametrize("make", ALL_FACTORIES)
def test_distribution_is_a_distribution(make):
    pol, rng = make(), np.random.default_rng(0)
    for _ in range(500):
        pol.update(pol.select(rng), 0.3)
    d = pol.distribution()
    if d is not None:
        assert d.shape == (N_OPERATORS,)
        assert np.all(d >= 0)
        assert d.sum() == pytest.approx(1.0)


def test_p_min_keeps_every_operator_reachable():
    """Without a floor, an operator that fails early can never recover."""
    for pol in (ProbabilityMatching(N_OPERATORS), AdaptivePursuit(N_OPERATORS)):
        for _ in range(5000):
            pol.update(0, 10.0)  # arm 0 is wildly better
        assert np.all(pol.distribution() >= pol.p_min - 1e-9)


def test_probability_matching_rejects_infeasible_p_min():
    with pytest.raises(ValueError):
        ProbabilityMatching(5, p_min=0.25)


def test_raw_credit_schemes():
    assert raw_credit(10.0, 4.0, "improvement") == 6.0
    assert raw_credit(4.0, 10.0, "improvement") == 0.0  # never negative
    assert raw_credit(10.0, 5.0, "relative") == pytest.approx(0.5)
    assert raw_credit(10.0, 9.99, "binary") == 1.0
    assert raw_credit(10.0, 10.0, "binary") == 0.0
    with pytest.raises(ValueError):
        raw_credit(1.0, 0.0, "nonsense")


def test_credit_window_evicts_and_aggregates():
    w = CreditWindow(3, window=4, aggregate="extreme")
    for c in (5.0, 1.0, 1.0, 1.0):
        w.push(0, c)
    assert w.values()[0] == 5.0
    w.push(1, 0.0)  # evicts the 5.0
    assert w.values()[0] == 1.0
    assert w.counts().sum() == 4


def test_credit_window_normalisation_bounded():
    w = CreditWindow(3, window=10, aggregate="average")
    w.push(0, 8.0)
    w.push(1, 2.0)
    n = w.normalised_values()
    assert n.max() == pytest.approx(1.0)
    assert np.all((n >= 0) & (n <= 1))
