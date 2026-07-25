"""社區服務應用邊界：團購的開團、跟團與結單。

住戶與管委會呼叫的是同一組資料，只是可做的動作不同——社區是共享範圍，不是兩套系統。
"""

from __future__ import annotations

from core.community import OPEN, GroupBuyRepository


class CommunityService:
    def __init__(self, group_buys: GroupBuyRepository) -> None:
        self.group_buys = group_buys

    # ---- 住戶 ----------------------------------------------------------

    def list_open_campaigns(self) -> list[dict]:
        """住戶端：可以參加的團購。"""
        return self.group_buys.list_campaigns(status=OPEN)

    def join_campaign(self, campaign_id: int, *, account_id: str, display_name: str, quantity: int) -> dict:
        return self.group_buys.join(
            campaign_id, account_id=account_id, display_name=display_name, quantity=quantity
        )

    def my_participation(self, account_id: str) -> list[dict]:
        """住戶端：我跟過的團與目前狀態。"""
        mine = []
        for campaign in self.group_buys.list_campaigns():
            joined = next((join for join in campaign["joins"] if join["account_id"] == account_id), None)
            if joined:
                mine.append({**campaign, "myQuantity": joined["quantity"]})
        return mine

    # ---- 管委會 --------------------------------------------------------

    def list_all_campaigns(self) -> list[dict]:
        return self.group_buys.list_campaigns()

    def create_campaign(self, **kwargs) -> dict:
        return self.group_buys.create_campaign(**kwargs)

    def close_campaign(self, campaign_id: int) -> dict:
        return self.group_buys.close_campaign(campaign_id)

    def purchase_order(self, campaign_id: int) -> dict | None:
        """結單後給廠商的採購彙總。"""
        campaign = self.group_buys.get_campaign(campaign_id)
        if campaign is None:
            return None
        return {
            "campaignId": campaign["id"],
            "itemName": campaign["itemName"],
            "unitPrice": campaign["unitPrice"],
            "totalQuantity": campaign["totalQuantity"],
            "totalAmount": campaign["totalAmount"],
            "householdCount": campaign["householdCount"],
            "households": [
                {"name": join["display_name"], "quantity": join["quantity"]}
                for join in campaign["joins"]
            ],
        }
