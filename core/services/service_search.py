"""服務目錄的可重算語意檢索。

資料量只有九項，先採領域同義詞＋文字重疊，比向量資料庫更透明也更穩定。回傳匹配證據，
LLM 只負責理解語境，不能把零分服務塞進候選。
"""

from __future__ import annotations

from core.forms.service_catalog import ServiceInfo, list_services


def search(query: str, *, limit: int = 3) -> dict:
    text = query.strip().lower()
    if not text:
        return {"query": query, "confidence": "low", "matches": [], "computedBy": "catalog_rules"}
    scored: list[tuple[int, ServiceInfo, list[str]]] = []
    for service in list_services():
        matched = [term for term in service.search_terms if term.lower() in text]
        direct = service.name.lower() in text
        score = sum(4 + len(term) for term in matched) + (20 if direct else 0)
        if score:
            scored.append((score, service, matched or [service.name]))
    scored.sort(key=lambda row: (-row[0], row[1].id))
    top = scored[: max(1, min(limit, 5))]
    return {
        "query": query,
        "confidence": "high" if top and top[0][0] >= 6 else "low",
        "matches": [
            {
                "id": service.id,
                "name": service.name,
                "category": service.category,
                "summary": service.summary,
                "partner": service.partner,
                "score": score,
                "matchedTerms": evidence,
                "nextAction": "get_service_form",
            }
            for score, service, evidence in top
        ],
        "computedBy": "catalog_rules",
    }
