"""The algorithm roster.

Order is fixed and load-bearing: the index of a name in ``ALGORITHM_NAMES`` is folded
into that cell's random seed, so reordering changes every seed in the study.

**Appending is only safe at the very end.** ``ALGORITHM_NAMES`` is
``tuple(POLICY_FACTORIES) + STANDALONE``, so adding a policy shifts the index of
everything in ``STANDALONE`` and silently re-seeds those cells. Add new policies at the
end of ``STANDALONE``, or freeze an explicit order list before the next study.

Policies are stateful, so each entry is a *factory* -- a fresh policy per run, never a
shared one.
"""

from __future__ import annotations

from collections.abc import Callable

from .operators import N_OPERATORS, OPERATOR_NAMES
from .policies import (
    AdaptivePursuit,
    Fixed,
    Policy,
    ProbabilityMatching,
    SlidingWindowUCB,
    SuccessRate,
    ThompsonGaussian,
    Uniform,
)

#: Algorithms that are a policy over the shared operator pool.
POLICY_FACTORIES: dict[str, Callable[[], Policy]] = {
    f"fixed:{OPERATOR_NAMES[k]}": (lambda k=k: Fixed(N_OPERATORS, k, f"fixed:{OPERATOR_NAMES[k]}"))
    for k in range(N_OPERATORS)
}
POLICY_FACTORIES.update(
    {
        "uniform": lambda: Uniform(N_OPERATORS),
        "ucb": lambda: SlidingWindowUCB(N_OPERATORS, C=0.5, window=50, aggregate="extreme"),
        "thompson": lambda: ThompsonGaussian(N_OPERATORS, window=50, aggregate="average"),
        "pm": lambda: ProbabilityMatching(N_OPERATORS, alpha=0.3, p_min=0.05),
        "ap": lambda: AdaptivePursuit(N_OPERATORS, alpha=0.3, beta=0.3, p_min=0.05),
        "success-rate": lambda: SuccessRate(N_OPERATORS, window=250),
    }
)

#: Algorithms that are not policy-based and run their own loop.
STANDALONE: tuple[str, ...] = ("jade",)

ALGORITHM_NAMES: tuple[str, ...] = tuple(POLICY_FACTORIES) + STANDALONE

#: The adaptive policies -- the ones whose learning is on trial.
ADAPTIVE: tuple[str, ...] = ("ucb", "thompson", "pm", "ap", "success-rate")
#: The single fixed operators.
FIXED: tuple[str, ...] = tuple(f"fixed:{n}" for n in OPERATOR_NAMES)
#: The ablation.
ABLATION: str = "uniform"


def algorithm_index(name: str) -> int:
    return ALGORITHM_NAMES.index(name)
