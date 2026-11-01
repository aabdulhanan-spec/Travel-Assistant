import json
from datetime import datetime, timezone

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class WebSearchInput(BaseModel):
    query: str = Field(
        description=(
            "A specific current travel query for any destination, such as "
            "attractions, opening hours, admission prices, or temporary closures."
        )
    )
    max_results: int = Field(default=5, ge=1, le=8)


def search_web(query: str, max_results: int = 5) -> str:
    if not query.strip():
        return json.dumps({"error": "A search query is required."})
    try:
        from duckduckgo_search import DDGS
        from duckduckgo_search.exceptions import DuckDuckGoSearchException
    except ImportError as exc:
        raise RuntimeError(
            "DuckDuckGo search support is missing. Install the project requirements."
        ) from exc

    try:
        results = DDGS().text(query, max_results=max(1, min(max_results, 8)))
    except DuckDuckGoSearchException as exc:
        return json.dumps({
            "query": query,
            "error": f"Live web search failed: {exc}",
            "source": "DuckDuckGo",
        })

    return json.dumps({
        "query": query,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "DuckDuckGo search results; confirm details at the linked source.",
        "results": [
            {
                "title": item.get("title"),
                "url": item.get("href") or item.get("url"),
                "snippet": item.get("body") or item.get("snippet"),
            }
            for item in results
        ],
        "notice": (
            "Search snippets are not authoritative. Treat prices and hours as "
            "unverified until confirmed on the linked official source."
        ),
    }, ensure_ascii=False)


def create_web_search_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=search_web,
        name="web_search",
        description=(
            "Search the live web for current attraction opening hours, ticket "
            "prices, closures, and travel updates. Include the result URLs in "
            "your response and distinguish search snippets from verified facts."
        ),
        args_schema=WebSearchInput,
    )
