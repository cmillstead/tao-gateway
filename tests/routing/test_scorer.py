import threading
from datetime import UTC, datetime

from gateway.routing.scorer import MinerScorer, ScoreObservation


def _make_observation(
    *,
    miner_uid: int = 1,
    hotkey: str = "abc12345",
    netuid: int = 1,
    success: bool = True,
    latency_ms: float = 100.0,
    response_valid: bool = True,
    response_complete: bool | None = True,
) -> ScoreObservation:
    return ScoreObservation(
        miner_uid=miner_uid,
        hotkey=hotkey,
        netuid=netuid,
        success=success,
        latency_ms=latency_ms,
        response_valid=response_valid,
        response_complete=response_complete,
        timestamp=datetime.now(UTC),
    )


class TestMinerScorer:
    def test_record_observation_updates_score(self) -> None:
        scorer = MinerScorer(ema_alpha=0.3)
        scorer.record_observation(_make_observation())
        score = scorer.get_score(netuid=1, hotkey="abc12345")
        assert score is not None
        assert 0.0 < score <= 1.0

    def test_ema_calculation_converges(self) -> None:
        """After many perfect observations, score should approach 1.0."""
        scorer = MinerScorer(ema_alpha=0.3)
        for _ in range(50):
            scorer.record_observation(
                _make_observation(latency_ms=50.0, success=True, response_complete=True)
            )
        score = scorer.get_score(netuid=1, hotkey="abc12345")
        assert score is not None
        assert score > 0.9

    def test_ema_with_failures_lowers_score(self) -> None:
        """After some successes then failures, score should decrease."""
        scorer = MinerScorer(ema_alpha=0.3)
        # Build up a good score
        for _ in range(10):
            scorer.record_observation(_make_observation(success=True, latency_ms=100.0))
        good_score = scorer.get_score(netuid=1, hotkey="abc12345")

        # Now record failures
        for _ in range(5):
            scorer.record_observation(_make_observation(success=False, latency_ms=5000.0))
        bad_score = scorer.get_score(netuid=1, hotkey="abc12345")

        assert good_score is not None
        assert bad_score is not None
        assert bad_score < good_score

    def test_get_score_returns_none_for_unknown(self) -> None:
        scorer = MinerScorer(ema_alpha=0.3)
        assert scorer.get_score(netuid=99, hotkey="unknown") is None

    def test_get_scores_returns_all_for_subnet(self) -> None:
        scorer = MinerScorer(ema_alpha=0.3)
        scorer.record_observation(_make_observation(miner_uid=1, hotkey="aaa"))
        scorer.record_observation(_make_observation(miner_uid=2, hotkey="bbb"))
        scorer.record_observation(_make_observation(miner_uid=3, hotkey="ccc", netuid=2))

        scores = scorer.get_scores(netuid=1)
        assert len(scores) == 2
        assert "aaa" in scores
        assert "bbb" in scores
        # Different subnet not included
        assert "ccc" not in scores

    def test_get_scores_empty_subnet(self) -> None:
        scorer = MinerScorer(ema_alpha=0.3)
        assert scorer.get_scores(netuid=99) == {}

    def test_get_snapshot_and_reset(self) -> None:
        scorer = MinerScorer(ema_alpha=0.3)
        scorer.record_observation(_make_observation(miner_uid=1, hotkey="aaa"))
        scorer.record_observation(_make_observation(miner_uid=1, hotkey="aaa"))
        scorer.record_observation(_make_observation(miner_uid=2, hotkey="bbb"))

        snapshot = scorer.get_snapshot_and_reset()
        assert len(snapshot) == 2

        # Verify snapshot has correct fields
        by_hotkey = {s.hotkey: s for s in snapshot}
        assert by_hotkey["aaa"].total_requests == 2
        assert by_hotkey["bbb"].total_requests == 1

        # Scores should still exist (not cleared), but request counters reset
        score = scorer.get_score(netuid=1, hotkey="aaa")
        assert score is not None  # Score preserved

        # Second snapshot should show 0 total_requests (counters were reset)
        snapshot2 = scorer.get_snapshot_and_reset()
        for item in snapshot2:
            assert item.total_requests == 0

    def test_success_false_scores_lower(self) -> None:
        scorer = MinerScorer(ema_alpha=1.0)  # alpha=1 means only latest observation matters
        scorer.record_observation(_make_observation(success=True, latency_ms=100.0))
        good = scorer.get_score(netuid=1, hotkey="abc12345")

        scorer2 = MinerScorer(ema_alpha=1.0)
        scorer2.record_observation(_make_observation(success=False, latency_ms=100.0))
        bad = scorer2.get_score(netuid=1, hotkey="abc12345")

        assert good is not None and bad is not None
        assert bad < good

    def test_latency_normalization(self) -> None:
        """Low latency should score higher than high latency."""
        scorer = MinerScorer(ema_alpha=1.0, subnet_timeouts={1: 12000.0})

        scorer.record_observation(_make_observation(miner_uid=1, hotkey="fast", latency_ms=100.0))
        fast_score = scorer.get_score(netuid=1, hotkey="fast")

        scorer.record_observation(
            _make_observation(miner_uid=2, hotkey="slow", latency_ms=10000.0)
        )
        slow_score = scorer.get_score(netuid=1, hotkey="slow")

        assert fast_score is not None and slow_score is not None
        assert fast_score > slow_score

    def test_response_complete_none_not_penalized(self) -> None:
        """When response_complete is None (not sampled), completeness shouldn't hurt score."""
        scorer = MinerScorer(ema_alpha=1.0)
        scorer.record_observation(
            _make_observation(miner_uid=1, hotkey="sampled", response_complete=True)
        )
        sampled = scorer.get_score(netuid=1, hotkey="sampled")

        scorer.record_observation(
            _make_observation(miner_uid=2, hotkey="not_sampled", response_complete=None)
        )
        not_sampled = scorer.get_score(netuid=1, hotkey="not_sampled")

        assert sampled is not None and not_sampled is not None
        # Not-sampled should get full completeness credit (not penalized)
        assert not_sampled == sampled

    def test_thread_safety_concurrent_observations(self) -> None:
        """Multiple threads recording observations should not corrupt state."""
        scorer = MinerScorer(ema_alpha=0.3)
        errors: list[Exception] = []

        def record_many(uid: int) -> None:
            try:
                for _ in range(100):
                    scorer.record_observation(
                        _make_observation(miner_uid=uid, hotkey=f"h{uid}", netuid=1)
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_many, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        scores = scorer.get_scores(netuid=1)
        assert len(scores) == 5
        for uid in range(5):
            assert scores[f"h{uid}"] is not None

    def test_multiple_subnets_independent(self) -> None:
        scorer = MinerScorer(ema_alpha=0.3)
        scorer.record_observation(
            _make_observation(miner_uid=1, hotkey="a", netuid=1, success=True)
        )
        scorer.record_observation(
            _make_observation(miner_uid=1, hotkey="a", netuid=2, success=False)
        )

        score_sn1 = scorer.get_score(netuid=1, hotkey="a")
        score_sn2 = scorer.get_score(netuid=2, hotkey="a")

        assert score_sn1 is not None and score_sn2 is not None
        assert score_sn1 > score_sn2

    def test_sample_rate_property(self) -> None:
        scorer = MinerScorer(ema_alpha=0.3, sample_rate=0.5)
        assert scorer.sample_rate == 0.5

    def test_default_sample_rate_is_one(self) -> None:
        scorer = MinerScorer(ema_alpha=0.3)
        assert scorer.sample_rate == 1.0
