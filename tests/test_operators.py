import numpy as np
import pytest

from aos.operators import (
    MIN_POPULATION,
    OPERATOR_NAMES,
    POOL,
    MutationContext,
    _distinct,
    binomial_crossover,
    repair_midpoint,
)


@pytest.fixture
def ctx():
    rng = np.random.default_rng(0)
    return MutationContext(
        pop=rng.random((12, 6)), fit=rng.random(12), i=3, F=0.5, rng=rng
    )


@pytest.mark.parametrize("name,fn", POOL)
def test_operator_shape_and_finite(name, fn, ctx):
    for _ in range(50):
        v = fn(ctx)
        assert v.shape == (6,)
        assert np.all(np.isfinite(v))


@pytest.mark.parametrize("name,fn", POOL)
def test_operator_does_not_mutate_population(name, fn, ctx):
    before = ctx.pop.copy()
    fn(ctx)
    assert np.array_equal(ctx.pop, before)


def test_pool_has_min_population_headroom():
    # DE/rand/2 draws five distinct indices besides the target.
    assert MIN_POPULATION >= 6
    assert len(OPERATOR_NAMES) == len(POOL)


def test_distinct_excludes_and_is_distinct():
    rng = np.random.default_rng(0)
    for _ in range(500):
        idx = _distinct(rng, 10, 5, exclude=4)
        assert 4 not in idx
        assert len(set(idx.tolist())) == 5
        assert idx.min() >= 0 and idx.max() < 10


def test_distinct_rejects_impossible_draw():
    with pytest.raises(ValueError):
        _distinct(np.random.default_rng(0), 4, 5, exclude=0)


def test_crossover_inherits_at_least_one_mutant_component():
    rng = np.random.default_rng(0)
    x, v = np.zeros(20), np.ones(20)
    for _ in range(200):
        u = binomial_crossover(x, v, CR=0.0, rng=rng)  # worst case: jrand only
        assert u.sum() >= 1.0


def test_crossover_full_cr_takes_mutant():
    rng = np.random.default_rng(0)
    x, v = np.zeros(20), np.ones(20)
    assert np.array_equal(binomial_crossover(x, v, CR=1.0, rng=rng), v)


def test_repair_returns_into_bounds():
    lb, ub = np.full(8, -5.0), np.full(8, 5.0)
    rng = np.random.default_rng(0)
    for _ in range(200):
        x = rng.uniform(lb, ub)
        u = rng.uniform(-50, 50, size=8)
        r = repair_midpoint(u, x, lb, ub)
        assert np.all(r >= lb) and np.all(r <= ub)


def test_repair_leaves_interior_untouched():
    lb, ub = np.full(4, -5.0), np.full(4, 5.0)
    x = np.zeros(4)
    u = np.array([1.0, -2.0, 3.0, 0.0])
    assert np.array_equal(repair_midpoint(u, x, lb, ub), u)
