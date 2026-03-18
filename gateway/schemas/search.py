"""Pydantic schemas for web search (SN22)."""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    model: str = Field(default="tao-sn22", min_length=1, max_length=64)
    query: str = Field(..., min_length=1, max_length=1000)
    num_results: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    position: int


class SearchResponse(BaseModel):
    id: str
    model: str
    query: str
    results: list[SearchResult]
    total_results: int
