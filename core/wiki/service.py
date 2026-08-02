"""Loader and validator for the two isolated v4 knowledge domains.

The initial corpus is deliberately small.  Every answer is grounded in the
published files selected by domain, locale, region, and application version;
unknown content returns an explicit no-evidence response.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class WikiError(ValueError):
    pass


@dataclass(frozen=True)
class WikiArticle:
    id: str
    title: str
    domain: str
    status: str
    locale: str
    region: str
    app_version: str | None
    updated_at: str
    reviewed_by: str | None
    commercial_use: str
    push_eligible: bool
    sources: list[dict[str, Any]]
    body: str
    path: str

    def metadata(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "domain": self.domain,
            "status": self.status,
            "locale": self.locale,
            "region": self.region,
            "appVersion": self.app_version,
            "updatedAt": self.updated_at,
            "reviewedBy": self.reviewed_by,
            "commercialUse": self.commercial_use,
            "pushEligible": self.push_eligible,
            "sources": self.sources,
        }

    def context_entry(self) -> dict[str, Any]:
        return {**self.metadata(), "content": self.body}


class WikiService:
    PRODUCT_ROUTES = {
        "home", "points", "assistant", "services", "member", "orders", "calendar",
        "booking", "life-circle",
    }
    LIFE_ACTIONS = {"view-life-circle", "create-checklist", "create-task-draft"}

    def __init__(
        self,
        root: str | Path = "docs/knowledge",
        *,
        app_version: str = "0.1.0",
        locale: str = "zh-TW",
        region: str = "TW",
    ) -> None:
        self.root = Path(root)
        self.app_version = app_version
        self.locale = locale
        self.region = region
        self._articles = self._load()

    def _load(self) -> list[WikiArticle]:
        articles: list[WikiArticle] = []
        for path in sorted(self.root.glob("**/*.md")):
            if path.name.lower() == "readme.md":
                continue
            raw = path.read_text(encoding="utf-8")
            if not raw.startswith("---"):
                continue
            parts = raw.split("---", 2)
            if len(parts) != 3:
                continue
            try:
                metadata = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError as exc:
                raise WikiError(f"無法解析 Wiki front matter: {path}") from exc
            if not isinstance(metadata, dict):
                raise WikiError(f"Wiki front matter 必須是物件: {path}")
            domain = str(metadata.get("domain") or "")
            if domain not in {"life-guide", "product-help"}:
                raise WikiError(f"不支援的 Wiki domain: {path}")
            sources = metadata.get("sources") or []
            if not isinstance(sources, list) or not sources:
                raise WikiError(f"Wiki article 必須有 sources: {path}")
            article = WikiArticle(
                id=str(metadata.get("id") or ""),
                title=str(metadata.get("title") or path.stem),
                domain=domain,
                status=str(metadata.get("status") or "draft"),
                locale=str(metadata.get("locale") or ""),
                region=str(metadata.get("region") or ""),
                app_version=(None if metadata.get("app_version") is None else str(metadata.get("app_version"))),
                updated_at=str(metadata.get("updated_at") or ""),
                reviewed_by=(None if metadata.get("reviewed_by") is None else str(metadata.get("reviewed_by"))),
                commercial_use=str(metadata.get("commercial_use") or "prohibited"),
                push_eligible=bool(metadata.get("push_eligible", False)),
                sources=[dict(item) for item in sources if isinstance(item, dict)],
                body=parts[2].strip(),
                path=str(path),
            )
            if not article.id or article.status not in {"draft", "in-review", "published", "retired"}:
                raise WikiError(f"Wiki article id/status 無效: {path}")
            if article.status == "published" and not article.reviewed_by:
                raise WikiError(f"published Wiki article 必須有 reviewed_by: {path}")
            if article.status == "published" and any(
                str(source.get("license_or_permission") or "unknown") in {"unknown", "permission-required"}
                for source in article.sources
            ):
                raise WikiError(f"published Wiki article 的來源授權未確認: {path}")
            articles.append(article)
        return articles

    def published(self, domain: str) -> list[WikiArticle]:
        if domain not in {"life-guide", "product-help"}:
            raise WikiError(f"不支援的 Wiki domain: {domain}")
        return [
            article for article in self._articles
            if article.domain == domain
            and article.status == "published"
            and article.locale == self.locale
            and article.region == self.region
            and (article.app_version is None or article.app_version == self.app_version)
        ]

    def context(self, domain: str) -> list[dict[str, Any]]:
        return [article.context_entry() for article in self.published(domain)]

    def _article_map(self, domain: str) -> dict[str, WikiArticle]:
        return {article.id: article for article in self.published(domain)}

    def validate_product_output(self, payload: dict[str, Any]) -> dict[str, Any]:
        articles = self._article_map("product-help")
        citations = self._validate_citations(payload.get("citations") or [], articles, "product-help")
        actions = []
        for action in payload.get("navigationActions") or []:
            if not isinstance(action, dict) or str(action.get("routeId") or "") not in self.PRODUCT_ROUTES:
                raise WikiError("product-help navigation action 不在 allowlist")
            actions.append({"routeId": str(action["routeId"]), "label": str(action.get("label") or "前往功能")})
        return {
            "answer": str(payload.get("answer") or self.no_evidence()),
            "citations": citations,
            "navigationActions": actions,
            "limitations": [str(item) for item in (payload.get("limitations") or [])],
        }

    def validate_life_guide_output(self, payload: dict[str, Any]) -> dict[str, Any]:
        articles = self._article_map("life-guide")
        citations = self._validate_citations(payload.get("citations") or [], articles, "life-guide")
        items = []
        for item in payload.get("preparationItems") or []:
            if not isinstance(item, dict) or not str(item.get("name") or "").strip():
                raise WikiError("PreparationItem 必須有通用名稱")
            if item.get("sku") or item.get("price") or item.get("stock") or item.get("store"):
                raise WikiError("PreparationItem 不得包含 SKU、價格、庫存或門市")
            necessity = str(item.get("necessity") or "optional")
            if necessity not in {
                "common-required", "optional", "convenience", "cooperation-recommendation",
            }:
                raise WikiError("PreparationItem necessity 無效")
            cooperation_label = item.get("cooperationLabel")
            if necessity == "cooperation-recommendation" and not str(cooperation_label or "").strip():
                raise WikiError("合作推薦 PreparationItem 必須明確標示合作推薦")
            items.append({
                "name": str(item["name"]), "necessity": necessity,
                "quantityBasis": item.get("quantityBasis"),
                "limitations": [str(value) for value in (item.get("limitations") or [])],
                "cooperationLabel": str(cooperation_label).strip() if cooperation_label else None,
            })
        actions = []
        for action in payload.get("suggestedActions") or []:
            if not isinstance(action, dict) or str(action.get("type") or "") not in self.LIFE_ACTIONS:
                raise WikiError("life-guide suggested action 不在 allowlist")
            actions.append({"type": str(action["type"]), "label": str(action.get("label") or "下一步")})
        return {
            "answer": str(payload.get("answer") or self.no_evidence()),
            "citations": citations,
            "preparationItems": items,
            "suggestedActions": actions,
            "warnings": [str(item) for item in (payload.get("warnings") or [])],
        }

    def _validate_citations(
        self, citations: list[Any], articles: dict[str, WikiArticle], domain: str,
    ) -> list[dict[str, Any]]:
        validated = []
        for citation in citations:
            if not isinstance(citation, dict):
                raise WikiError("citation 形狀錯誤")
            article_id = str(citation.get("articleId") or "")
            if article_id not in articles or not article_id.startswith(f"{domain}."):
                raise WikiError("citation 指向未發布或錯誤知識域")
            validated.append({
                "articleId": article_id,
                "section": str(citation.get("section") or "全文"),
                "title": articles[article_id].title,
                "updatedAt": articles[article_id].updated_at,
                "domain": domain,
            })
        return validated

    def answer(self, domain: str, query: str) -> dict[str, Any]:
        articles = self.published(domain)
        normalized = query.casefold()
        matches = [article for article in articles if any(
            token and token in (article.title + article.body).casefold()
            for token in normalized.split()
        )]
        if not matches:
            return {
                "answer": self.no_evidence(), "citations": [],
                "preparationItems": [] if domain == "life-guide" else None,
                "suggestedActions": [] if domain == "life-guide" else None,
                "navigationActions": [] if domain == "product-help" else None,
                "limitations": [], "warnings": [],
            }
        article = matches[0]
        citation = {"articleId": article.id, "section": article.title}
        if domain == "product-help":
            return self.validate_product_output({
                "answer": article.body,
                "citations": [citation], "navigationActions": [], "limitations": [],
            })
        return self.validate_life_guide_output({
            "answer": article.body, "citations": [citation],
            "preparationItems": [], "suggestedActions": [], "warnings": [],
        })

    @staticmethod
    def no_evidence() -> str:
        return "目前沒有經確認的資料。"
