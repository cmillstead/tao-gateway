from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime

# Scoring formula weights
_SUCCESS_WEIGHT = 0.5
_LATENCY_WEIGHT = 0.3
_COMPLETENESS_WEIGHT = 0.2

# Default subnet timeout for latency normalization (ms)
_DEFAULT_TIMEOUT_MS = 30_000.0


@dataclass
class ScoreObservation:
    miner_uid: int
    hotkey: str
    netuid: int
    success: bool
    latency_ms: float
    response_valid: bool
    response_complete: bool | None  # None = not sampled
    timestamp: datetime


@dataclass
class MinerQualityScore:
    miner_uid: int
    hotkey: str
    netuid: int
    quality_score: float  # 0.0 to 1.0
    total_requests: int
    successful_requests: int
    avg_latency_ms: float
    last_updated: datetime


@dataclass
class _MinerState:
    """Internal mutable state for a single miner on a single subnet."""

    miner_uid: int
    hotkey: str
    netuid: int
    quality_score: float = 0.0
    total_requests: int = 0
    successful_requests: int = 0
    latency_sum_ms: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))


class MinerScorer:
    """In-memory miner quality scoring engine using EMA.

    Thread-safe: all mutations are protected by a lock.
    """

    def __init__(
        self,
        ema_alpha: float = 0.3,
        subnet_timeouts: dict[int, float] | None = None,
        sample_rate: float = 1.0,
    ) -> None:
        self._ema_alpha = ema_alpha
        self._subnet_timeouts = subnet_timeouts or {}
        self._sample_rate = sample_rate
        self._lock = threading.Lock()
        # Key: (netuid, hotkey) -> _MinerState
        self._states: dict[tuple[int, str], _MinerState] = {}

    def _compute_observation_score(self, obs: ScoreObservation) -> float:
        """Compute a 0.0-1.0 score for a single observation."""
        success_component = _SUCCESS_WEIGHT * float(obs.success)

        timeout_ms = self._subnet_timeouts.get(obs.netuid, _DEFAULT_TIMEOUT_MS)
        latency_ratio = max(0.0, 1.0 - (obs.latency_ms / timeout_ms)) if timeout_ms > 0 else 0.0
        latency_component = _LATENCY_WEIGHT * latency_ratio

        # If not sampled, give full completeness credit
        completeness_val = 1.0 if obs.response_complete is None else float(obs.response_complete)
        completeness_component = _COMPLETENESS_WEIGHT * completeness_val

        return success_component + latency_component + completeness_component

    @property
    def sample_rate(self) -> float:
        return self._sample_rate

    def record_observation(self, observation: ScoreObservation) -> None:
        key = (observation.netuid, observation.hotkey)
        obs_score = self._compute_observation_score(observation)

        with self._lock:
            state = self._states.get(key)
            if state is None:
                state = _MinerState(
                    miner_uid=observation.miner_uid,
                    hotkey=observation.hotkey,
                    netuid=observation.netuid,
                    quality_score=obs_score,
                )
                self._states[key] = state
            else:
                state.quality_score = (
                    self._ema_alpha * obs_score
                    + (1 - self._ema_alpha) * state.quality_score
                )

            state.total_requests += 1
            if observation.success:
                state.successful_requests += 1
            state.latency_sum_ms += observation.latency_ms
            state.last_updated = observation.timestamp

    def get_score(self, netuid: int, hotkey: str) -> float | None:
        with self._lock:
            state = self._states.get((netuid, hotkey))
            return state.quality_score if state is not None else None

    def get_scores(self, netuid: int) -> dict[str, float]:
        with self._lock:
            return {
                hk: state.quality_score
                for (net, hk), state in self._states.items()
                if net == netuid
            }

    def get_snapshot_and_reset(self) -> list[MinerQualityScore]:
        """Return current scores for DB flush and reset observation counters.

        Scores are preserved (not cleared); only request counters reset.
        """
        with self._lock:
            snapshot = []
            for state in self._states.values():
                avg_latency = (
                    state.latency_sum_ms / state.total_requests
                    if state.total_requests > 0
                    else 0.0
                )
                snapshot.append(
                    MinerQualityScore(
                        miner_uid=state.miner_uid,
                        hotkey=state.hotkey,
                        netuid=state.netuid,
                        quality_score=state.quality_score,
                        total_requests=state.total_requests,
                        successful_requests=state.successful_requests,
                        avg_latency_ms=avg_latency,
                        last_updated=state.last_updated,
                    )
                )
                # Reset counters but preserve scores
                state.total_requests = 0
                state.successful_requests = 0
                state.latency_sum_ms = 0.0
            return snapshot
