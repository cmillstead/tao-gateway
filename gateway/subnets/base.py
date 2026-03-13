import json
import re
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import bittensor as bt
import structlog

from gateway.core.exceptions import (
    MinerInvalidResponseError,
    MinerTimeoutError,
)
from gateway.routing.selector import MinerSelector

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

    # Dangerous HTML tags that could execute code or load external content
    _DANGEROUS_TAGS_RE = re.compile(
        r"<\s*/?\s*(?:script|iframe|object|embed|form|input|button|textarea"
        r"|select|style|link|meta|base|applet|svg)\b[^>]*>",
        re.IGNORECASE | re.DOTALL,
    )
    # Content between script/style tags (strip payload, not just the tags)
    _DANGEROUS_CONTENT_RE = re.compile(
        r"<\s*(?:script|style)\b[^>]*>.*?<\s*/\s*(?:script|style)\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    # Event handler attributes on any tag (onerror, onload, onclick, etc.)
    _EVENT_HANDLER_RE = re.compile(
        r"<([^>]*?\s)on\w+\s*=[^>]*>",
        re.IGNORECASE,
    )
    # javascript: protocol in attributes
    _JS_PROTOCOL_RE = re.compile(
        r"<[^>]*\s(?:href|src|action)\s*=\s*[\"']?\s*javascript\s*:[^>]*>",
        re.IGNORECASE,
    )

    def sanitize_text(self, text: str) -> str:
        """Sanitize a single text string using shared dangerous-tag regexes."""
        if not isinstance(text, str):
            return str(text) if text is not None else ""
        text = self._DANGEROUS_CONTENT_RE.sub("", text)
        text = self._DANGEROUS_TAGS_RE.sub("", text)
        text = self._EVENT_HANDLER_RE.sub("", text)
        text = self._JS_PROTOCOL_RE.sub("", text)
        return text.replace("\x00", "")

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

    async def execute(
        self,
        request_data: dict[str, Any],
        dendrite: bt.Dendrite,
        miner_selector: MinerSelector,
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
            logger.warning(
                "dendrite_query_timeout",
                subnet=config.subnet_name,
                miner_uid=miner_uid,
                error=str(exc),
                elapsed_ms=round(elapsed * 1000),
            )
            raise MinerTimeoutError(
                miner_uid=miner_uid, subnet=config.subnet_name
            ) from exc
        except Exception as exc:
            elapsed = time.monotonic() - start_time
            logger.warning(
                "dendrite_query_failed",
                subnet=config.subnet_name,
                miner_uid=miner_uid,
                error=str(exc),
                error_type=type(exc).__name__,
                elapsed_ms=round(elapsed * 1000),
            )
            raise MinerInvalidResponseError(
                miner_uid=miner_uid, subnet=config.subnet_name
            ) from exc

        if not responses:
            raise MinerInvalidResponseError(
                miner_uid=miner_uid, subnet=config.subnet_name
            )
        response_synapse = responses[0]

        # 4. Validate response
        if response_synapse.is_timeout:
            raise MinerTimeoutError(
                miner_uid=miner_uid, subnet=config.subnet_name
            )
        if not response_synapse.is_success:
            raise MinerInvalidResponseError(
                miner_uid=miner_uid, subnet=config.subnet_name
            )

        # 5. Convert and sanitize
        response_data = self.from_response(response_synapse, request_data)
        response_data = self.sanitize_output(response_data)

        elapsed_ms = round((time.monotonic() - start_time) * 1000)

        # 6. Gateway headers
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
            request_data, dendrite, axon, miner_uid, is_disconnected,
        )

    async def _stream_generator(
        self,
        request_data: dict[str, Any],
        dendrite: bt.Dendrite,
        axon: Any,
        miner_uid: str,
        is_disconnected: Any = None,
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
            logger.warning(
                "dendrite_stream_failed",
                subnet=config.subnet_name,
                miner_uid=miner_uid,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            yield self.sse_error("bad_gateway", str(exc), miner_uid)
            yield SSE_DONE
            return

        if not responses:
            yield self.sse_error("bad_gateway", "Empty response", miner_uid)
            yield SSE_DONE
            return

        stream = responses[0]

        # 3. Yield latency comment and stream chunks
        first_chunk = True
        had_error = False
        try:
            async for chunk in stream:
                # Check client disconnect
                if is_disconnected is not None and await is_disconnected():
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
            yield self.sse_error("bad_gateway", str(exc), miner_uid)
        finally:
            logger.info(
                "stream_cleanup",
                subnet=config.subnet_name,
                miner_uid=miner_uid,
                had_error=had_error,
            )

        # 4. Send done — stop chunk only on success, [DONE] always
        if not had_error:
            yield self.format_stream_done(chunk_id, model, created)
        else:
            yield SSE_DONE

    @staticmethod
    def sse_error(error_type: str, message: str, miner_uid: str) -> str:
        """Format an SSE error event."""
        data = {
            "error": {
                "type": error_type,
                "message": message,
                "miner_uid": miner_uid,
            }
        }
        return f"data: {json.dumps(data)}\n\n"
