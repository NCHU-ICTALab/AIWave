"""意圖判讀：把口語需求對應到服務目錄中的一項服務。

這是命題「需求理解」的入口——使用者說「浴室的燈不亮了」，而不是「我要水電修繕」。

分工同題組引擎（見 ADR-0016）：**LLM 只負責判讀**，回傳的 service id 一律用目錄驗證；
判讀不出或信心不足時回 `None`，由介面退回服務目錄，不硬猜。
"""

from __future__ import annotations

from dataclasses import dataclass

from core.clients import LlmClient
from core.forms.service_catalog import ServiceInfo, list_services

_SYSTEM = (
    "你是生活服務平台的需求判讀助理。使用者會用日常說法描述需求，"
    "你要從服務清單中挑出最合適的一項。"
    "只輸出一個 JSON 物件，不要多餘文字。"
    'schema：{"serviceId":"<服務 id 或 null>","confidence":"high|low","reason":"<12 字內的中文理由>"}。'
    "無法對應到清單中任何一項時，serviceId 必須是 null。"
)


@dataclass(frozen=True)
class IntentMatch:
    service_id: str
    service_name: str
    confidence: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "serviceId": self.service_id,
            "serviceName": self.service_name,
            "confidence": self.confidence,
            "reason": self.reason,
        }


class IntentAgent:
    def __init__(self, llm: LlmClient) -> None:
        self.llm = llm

    def match(self, need: str) -> IntentMatch | None:
        """回傳判讀到的服務；無法判讀時回 None（由介面退回目錄）。"""
        text = (need or "").strip()
        if not text:
            return None

        services = list_services()
        try:
            raw = self.llm.json([
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": self._prompt(services, text)},
            ])
        except Exception:  # noqa: BLE001 — 判讀失敗一律退回目錄，不阻斷使用者
            return None
        if not isinstance(raw, dict):
            return None

        service_id = raw.get("serviceId")
        if not isinstance(service_id, str):
            return None
        # LLM 回傳的 id 一律用目錄驗證，避免幻覺出不存在的服務
        service = next((s for s in services if s.id == service_id), None)
        if service is None:
            return None

        confidence = "high" if str(raw.get("confidence", "")).lower() == "high" else "low"
        return IntentMatch(
            service_id=service.id,
            service_name=service.name,
            confidence=confidence,
            reason=str(raw.get("reason") or "").strip(),
        )

    @staticmethod
    def _prompt(services: list[ServiceInfo], need: str) -> str:
        catalog = "\n".join(f"- {s.id}：{s.name}（{s.summary}）" for s in services)
        return f"服務清單：\n{catalog}\n\n使用者需求：「{need}」"
