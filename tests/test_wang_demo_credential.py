"""王小明（主要展示住戶）的 Bearer 必須打得通住戶端實際會呼叫的每一支 API。

`tests/test_demo_capabilities.py` 已經證明憑證解析得出 principal，但使用者回報的
「小明沒有憑證、存取不到後端」不是憑證解不開——是住戶頁載入時有端點回非 2xx，
前端把它顯示成「請確認後端服務是否啟動」。因此這裡驗的是**整條請求路徑**：
把 `web/app/src/views/*` 在住戶路由掛載時真的會打的端點列出來，逐一以王小明的
Bearer 驅動，任何一支非 2xx 就是回歸。

端點清單來源（住戶登入後會停留的頁面）：

| 路由 | View | 呼叫 |
| --- | --- | --- |
| `/user` | TodayView | insights summary／today、life-tasks、points、calendar、notifications |
| `/user/community` | CommunityHubView → CommunityBoardView | communities、announcements、campaigns、my-participation、groups/joint-services、groups |
| `/user/points` | PointsView | points、restock-plan |
| `/user/orders` | OrdersView | inquiries、orders、life-tasks、bookings、commerce-orders、support/tickets |
| `/user/calendar` | CalendarView | calendar/events |
| `/user/wellbeing` | WellbeingView | care/messages、agent/task-packages、outcomes |
| `/user/life-circle` | ReachabilityView | reachability/area |
| `/user/assistant` | AssistantView | agent/sessions、agent/sessions/latest |
| `/user/services` | ServicesView | services、catalog/providers、catalog/listings |
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import create_app


WANG = {"Authorization": "Bearer aiwave-demo-resident"}
WANG_ACCOUNT = "household-wang-xiaoming"

#: 住戶端在王小明身上會發出的 GET，照畫面載入順序排。
RESIDENT_GET_ENDPOINTS = (
    # 身分
    "/api/v1/auth/me",
    "/api/v1/auth/workspaces",
    # 今日／洞察
    f"/api/v1/insights/{WANG_ACCOUNT}/summary",
    f"/api/v1/insights/{WANG_ACCOUNT}/trail",
    f"/api/v1/insights/{WANG_ACCOUNT}/recommendations",
    f"/api/v1/today/{WANG_ACCOUNT}",
    f"/api/v1/personalization/{WANG_ACCOUNT}/restock-plan",
    f"/api/v1/personalization/{WANG_ACCOUNT}/reminders",
    # 社區（公告需要 community membership，不是只有 Bearer）
    "/api/v1/platform/communities",
    "/api/v1/platform/communities/community-sunshine/announcements",
    "/api/v1/community/campaigns",
    "/api/v1/community/my-participation",
    "/api/v1/groups",
    "/api/v1/groups/joint-services",
    # 訂單與客服
    "/api/v1/inquiries",
    "/api/v1/orders",
    "/api/v1/life-tasks",
    "/api/v1/platform/bookings",
    "/api/v1/platform/commerce-orders",
    "/api/v1/platform/task-drafts",
    "/api/v1/support/tickets",
    # 點數、行事曆、通知
    "/api/v1/platform/points",
    "/api/v1/platform/calendar/events",
    "/api/v1/platform/notifications",
    # 主動照護／生活任務包／成果
    "/api/v1/platform/care/messages",
    "/api/v1/platform/agent/task-packages",
    "/api/v1/platform/outcomes",
    # AI 管家
    "/api/v1/platform/agent/sessions",
    "/api/v1/platform/agent/sessions/latest",
    # 服務探索
    "/api/v1/services",
    "/api/v1/platform/catalog/providers",
    "/api/v1/platform/catalog/listings",
)


@pytest.fixture(scope="module")
def client(tmp_path_factory) -> TestClient:
    database = tmp_path_factory.mktemp("wang") / "demo.sqlite3"
    return TestClient(create_app(demo_db_path=database))


@pytest.mark.parametrize("path", RESIDENT_GET_ENDPOINTS)
def test_resident_ui_endpoints_answer_the_wang_bearer(client: TestClient, path: str) -> None:
    response = client.get(path, headers=WANG)

    assert response.status_code < 300, f"{path} → {response.status_code} {response.text[:200]}"


def test_wang_is_a_member_of_the_demo_community(client: TestClient) -> None:
    """社區是住戶共享的**範圍**（ADR-0003）：主要展示住戶必須真的屬於陽光社區。

    少了這筆 membership，`/user/community` 讀公告會拿到 403，畫面顯示
    「請確認後端服務是否啟動」——使用者看到的就是「存取不到後端」。
    """
    rows = client.get("/api/v1/platform/communities", headers=WANG).json()["data"]
    sunshine = next(row for row in rows if row["id"] == "community-sunshine")

    assert sunshine["membership"] == {"role": "resident", "status": "active", "isDefault": True}
    assert client.get(
        "/api/v1/platform/communities/community-sunshine/announcements", headers=WANG,
    ).status_code == 200


def test_wang_can_write_as_a_resident(client: TestClient) -> None:
    """住戶端的寫入動作（開團）也要走得通，不是只有讀得到。"""
    opened = client.post(
        "/api/v1/community/campaigns",
        headers=WANG,
        json={"title": "王小明的社區團", "item_name": "茶裏王", "unit_price": 828},
    )

    assert opened.status_code == 200
    campaign_id = opened.json()["data"]["id"]
    mine = client.get("/api/v1/community/campaigns", headers=WANG).json()["data"]
    assert campaign_id in {row["id"] for row in mine}


def test_missing_or_unknown_bearer_is_the_only_no_credential_case(client: TestClient) -> None:
    """「沒有憑證」只該發生在真的沒帶 header 時；帶了王小明的憑證就不該是 401。"""
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=WANG).status_code == 200
