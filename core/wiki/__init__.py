"""Small, version-filtered LLM Wiki for the competition corpus."""

from .service import WikiArticle, WikiError, WikiService

__all__ = ["WikiArticle", "WikiError", "WikiService"]
