import json
import random
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import bittensor as bt
import nh3
import structlog

from gateway.core.exceptions import (
    MinerInvalidResponseError,
    MinerTimeoutError,
)
from gateway.routing.selector import MinerSelector

if TYPE_CHECKING:
    from gateway.routing.scorer import MinerScorer

logger = structlog.get_logger()

MINER_UID_PREFIX_LEN = 8
SSE_DONE = "data: [DONE]\n\n"


def generate_completion_id() -> str:
    """Generate a unique OpenAI-compatible completion ID."""
    return f"chatcmpl-{uuid.uuid4().hex[:24]}"


@dataclass
class AdapterConfig:
    netuid: int
    subnet_name: str
    timeout_seconds: int
    max_retries: int = 0  # MVP: no retries


class BaseAdapter(ABC):
    """Fat base class — handles miner selection, Dendrite query, response
    validation, sanitization. Concrete adapters provide only ~50 lines:
    to_synapse(), from_response(), sanitize_output(), get_config()."""

    def sanitize_text(self, text: str) -> str:
        """Strip all HTML tags from miner output using nh3."""
        if not isinstance(text, str):
            return str(text) if text is not None else ""
        return nh3.clean(text, tags=set()).replace("\x00", "")

    @abstractmethod
    def to_synapse(self, request_data: dict[str, Any]) -> bt.Synapse:
        """Convert API request to subnet-specific Synapse."""
        ...

    @abstractmethod
    def from_response(
        self, synapse: bt.Synapse, request_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert miner's Synapse response to API response dict."""
        ...

    @abstractmethod
    def sanitize_output(self, response_data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize miner response before returning to consumer."""
        ...

    @abstractmethod
    def get_config(self) -> AdapterConfig:
        """Return adapter configuration."""
        ...

    @abstractmethod
    def get_capability(self) -> str:
        """Return human-readable capability name (e.g., 'Text Generation')."""
        ...

    @abstractmethod
    def get_parameters(self) -> dict[str, str]:
        """Return informational parameter descriptions for /v1/models discovery."""
        ...

    def _record_score(
        self,
        scorer: "MinerScorer | None",
        axon: bt.AxonInfo,
        config: AdapterConfig,
        elapsed_ms: float,
        *,
        success: bool,
        response_valid: bool = False,
        response_complete: bool | None = None,
    ) -> None:
        """Record a scoring observation if scorer is available.

        When success is True, content sampling is applied: response_complete
        is set to True only if the request is sampled (random draw against
        scorer.sample_rate), otherwise it is set to None (not sampled, gets
        full completeness credit).
        """
        if scorer is None:
            return
        from gateway.routing.scorer import ScoreObservation

        # Apply content sampling for successful responses
        if success and response_complete is not None:
            response_complete = True if random.random() < scorer.sample_rate else None

        scorer.record_observation(
            ScoreObservation(
                miner_uid=getattr(axon, "uid", 0),
                hotkey=axon.hotkey,
                netuid=config.netuid,
                success=success,
                latency_ms=elapsed_ms,
                response_valid=response_valid,
                response_complete=response_complete,
                timestamp=datetime.now(UTC),
            )
        )

    async def execute(
        self,
        request_data: dict[str, Any],
        dendrite: bt.Dendrite,
        miner_selector: MinerSelector,
        scorer: "MinerScorer | None" = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Full request lifecycle. Returns (response_body, gateway_headers)."""
        config = self.get_config()
        start_time = time.monotonic()

        # 1. Select miner (raises SubnetUnavailableError if none)
        axon = miner_selector.select_miner(config.netuid)
        miner_uid = axon.hotkey[:MINER_UID_PREFIX_LEN]  # Safe prefix for logging/headers

        # 2. Build synapse
        synapse = self.to_synapse(request_data)

        # 3. Query miner via Dendrite
        try:
            responses = await dendrite.forward(
                axons=[axon],
                synapse=synapse,
                timeout=config.timeout_seconds,
            )
        except TimeoutError as exc:
            elapsed = time.monotonic() - start_time
            elapsed_ms = round(elapsed * 1000)
            self._record_score(scorer, axon, config, elapsed_ms, success=False)
            logger.warning(
                "dendrite_query_timeout",
                subnet=config.subnet_name,
                miner_uid=miner_uid,
                error=str(exc),
                elapsed_ms=elapsed_ms,
            )
            raise MinerTimeoutError(
                miner_uid=miner_uid, subnet=config.subnet_name
            ) from exc
        except Exception as exc:
            elapsed = time.monotonic() - start_time
            elapsed_ms = round(elapsed * 1000)
            self._record_score(scorer, axon, config, elapsed_ms, success=False)
            logger.warning(
                "dendrite_query_failed",
                subnet=config.subnet_name,
                miner_uid=miner_uid,
                error=str(exc),
                error_type=type(exc).__name__,
                elapsed_ms=elapsed_ms,
            )
            raise MinerInvalidResponseError(
                miner_uid=miner_uid, subnet=config.subnet_name
            ) from exc

        if not responses:
            elapsed_ms = round((time.monotonic() - start_time) * 1000)
            self._record_score(scorer, axon, config, elapsed_ms, success=False)
            raise MinerInvalidResponseError(
                miner_uid=miner_uid, subnet=config.subnet_name
            )
        response_synapse = responses[0]

        # 4. Validate response
        if response_synapse.is_timeout:
            elapsed_ms = round((time.monotonic() - start_time) * 1000)
            self._record_score(scorer, axon, config, elapsed_ms, success=False)
            raise MinerTimeoutError(
                miner_uid=miner_uid, subnet=config.subnet_name
            )
        if not response_synapse.is_success:
            elapsed_ms = round((time.monotonic() - start_time) * 1000)
            self._record_score(scorer, axon, config, elapsed_ms, success=False)
            raise MinerInvalidResponseError(
                miner_uid=miner_uid, subnet=config.subnet_name
            )

        # 5. Convert and sanitize — re-raise with actual miner_uid
        try:
            response_data = self.from_response(response_synapse, request_data)
            response_data = self.sanitize_output(response_data)
        except MinerInvalidResponseError as exc:
            elapsed_ms = round((time.monotonic() - start_time) * 1000)
            self._record_score(scorer, axon, config, elapsed_ms, success=False)
            if exc.miner_uid == "unknown":
                raise MinerInvalidResponseError(
                    miner_uid=miner_uid, subnet=config.subnet_name
                ) from exc
            raise

        elapsed_ms = round((time.monotonic() - start_time) * 1000)

        # 6. Record successful observation
        self._record_score(
            scorer, axon, config, elapsed_ms,
            success=True, response_valid=True, response_complete=True,
        )

        # 7. Gateway headers
        headers = {
            "X-TaoGateway-Miner-UID": miner_uid,
            "X-TaoGateway-Latency-Ms": str(elapsed_ms),
            "X-TaoGateway-Subnet": config.subnet_name,
        }

        return response_data, headers

    def to_streaming_synapse(
        self, request_data: dict[str, Any]
    ) -> bt.StreamingSynapse:
        """Convert API request to subnet-specific StreamingSynapse.
        Override in concrete adapters that support streaming."""
        raise NotImplementedError("Adapter does not support streaming")

    def format_stream_chunk(
        self, chunk: str, chunk_id: str, model: str, created: int,
        *, include_role: bool = False,
    ) -> str:
        """Format a raw miner chunk as an SSE data line.
        Override in concrete adapters that support streaming."""
        raise NotImplementedError("Adapter does not support streaming")

    def format_stream_done(
        self, chunk_id: str, model: str, created: int
    ) -> str:
        """Format the final stop chunk and [DONE] terminator.
        Override in concrete adapters that support streaming."""
        raise NotImplementedError("Adapter does not support streaming")

    async def execute_stream(
        self,
        request_data: dict[str, Any],
        dendrite: bt.Dendrite,
        miner_selector: MinerSelector,
        is_disconnected: Any = None,
        scorer: "MinerScorer | None" = None,
    ) -> tuple[dict[str, str], AsyncGenerator[str, None]]:
        """Streaming request lifecycle.

        Returns (gateway_headers, sse_generator) so the caller gets
        consistent headers without pre-selecting the miner.
        """
        config = self.get_config()
        axon = miner_selector.select_miner(config.netuid)
        miner_uid = axon.hotkey[:MINER_UID_PREFIX_LEN]

        headers = {
            "X-TaoGateway-Miner-UID": miner_uid,
            "X-TaoGateway-Subnet": config.subnet_name,
        }

        return headers, self._stream_generator(
            request_data, dendrite, axon, miner_uid, is_disconnected, scorer,
        )

    async def _stream_generator(
        self,
        request_data: dict[str, Any],
        dendrite: bt.Dendrite,
        axon: Any,
        miner_uid: str,
        is_disconnected: Any = None,
        scorer: "MinerScorer | None" = None,
    ) -> AsyncGenerator[str, None]:
        """Internal streaming generator. Yields SSE-formatted strings."""
        config = self.get_config()
        start_time = time.monotonic()
        chunk_id = generate_completion_id()
        created = int(time.time())
        model = str(request_data.get("model", "unknown"))

        # 1. Build streaming synapse
        synapse = self.to_streaming_synapse(request_data)

        # 2. Query miner with streaming=True
        try:
            responses = await dendrite.forward(
                axons=[axon],
                synapse=synapse,
                timeout=config.timeout_seconds,
                streaming=True,
            )
        except TimeoutError as exc:
            elapsed_ms = round((time.monotonic() - start_time) * 1000)
            self._record_score(scorer, axon, config, elapsed_ms, success=False)
            logger.warning(
                "dendrite_stream_timeout",
                subnet=config.subnet_name,
                miner_uid=miner_uid,
                error=str(exc),
            )
            yield self.sse_error("gateway_timeout", "Miner timed out", miner_uid)
            yield SSE_DONE
            return
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - start_time) * 1000)
            self._record_score(scorer, axon, config, elapsed_ms, success=False)
            logger.warning(
                "dendrite_stream_failed",
                subnet=config.subnet_name,
                miner_uid=miner_uid,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            yield self.sse_error("bad_gateway", "Miner communication error", miner_uid)
            yield SSE_DONE
            return

        if not responses:
            elapsed_ms = round((time.monotonic() - start_time) * 1000)
            self._record_score(scorer, axon, config, elapsed_ms, success=False)
            yield self.sse_error("bad_gateway", "Empty response", miner_uid)
            yield SSE_DONE
            return

        stream = responses[0]

        # 3. Yield latency comment and stream chunks
        first_chunk = True
        had_error = False
        client_disconnected = False
        try:
            async for chunk in stream:
                # Check client disconnect
                if is_disconnected is not None and await is_disconnected():
                    client_disconnected = True
                    logger.info(
                        "client_disconnected",
                        subnet=config.subnet_name,
                        miner_uid=miner_uid,
                    )
                    return

                chunk_text = chunk if isinstance(chunk, str) else str(chunk)
                if not chunk_text:
                    continue

                include_role = first_chunk
                if first_chunk:
                    ttft_ms = round((time.monotonic() - start_time) * 1000)
                    yield f": ttft_ms={ttft_ms}\n\n"
                    first_chunk = False

                yield self.format_stream_chunk(
                    chunk_text, chunk_id, model, created,
                    include_role=include_role,
                )
        except TimeoutError:
            had_error = True
            yield self.sse_error(
                "gateway_timeout", "Miner timed out mid-stream", miner_uid
            )
        except Exception as exc:
            had_error = True
            logger.warning(
                "stream_chunk_error",
                subnet=config.subnet_name,
                miner_uid=miner_uid,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            yield self.sse_error("bad_gateway", "Miner communication error", miner_uid)
        finally:
            elapsed_ms = round((time.monotonic() - start_time) * 1000)
            # Don't count client disconnects as full success — response wasn't completed
            if not client_disconnected:
                self._record_score(
                    scorer, axon, config, elapsed_ms,
                    success=not had_error,
                    response_valid=not had_error,
                    response_complete=True if not had_error else None,
                )
            logger.info(
                "stream_cleanup",
                subnet=config.subnet_name,
                miner_uid=miner_uid,
                had_error=had_error,
                client_disconnected=client_disconnected,
            )

        # 4. Send done — stop chunk only on success, [DONE] always
        if not had_error:
            yield self.format_stream_done(chunk_id, model, created)
        else:
            yield SSE_DONE

    @staticmethod
    def sse_error(error_type: str, message: str, miner_uid: str) -> str:
        """Format an SSE error event.

        miner_uid is accepted for structured logging but intentionally
        omitted from the client-facing payload (SEC-018).
        """
        logger.warning(
            "sse_error",
            error_type=error_type,
            message=message,
            miner_uid=miner_uid,
        )
        data = {
            "error": {
                "type": error_type,
                "message": message,
            }
        }
        return f"data: {json.dumps(data)}\n\n"
