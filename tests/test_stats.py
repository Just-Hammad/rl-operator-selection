"""The statistics module is the one piece every other project will import.

These tests are what make the spine seam safe to swap: if `mhbench.stats` passes
them too, the swap cannot silently change a published number.
"""

import numpy as np
import pandas as pd
import pytest

from aos.stats import cliffs_delta, cliffs_magnitude, friedman_ranks, posthoc_holm


def test_cliffs_delta_identities():
    x = np.arange(10.0)
    assert cliffs_delta(x, x) == 0.0
    assert cliffs_delta(x + 100, x) == 1.0
    assert cliffs_delta(x - 100, x) == -1.0


def test_cliffs_delta_antisymmetric():
    rng = np.random.default_rng(0)
    a, b = rng.normal(size=40), rng.normal(1, size=40)
    assert cliffs_delta(a, b) == pytest.approx(-cliffs_delta(b, a))


def test_cliffs_delta_bounded():
    rng = np.random.default_rng(1)
    for _ in range(20):
        a, b = rng.normal(size=15), rng.normal(size=15)
        assert -1.0 <= cliffs_delta(a, b) <= 1.0


def test_cliffs_delta_rejects_empty():
    with pytest.raises(ValueError):
        cliffs_delta([], [1.0])


def test_cliffs_magnitude_cutpoints():
    assert cliffs_magnitude(0.10) == "negligible"
    assert cliffs_magnitude(0.20) == "small"
    assert cliffs_magnitude(0.40) == "medium"
    assert cliffs_magnitude(0.90) == "large"
    assert cliffs_magnitude(-0.90) == "large"  # magnitude ignores direction


def test_friedman_ranks_ordering():
    rng = np.random.default_rng(0)
    m = pd.DataFrame(
        {"A": rng.random(25), "B": rng.random(25) + 2, "C": rng.random(25) + 4}
    )
    stat, p, ranks = friedman_ranks(m)
    assert p < 0.01
    assert list(ranks.index) == ["A", "B", "C"]  # ascending: rank 1 is lowest error
    assert ranks["A"] == pytest.approx(1.0)


def test_friedman_needs_three_groups():
    m = pd.DataFrame({"A": [1.0, 2, 3], "B": [2.0, 3, 4]})
    with pytest.raises(ValueError):
        friedman_ranks(m)


def test_posthoc_holm_shape_and_labels():
    rng = np.random.default_rng(2)
    m = pd.DataFrame(
        {"A": rng.random(25), "B": rng.random(25) + 2, "C": rng.random(25) + 4}
    )
    h = posthoc_holm(m)
    assert list(h.columns) == ["A", "B", "C"]
    assert list(h.index) == ["A", "B", "C"]
    assert np.allclose(np.diag(h.to_numpy()), 1.0)
    assert np.allclose(h.to_numpy(), h.to_numpy().T)  # symmetric
    assert h.loc["A", "C"] < 0.05
