import numpy as np

from aos.registry import ALGORITHM_NAMES, algorithm_index
from aos.runner import ExperimentConfig, build_tasks, cell_seed


def test_cell_seed_is_deterministic():
    a = cell_seed(7, "ucb", 3, 1, 20, 11)
    b = cell_seed(7, "ucb", 3, 1, 20, 11)
    assert a == b


def test_cell_seed_varies_across_every_axis():
    base = dict(master=7, algorithm="ucb", fid=3, instance=1, dim=20, run=11)
    seeds = {cell_seed(**base)}
    for k, v in [
        ("master", 8),
        ("algorithm", "pm"),
        ("fid", 4),
        ("instance", 2),
        ("dim", 5),
        ("run", 12),
    ]:
        seeds.add(cell_seed(**{**base, k: v}))
    assert len(seeds) == 7, "seed must depend on every grid coordinate"


def test_seeds_are_unique_across_a_grid():
    seeds = [
        cell_seed(1, alg, fid, 1, d, r)
        for alg in ALGORITHM_NAMES
        for fid in range(1, 25)
        for d in (5, 20)
        for r in range(25)
    ]
    assert len(set(seeds)) == len(seeds)


def test_algorithm_index_is_stable_and_total():
    assert len(set(ALGORITHM_NAMES)) == len(ALGORITHM_NAMES)
    for i, name in enumerate(ALGORITHM_NAMES):
        assert algorithm_index(name) == i


def test_config_round_trip(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(
        "name: t\ndims: [5]\nfids: [1,2]\nruns: 2\nbudget_multiplier: 100\n"
        "master_seed: 1\nalgorithms: [uniform, ucb]\nde: {NP: 20}\n"
    )
    cfg = ExperimentConfig.load(p)
    assert cfg.budget(5) == 500
    assert cfg.de.NP == 20
    assert len(build_tasks(cfg)) == 1 * 2 * 2 * 2  # dims x algs x fids x runs


def test_config_rejects_unknown_algorithm(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(
        "name: t\ndims: [5]\nruns: 1\nbudget_multiplier: 100\nmaster_seed: 1\n"
        "algorithms: [not_a_real_algorithm]\n"
    )
    try:
        ExperimentConfig.load(p)
    except ValueError as e:
        assert "not_a_real_algorithm" in str(e)
    else:
        raise AssertionError("must reject unknown algorithm names")
