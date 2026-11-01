import json

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from rag.knowledge_base import get_knowledge_base


class GuideSearchInput(BaseModel):
    query: str = Field(description="The Toronto travel-guide question to search.")


def search_toronto_guide(query: str) -> str:
    documents = get_knowledge_base().search(query, k=4)
    return json.dumps({
        "source": "Toronto travel guide",
        "documents": [
            {
                "content": document.page_content,
                "source_file": document.metadata.get("source"),
            }
            for document in documents
        ],
    }, ensure_ascii=False)


def create_rag_tool() -> StructuredTool:
    return StructuredTool.from_function(
        func=search_toronto_guide,
        name="toronto_guide",
        description=(
            "Search the supplied Toronto guide for stable facts about attractions, "
            "neighborhoods, food, transport, itineraries, and travel advice. Use "
            "this instead of web search for general guide questions."
        ),
        args_schema=GuideSearchInput,
    )
