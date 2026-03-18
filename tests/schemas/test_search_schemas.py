"""Tests for search request/response schemas (Story 7-3)."""

import pytest
from pydantic import ValidationError

from gateway.schemas.search import SearchRequest, SearchResponse, SearchResult


class TestSearchRequest:
    """Test SearchRequest validation."""

    def test_valid_basic_query(self) -> None:
        req = SearchRequest(query="bittensor subnets")
        assert req.query == "bittensor subnets"
        assert req.model == "tao-sn22"
        assert req.num_results == 10
        assert req.offset == 0

    def test_custom_params(self) -> None:
        req = SearchRequest(query="test", num_results=20, offset=10)
        assert req.num_results == 20
        assert req.offset == 10

    def test_rejects_empty_query(self) -> None:
        with pytest.raises(ValidationError, match="too_short"):
            SearchRequest(query="")

    def test_rejects_query_too_long(self) -> None:
        with pytest.raises(ValidationError, match="too_long"):
            SearchRequest(query="x" * 1001)

    def test_accepts_max_length_query(self) -> None:
        req = SearchRequest(query="x" * 1000)
        assert len(req.query) == 1000

    def test_rejects_num_results_too_high(self) -> None:
        with pytest.raises(ValidationError, match="less_than_equal"):
            SearchRequest(query="test", num_results=51)

    def test_rejects_num_results_zero(self) -> None:
        with pytest.raises(ValidationError, match="greater_than_equal"):
            SearchRequest(query="test", num_results=0)

    def test_rejects_negative_offset(self) -> None:
        with pytest.raises(ValidationError, match="greater_than_equal"):
            SearchRequest(query="test", offset=-1)

    def test_rejects_empty_model(self) -> None:
        with pytest.raises(ValidationError, match="too_short"):
            SearchRequest(query="test", model="")


class TestSearchResult:
    """Test SearchResult schema."""

    def test_valid_result(self) -> None:
        result = SearchResult(
            title="Example", url="https://example.com", snippet="A result", position=1,
        )
        assert result.title == "Example"
        assert result.position == 1


class TestSearchResponse:
    """Test SearchResponse schema."""

    def test_valid_response(self) -> None:
        resp = SearchResponse(
            id="search-abc123",
            model="tao-sn22",
            query="test",
            results=[
                SearchResult(
                    title="R1", url="https://r1.com", snippet="S1", position=1,
                )
            ],
            total_results=1,
        )
        assert resp.total_results == 1

    def test_empty_results(self) -> None:
        resp = SearchResponse(
            id="search-abc", model="tao-sn22", query="test",
            results=[], total_results=0,
        )
        assert resp.results == []
