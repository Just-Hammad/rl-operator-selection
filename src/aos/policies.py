"""Operator-selection policies.

Every policy is an arm-selection rule over the same operator pool, so a comparison
between them isolates the *selection mechanism* and nothing else -- same DE, same
operators, same F, same CR, same budget.

``Uniform`` is the ablation the whole project turns on: if a learned policy cannot
beat uniform random selection over the identical pool, the benefit came from operator
diversity rather than from learning.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from .credit import CreditWindow


class Policy(ABC):
    """Selection rule over ``n`` operators.

    The RNG is passed in rather than held, so a run is fully determined by its seed.
    """

    name: str = "policy"

    def __init__(self, n_operators: int):
        self.n = n_operators

    @abstractmethod
    def select(self, rng: np.random.Generator) -> int: ...

    def update(self, k: int, credit: float) -> None:  # noqa: B027
        """Observe the credit earned by operator ``k``. Stateless policies ignore it."""

    def distribution(self) -> np.ndarray | None:
        """Current selection probabilities, where the policy has them.

        ``None`` for argmax policies (UCB, Thompson), whose behaviour is only
        observable through the selections they actually make -- which is why the
        report derives the adaptation plot from realised selections, not from this.
        """
        return None


class Fixed(Policy):
    """Always the same operator. One instance per operator gives the fixed baselines."""

    def __init__(self, n_operators: int, k: int, label: str | None = None):
        super().__init__(n_operators)
        self.k = int(k)
        self.name = label or f"fixed:{k}"

    def select(self, rng: np.random.Generator) -> int:
        return self.k

    def distribution(self) -> np.ndarray:
        p = np.zeros(self.n)
        p[self.k] = 1.0
        return p


class Uniform(Policy):
    """Uniform random selection. **The ablation.**

    Costs nothing, learns nothing, and has the same operator diversity as every
    adaptive policy here. Any adaptive policy that fails to beat it has demonstrated
    that its learning contributes nothing -- which is a result, and one this
    literature rarely reports.
    """

    name = "uniform"

    def select(self, rng: np.random.Generator) -> int:
        return int(rng.integers(self.n))

    def distribution(self) -> np.ndarray:
        return np.full(self.n, 1.0 / self.n)


class SlidingWindowUCB(Policy):
    """UCB1 over a sliding window of recent credits.

    Vanilla UCB1 assumes a stationary reward distribution. Operator utility here is
    emphatically non-stationary -- exploratory operators pay early, exploitative ones
    pay late -- so the window is not an optimisation, it is what makes the algorithm
    applicable at all.

    Each arm is played once before the confidence bound is used, which is UCB1's own
    initialisation rule.
    """

    def __init__(
        self,
        n_operators: int,
        C: float = 0.5,
        window: int = 50,
        aggregate: str = "extreme",
        credit_scheme: str = "improvement",
    ):
        super().__init__(n_operators)
        self.C = float(C)
        self.credit_scheme = credit_scheme
        self.win = CreditWindow(n_operators, window=window, aggregate=aggregate)
        self.name = f"ucb(C={C},W={window},{aggregate})"

    def select(self, rng: np.random.Generator) -> int:
        counts = self.win.counts()
        unplayed = np.flatnonzero(counts == 0)
        if len(unplayed):
            return int(rng.choice(unplayed))
        q = self.win.normalised_values()
        total = counts.sum()
        bonus = self.C * np.sqrt(2.0 * np.log(total) / counts)
        return int(np.argmax(q + bonus))

    def update(self, k: int, credit: float) -> None:
        self.win.push(k, credit)


class ThompsonGaussian(Policy):
    """Thompson sampling with a Gaussian posterior over each arm's mean credit.

    Gaussian rather than Beta-Bernoulli because credit here is a continuous magnitude
    and binarising it throws away exactly the information that extreme-value credit
    assignment exists to keep. Posterior width shrinks as 1/sqrt(n+1) over the window.
    """

    def __init__(
        self,
        n_operators: int,
        window: int = 50,
        aggregate: str = "average",
        prior_sigma: float = 0.5,
        credit_scheme: str = "improvement",
    ):
        super().__init__(n_operators)
        self.prior_sigma = float(prior_sigma)
        self.credit_scheme = credit_scheme
        self.win = CreditWindow(n_operators, window=window, aggregate=aggregate)
        self.name = f"thompson(W={window},{aggregate})"

    def select(self, rng: np.random.Generator) -> int:
        counts = self.win.counts()
        mu = self.win.normalised_values()
        sigma = self.prior_sigma / np.sqrt(counts + 1.0)
        return int(np.argmax(rng.normal(mu, sigma)))

    def update(self, k: int, credit: float) -> None:
        self.win.push(k, credit)


class ProbabilityMatching(Policy):
    """Probability matching: selection probability proportional to estimated quality.

    Quality is an exponential recency-weighted average. ``p_min`` keeps every operator
    reachable -- without it an operator that fails early is never sampled again and
    cannot recover when the search phase changes.
    """

    def __init__(
        self,
        n_operators: int,
        alpha: float = 0.3,
        p_min: float = 0.05,
        credit_scheme: str = "improvement",
    ):
        super().__init__(n_operators)
        if p_min * n_operators >= 1.0:
            raise ValueError("p_min * n_operators must be < 1")
        self.alpha = float(alpha)
        self.p_min = float(p_min)
        self.credit_scheme = credit_scheme
        self.q = np.zeros(n_operators)
        self.name = f"pm(alpha={alpha},pmin={p_min})"

    def _probs(self) -> np.ndarray:
        total = self.q.sum()
        if total <= 0:
            return np.full(self.n, 1.0 / self.n)
        return self.p_min + (1.0 - self.n * self.p_min) * (self.q / total)

    def select(self, rng: np.random.Generator) -> int:
        return int(rng.choice(self.n, p=self._probs()))

    def update(self, k: int, credit: float) -> None:
        self.q[k] += self.alpha * (credit - self.q[k])

    def distribution(self) -> np.ndarray:
        return self._probs()


class AdaptivePursuit(Policy):
    """Adaptive pursuit: push probability mass toward the current best operator.

    More aggressive than probability matching -- it pursues the argmax rather than
    matching the quality ratio, so it commits faster and recovers more slowly.
    """

    def __init__(
        self,
        n_operators: int,
        alpha: float = 0.3,
        beta: float = 0.3,
        p_min: float = 0.05,
        credit_scheme: str = "improvement",
    ):
        super().__init__(n_operators)
        if p_min * n_operators >= 1.0:
            raise ValueError("p_min * n_operators must be < 1")
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.p_min = float(p_min)
        self.p_max = 1.0 - (n_operators - 1) * p_min
        self.credit_scheme = credit_scheme
        self.q = np.zeros(n_operators)
        self.p = np.full(n_operators, 1.0 / n_operators)
        self.name = f"ap(alpha={alpha},beta={beta})"

    def select(self, rng: np.random.Generator) -> int:
        return int(rng.choice(self.n, p=self.p / self.p.sum()))

    def update(self, k: int, credit: float) -> None:
        self.q[k] += self.alpha * (credit - self.q[k])
        best = int(np.argmax(self.q))
        target = np.full(self.n, self.p_min)
        target[best] = self.p_max
        self.p += self.beta * (target - self.p)

    def distribution(self) -> np.ndarray:
        return self.p / self.p.sum()


class SuccessRate(Policy):
    """SaDE-style selection: probability proportional to recent success rate.

    Not a bandit -- no exploration term, no posterior. It is the mechanism published
    adaptive-DE methods actually use, included so the bandits are measured against
    the field's own approach rather than only against fixed operators.

    **Deviation from published SaDE, stated plainly:** SaDE's learning period is
    counted in generations and it simultaneously adapts F and CR. Here the window is
    counted in applications and F/CR are held fixed, so that this comparison isolates
    the selection mechanism. It is *SaDE-style*, not SaDE.
    """

    def __init__(self, n_operators: int, window: int = 250, eps: float = 0.01):
        super().__init__(n_operators)
        self.eps = float(eps)
        self.win = CreditWindow(n_operators, window=window, aggregate="average")
        self.name = f"success-rate(W={window})"

    def _probs(self) -> np.ndarray:
        if len(self.win) < self.n:
            return np.full(self.n, 1.0 / self.n)
        # 'average' over binary credit is exactly the success rate.
        s = self.win.values() + self.eps
        return s / s.sum()

    def select(self, rng: np.random.Generator) -> int:
        return int(rng.choice(self.n, p=self._probs()))

    def update(self, k: int, credit: float) -> None:
        self.win.push(k, 1.0 if credit > 0 else 0.0)

    def distribution(self) -> np.ndarray:
        return self._probs()
