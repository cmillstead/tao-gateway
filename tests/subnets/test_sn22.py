"""Tests for SN22 Web Search adapter (Story 7-3).

Uses real Postgres and Redis per CLAUDE.md. Only Bittensor SDK is mocked
at conftest level (paid external network).
"""

from typing import Any

from gateway.subnets.sn22_search import SN22SearchAdapter, WebSearchSynapse, _is_valid_url


class TestWebSearchSynapse:
    """Test WebSearchSynapse creation and field defaults."""

    def test_default_fields(self) -> None:
        synapse = WebSearchSynapse()
        assert synapse.query == ""
        assert synapse.num == 10
        assert synapse.start == 0

    def test_with_query(self) -> None:
        synapse = WebSearchSynapse(query="bittensor subnets", num=20, start=5)
        assert synapse.query == "bittensor subnets"
        assert synapse.num == 20
        assert synapse.start == 5

    def test_required_hash_fields(self) -> None:
        synapse = WebSearchSynapse()
        assert synapse.required_hash_fields == ["query"]


class TestIsValidUrl:
    """Test URL validation helper."""

    def test_valid_http(self) -> None:
        assert _is_valid_url("http://example.com") is True

    def test_valid_https(self) -> None:
        assert _is_valid_url("https://example.com/path?q=1") is True

    def test_invalid_ftp(self) -> None:
        assert _is_valid_url("ftp://example.com") is False

    def test_invalid_no_scheme(self) -> None:
        assert _is_valid_url("example.com") is False

    def test_invalid_empty(self) -> None:
        assert _is_valid_url("") is False

    def test_invalid_javascript(self) -> None:
        assert _is_valid_url("javascript:alert(1)") is False

    def test_invalid_data_uri(self) -> None:
        assert _is_valid_url("data:text/html,<h1>hi</h1>") is False


class TestSN22SearchAdapterToSynapse:
    """Test to_synapse() field mapping."""

    def setup_method(self) -> None:
        self.adapter = SN22SearchAdapter()

    def test_basic_query(self) -> None:
        synapse = self.adapter.to_synapse({"query": "test query"})
        assert isinstance(synapse, WebSearchSynapse)
        assert synapse.query == "test query"
        assert synapse.num == 10
        assert synapse.start == 0

    def test_custom_num_and_offset(self) -> None:
        synapse = self.adapter.to_synapse({
            "query": "test",
            "num_results": 20,
            "offset": 10,
        })
        assert synapse.num == 20
        assert synapse.start == 10


class TestSN22SearchAdapterFromResponse:
    """Test from_response() defensive parsing."""

    def setup_method(self) -> None:
        self.adapter = SN22SearchAdapter()

    def _make_synapse_with_results(self, results: list[dict[str, str]]) -> WebSearchSynapse:
        return WebSearchSynapse(query="test", results=results)

    def test_dict_results(self) -> None:
        synapse = self._make_synapse_with_results([
            {"title": "Result 1", "url": "https://example.com", "snippet": "A snippet"},
            {"title": "Result 2", "url": "https://other.com", "snippet": "Another"},
        ])
        result = self.adapter.from_response(synapse, {"query": "test", "model": "tao-sn22"})

        assert result["id"].startswith("search-")
        assert result["model"] == "tao-sn22"
        assert result["query"] == "test"
        assert len(result["results"]) == 2
        assert result["results"][0]["title"] == "Result 1"
        assert result["results"][0]["url"] == "https://example.com"

    def test_empty_results(self) -> None:
        synapse = WebSearchSynapse(query="test")
        result = self.adapter.from_response(synapse, {"query": "test", "model": "tao-sn22"})

        assert result["results"] == []
        assert result["total_results"] == 0

    def test_link_field_fallback(self) -> None:
        """Results using 'link' instead of 'url' are handled."""
        synapse = self._make_synapse_with_results([
            {"title": "R", "link": "https://example.com", "description": "D"},
        ])
        result = self.adapter.from_response(synapse, {"query": "test", "model": "tao-sn22"})
        assert result["results"][0]["url"] == "https://example.com"
        assert result["results"][0]["snippet"] == "D"

    def test_results_without_url_are_skipped(self) -> None:
        synapse = self._make_synapse_with_results([
            {"title": "No URL", "url": "", "snippet": "Skip me"},
            {"title": "Has URL", "url": "https://ok.com", "snippet": "Keep me"},
        ])
        result = self.adapter.from_response(synapse, {"query": "test", "model": "tao-sn22"})
        assert len(result["results"]) == 1
        assert result["results"][0]["url"] == "https://ok.com"


class TestSN22SearchAdapterSanitize:
    """Test sanitize_output() URL validation, HTML stripping, position renumbering."""

    def setup_method(self) -> None:
        self.adapter = SN22SearchAdapter()

    def _make_response(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "id": "search-test",
            "model": "tao-sn22",
            "query": "test",
            "results": results,
            "total_results": len(results),
        }

    def test_valid_urls_kept(self) -> None:
        data = self._make_response([
            {"title": "T", "url": "https://example.com", "snippet": "S", "position": 0},
        ])
        result = self.adapter.sanitize_output(data)
        assert len(result["results"]) == 1

    def test_invalid_urls_dropped(self) -> None:
        data = self._make_response([
            {"title": "Good", "url": "https://good.com", "snippet": "S", "position": 0},
            {"title": "Bad", "url": "ftp://bad.com", "snippet": "S", "position": 0},
            {"title": "Worse", "url": "not-a-url", "snippet": "S", "position": 0},
        ])
        result = self.adapter.sanitize_output(data)
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "Good"
        assert result["total_results"] == 1

    def test_html_stripped_from_title_and_snippet(self) -> None:
        data = self._make_response([
            {
                "title": "<b>Bold Title</b>",
                "url": "https://example.com",
                "snippet": "<script>alert(1)</script>Safe text",
                "position": 0,
            },
        ])
        result = self.adapter.sanitize_output(data)
        assert "<b>" not in result["results"][0]["title"]
        assert "<script>" not in result["results"][0]["snippet"]
        assert "Bold Title" in result["results"][0]["title"]
        assert "Safe text" in result["results"][0]["snippet"]

    def test_positions_renumbered_sequentially(self) -> None:
        data = self._make_response([
            {"title": "A", "url": "https://a.com", "snippet": "S", "position": 0},
            {"title": "B", "url": "ftp://invalid", "snippet": "S", "position": 0},
            {"title": "C", "url": "https://c.com", "snippet": "S", "position": 0},
        ])
        result = self.adapter.sanitize_output(data)
        assert len(result["results"]) == 2
        assert result["results"][0]["position"] == 1
        assert result["results"][1]["position"] == 2

    def test_empty_results_valid(self) -> None:
        data = self._make_response([])
        result = self.adapter.sanitize_output(data)
        assert result["results"] == []
        assert result["total_results"] == 0


class TestSN22SearchAdapterConfig:
    """Test get_config(), get_capability(), get_parameters()."""

    def setup_method(self) -> None:
        self.adapter = SN22SearchAdapter()

    def test_config(self) -> None:
        config = self.adapter.get_config()
        assert config.netuid == 22
        assert config.subnet_name == "sn22-search"
        assert config.timeout_seconds == 30

    def test_capability(self) -> None:
        assert self.adapter.get_capability() == "Web Search"

    def test_parameters(self) -> None:
        params = self.adapter.get_parameters()
        assert "query" in params
        assert "num_results" in params
        assert "offset" in params
