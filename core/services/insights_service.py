"""個人洞察應用邊界：行為軌跡、消費摘要、可解釋推薦。

HTTP 與（未來）personal-intelligence MCP 都經此層，不直接碰資料模組。
資料一律來自官方 `mms_order_record` 範例，畫面上的數字因此都指得出來源。
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from core.data.official_orders import list_accounts, orders_for
from core.insights import build_trail, recommend, summarize

# 展示用主 persona：官方資料中同時具備「跨服務歷史」與「未完成訂單」的帳號，
# 未完成的水電修繕正好接上諮詢單→報價流程。
DEMO_ACCOUNT_ID = "019a52d3-7f6b-7da3-b48d-9c9e2522d616"


class InsightsService:
    def __init__(self, *, today: date, default_account_id: str = DEMO_ACCOUNT_ID) -> None:
        self.today = today
        self.default_account_id = default_account_id

    def _resolve(self, account_id: str | None) -> str:
        """`me` 或未指定時解析為展示 persona；正式環境改為登入者。"""
        if account_id in (None, "", "me"):
            return self.default_account_id
        return account_id  # type: ignore[return-value]

    def accounts(self) -> list[dict]:
        """官方資料中可登入的既有使用者，附行為描述供登入頁辨識。"""
        result = []
        for account_id in list_accounts():
            orders = orders_for(account_id)
            usage = Counter(order.service_name for order in orders)
            top_service, top_count = usage.most_common(1)[0] if usage else ("", 0)
            result.append({
                "accountId": account_id,
                "orderCount": len(orders),
                "serviceCount": len(usage),
                "openCount": sum(1 for o in orders if o.is_open),
                "topService": top_service,
                "topServiceCount": top_count,
                "isDefault": account_id == self.default_account_id,
            })
        result.sort(key=lambda row: (-row["serviceCount"], -row["orderCount"]))
        return result

    def summary(self, account_id: str | None = None) -> dict:
        return summarize(self._resolve(account_id), today=self.today).to_dict()

    def trail(self, account_id: str | None = None) -> list[dict]:
        return [event.to_dict() for event in build_trail(self._resolve(account_id))]

    def recommendations(self, account_id: str | None = None, *, limit: int = 3) -> list[dict]:
        return [
            rec.to_dict()
            for rec in recommend(self._resolve(account_id), today=self.today, limit=limit)
        ]
