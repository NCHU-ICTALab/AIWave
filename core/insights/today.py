"""今日摘要：使用者打開 app 的第一個問題是「我現在該做什麼」。

[spec 08](../../docs/specs/08-product-experience.md) 的產品原則第一條就是這個，
§7.5 也把「需求側主動性」排在 AI 能力建置的第一順位。

**摘要由真實待辦算出，不是由 LLM 生成。** 沿用 [ADR-0011] 可解釋推薦的紀律：
規則決定「有哪些事、為什麼要提、多急」，每一則都指得出來源（諮詢單編號、團購活動、
官方訂單）。LLM 至多把這些潤飾成一句話，不參與判斷——否則畫面上會出現一件
使用者其實沒有的待辦，那比沒有摘要更糟。

排序依據是**誰在等誰**：
1. 卡在使用者身上的事最優先（廠商報好價了，等你點頭）——不處理就整條流程停住。
2. 有時限的事次之（團購快截止）——錯過就沒了。
3. 進行中的事再次之（已排程，只需知道）。
4. 沒有時限的建議最後（回訪提醒）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from core.community.group_buy import OPEN
from core.inquiries import CONFIRMED, PENDING_QUOTE, QUOTED

from .recommendations import recommend

#: 團購剩幾天內算「快截止」
CLOSING_SOON_DAYS = 3

# 分數只用來排序，數值本身不對外顯示——避免看起來像某種精算出來的優先度
_SCORE = {
    "needs_your_decision": 100,
    "closing_soon": 80,
    "in_progress": 50,
    "waiting_on_vendor": 40,
    "suggestion": 20,
}


@dataclass(frozen=True)
class BriefingItem:
    """今日摘要中的一則。"""

    id: str
    kind: str
    title: str
    detail: str
    #: 使用者可以做什麼；沒有動作時為 None（純告知）
    action_label: str | None = None
    action_route: str | None = None
    #: 這則從哪來——諮詢單編號、團購活動、官方訂單 record_id
    source: str = ""
    score: int = 0
    evidence: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "detail": self.detail,
            "actionLabel": self.action_label,
            "actionRoute": self.action_route,
            "source": self.source,
            "score": self.score,
            "evidence": list(self.evidence),
            "computedBy": "rules",
        }


def _days_until(value: str | None, today: date) -> int | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (moment.astimezone(timezone.utc).date() - today).days


def _inquiry_items(inquiries: list[dict]) -> list[BriefingItem]:
    items: list[BriefingItem] = []
    for record in inquiries:
        status = record.get("status")
        inquiry_id = str(record.get("id"))
        if status == QUOTED:
            quote = record.get("quote") or {}
            amount = quote.get("amount")
            vendor = quote.get("vendorName") or "合作廠商"
            items.append(
                BriefingItem(
                    id=f"quote-{inquiry_id}",
                    kind="needs_your_decision",
                    title="有一筆報價等你確認",
                    detail=f"{vendor}針對 {inquiry_id} 報價 NT${amount:,}，確認後才會排程施作。"
                    if isinstance(amount, int) else f"{vendor}已針對 {inquiry_id} 提出報價。",
                    action_label="查看報價",
                    action_route="/user/orders",
                    source=inquiry_id,
                    score=_SCORE["needs_your_decision"],
                    evidence=[{"type": "inquiry", "id": inquiry_id, "status": status}],
                )
            )
        elif status == CONFIRMED:
            items.append(
                BriefingItem(
                    id=f"scheduled-{inquiry_id}",
                    kind="in_progress",
                    title="已確認，等待師傅到場",
                    detail=f"{inquiry_id} 已排程，完工後會通知你。",
                    action_label="查看進度",
                    action_route="/user/orders",
                    source=inquiry_id,
                    score=_SCORE["in_progress"],
                    evidence=[{"type": "inquiry", "id": inquiry_id, "status": status}],
                )
            )
        elif status == PENDING_QUOTE:
            items.append(
                BriefingItem(
                    id=f"pending-{inquiry_id}",
                    kind="waiting_on_vendor",
                    title="等待廠商報價",
                    detail=f"{inquiry_id} 已送出，廠商回覆後會通知你。",
                    action_label="查看進度",
                    action_route="/user/orders",
                    source=inquiry_id,
                    score=_SCORE["waiting_on_vendor"],
                    evidence=[{"type": "inquiry", "id": inquiry_id, "status": status}],
                )
            )
    return items


def _group_buy_items(campaigns: list[dict], account_id: str, today: date) -> list[BriefingItem]:
    """只提**還沒跟、而且快截止**的團。

    已經跟過的團不需要再催——那不是待辦，是雜訊。
    """
    items: list[BriefingItem] = []
    for campaign in campaigns:
        if campaign.get("status") != OPEN:
            continue
        if any(join.get("account_id") == account_id for join in campaign.get("joins") or []):
            continue
        remaining = _days_until(campaign.get("closeTime"), today)
        if remaining is None or remaining < 0 or remaining > CLOSING_SOON_DAYS:
            continue
        when = "今天截止" if remaining == 0 else f"還剩 {remaining} 天"
        items.append(
            BriefingItem(
                id=f"groupbuy-{campaign.get('id')}",
                kind="closing_soon",
                title=f"社區團購「{campaign.get('title')}」{when}",
                detail=f"{campaign.get('itemName')} 每{campaign.get('unit')} NT${campaign.get('unitPrice'):,}，"
                f"目前 {campaign.get('householdCount')} 戶跟團。",
                action_label="去跟團",
                action_route="/user/community",
                source=f"campaign-{campaign.get('id')}",
                score=_SCORE["closing_soon"] + max(0, CLOSING_SOON_DAYS - remaining),
                evidence=[{"type": "campaign", "id": campaign.get("id"), "closeTime": campaign.get("closeTime")}],
            )
        )
    return items


def _recommendation_items(account_id: str, today: date, limit: int) -> list[BriefingItem]:
    return [
        BriefingItem(
            id=f"rec-{rec.id}",
            kind="suggestion",
            title=rec.title,
            detail=rec.reason_text,
            action_label="安排服務",
            action_route=f"/user/services/{rec.service_id.replace('service-', '')}" if rec.service_id else None,
            source=rec.id,
            score=_SCORE["suggestion"],
            evidence=[item.to_dict() for item in rec.evidence],
        )
        for rec in recommend(account_id, today=today, limit=limit)
    ]


def build_briefing(
    *,
    account_id: str | None,
    inquiries: list[dict],
    campaigns: list[dict],
    today: date,
    limit: int = 5,
) -> list[BriefingItem]:
    """彙整今天該知道的事，依「誰在等誰」排序。

    `account_id` 為 None（全新使用者）時只會有團購這類公開事項——
    新帳號真的沒有待辦，這時候應該由零狀態負責教學，不是塞假資料（spec 08）。
    """
    items: list[BriefingItem] = []
    if account_id:
        items += _inquiry_items([r for r in inquiries if r.get("account_id") == account_id])
        items += _group_buy_items(campaigns, account_id, today)
        items += _recommendation_items(account_id, today, limit)

    items.sort(key=lambda item: (-item.score, item.id))
    return items[:limit]
