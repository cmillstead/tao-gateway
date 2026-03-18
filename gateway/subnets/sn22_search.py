"""SN22 Desearch web search adapter."""

import uuid
from typing import Any
from urllib.parse import urlparse

import bittensor as bt
import structlog

from gateway.core.config import settings
from gateway.subnets.base import AdapterConfig, BaseAdapter

logger = structlog.get_logger()


class WebSearchSynapse(bt.Synapse):  # type: ignore[misc]
    """SN22 Desearch web search synapse.

    Source: GitHub Desearch-ai/subnet-22-desearch/desearch/protocol.py
    """

    query: str = ""
    num: int = 10
    start: int = 0
    # Response field (populated by miner)
    results: list[dict[str, Any]] = []
    required_hash_fields: list[str] = ["query"]


def _is_valid_url(url: str) -> bool:
    """Validate URL is well-formed HTTP(S)."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


class SN22SearchAdapter(BaseAdapter):
    """Thin adapter: search request <-> WebSearchSynapse."""

    def to_synapse(self, request_data: dict[str, Any]) -> WebSearchSynapse:
        return WebSearchSynapse(
            query=request_data["query"],
            num=request_data.get("num_results", 10),
            start=request_data.get("offset", 0),
        )

    def from_response(
        self, synapse: WebSearchSynapse, request_data: dict[str, Any]
    ) -> dict[str, Any]:
        raw_results = synapse.results if synapse.results else []

        results = []
        for item in raw_results:
            try:
                if isinstance(item, dict):
                    title = str(item.get("title", ""))
                    url = str(item.get("url", item.get("link", "")))
                    snippet = str(item.get("snippet", item.get("description", "")))
                else:
                    # Item might be a Pydantic model or similar
                    title = str(getattr(item, "title", ""))
                    url = str(getattr(item, "url", getattr(item, "link", "")))
                    snippet = str(getattr(item, "snippet", getattr(item, "description", "")))

                if url:  # Only include results with a URL
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "position": 0,  # Will be renumbered in sanitize
                    })
            except Exception:
                logger.debug("sn22_result_parse_skip", item_type=type(item).__name__)
                continue

        model = request_data.get("model", "tao-sn22")
        return {
            "id": f"search-{uuid.uuid4().hex[:24]}",
            "model": model,
            "query": request_data["query"],
            "results": results,
            "total_results": len(results),
        }

    def sanitize_output(self, response_data: dict[str, Any]) -> dict[str, Any]:
        valid_results = []
        for result in response_data.get("results", []):
            url = result.get("url", "")
            if not _is_valid_url(url):
                logger.debug("sn22_invalid_url_dropped", url=url[:100])
                continue

            # Sanitize text fields (miner content is untrusted)
            result["title"] = self.sanitize_text(result.get("title", ""))
            result["snippet"] = self.sanitize_text(result.get("snippet", ""))
            valid_results.append(result)

        # Re-number positions sequentially after dropping invalid results
        for i, result in enumerate(valid_results, start=1):
            result["position"] = i

        response_data["results"] = valid_results
        response_data["total_results"] = len(valid_results)
        return response_data

    def get_config(self) -> AdapterConfig:
        return AdapterConfig(
            netuid=settings.sn22_netuid,
            subnet_name="sn22-search",
            timeout_seconds=settings.sn22_timeout_seconds,
        )

    def get_capability(self) -> str:
        return "Web Search"

    def get_parameters(self) -> dict[str, str]:
        return {
            "query": "Search query (1-1000 chars)",
            "num_results": "Results to return (1-50, default 10)",
            "offset": "Pagination offset (default 0)",
        }
