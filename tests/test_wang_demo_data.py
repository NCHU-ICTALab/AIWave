"""王小明（主要展示住戶）的儀表板必須有資料，而且要說得出資料是怎麼來的。

`tests/test_wang_demo_credential.py` 證明了他的 Bearer 打得通每一支住戶端 API，
但那時候每一支都回**格式正確的空 200**：訂單 0 筆、行為軌跡 0 筆、點數 0 點。
誠實但沒用——評審看到的首頁 KPI 整排是 0。原因是 `household-wang-xiaoming`
不是官方帳號，`orders_for()` 展不出任何官方訂單。

修法是沿用既有的那條縫（`accounts_for_persona()` → `orders_for()`），
把他也組成一位展示住戶，**重用**既有的官方帳號。因此這組測試守兩件事：

1. **有資料**——摘要／軌跡／推薦／今日摘要／點數都不是空的（回歸空儀表板的哨兵）；
2. **標示得出來**——那些訂單是重用組出來的，API 必須帶 `demo_composition`，
   不可讓人以為系統用行為指紋算出王小明就是那幾個官方帳號。

第 2 點比第 1 點重要：把數字填滿卻不標示來源，比空著更糟。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.data.personas import WANG_XIAOMING_ID

WANG = {"Authorization": "Bearer aiwave-demo-resident"}


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    database: Path = tmp_path_factory.mktemp("wang-data") / "demo.sqlite3"
    return TestClient(create_app(demo_db_path=database))


def _data(client: TestClient, path: str):
    response = client.get(path, headers=WANG)
    assert response.status_code == 200, f"{path} → {response.status_code} {response.text[:200]}"
    return response.json()["data"]


class TestDashboardIsNotEmpty:
    """首頁四塊資料都要有東西——這是「空儀表板」的回歸哨兵。"""

    def test_summary_has_real_cross_service_numbers(self, client: TestClient) -> None:
        summary = _data(client, f"/api/v1/insights/{WANG_XIAOMING_ID}/summary")

        assert summary["totalOrders"] > 0
        assert summary["distinctServices"] >= 3, "跨服務是這個產品的價值主張"
        assert summary["openOrders"] > 0, "要有進行中的事，首頁才有得追"
        assert summary["totalSpend"] > 0
        assert summary["lastActivity"] is not None
        # 金額仍然是各服務加總算出來的，沒有另外寫死的 KPI
        assert summary["totalSpend"] == sum(usage["totalAmount"] for usage in summary["services"])

    def test_trail_is_non_empty_and_traceable_to_official_records(self, client: TestClient) -> None:
        trail = _data(client, f"/api/v1/insights/{WANG_XIAOMING_ID}/trail")

        assert len(trail) > 0
        assert len({event["serviceName"] for event in trail}) >= 3
        assert all(event["recordId"] > 0 for event in trail), "每個事件都要指得回官方紀錄"

    def test_recommendations_are_non_empty_and_carry_evidence(self, client: TestClient) -> None:
        recs = _data(client, f"/api/v1/insights/{WANG_XIAOMING_ID}/recommendations")

        assert len(recs) > 0
        for rec in recs:
            assert rec["computedBy"] == "rules"      # 推薦由規則決定，不是 LLM 生的
            assert rec["evidence"][0]["recordId"] > 0

    def test_today_briefing_is_non_empty(self, client: TestClient) -> None:
        briefing = _data(client, f"/api/v1/today/{WANG_XIAOMING_ID}")

        assert len(briefing) > 0
        assert all(item["computedBy"] == "rules" for item in briefing)

    def test_points_ledger_is_seeded_like_the_other_demo_households(
        self, client: TestClient,
    ) -> None:
        """種子迴圈只跑 `PERSONAS` 時王小明的錢包會停在 0——改跑 `DEMO_HOUSEHOLDS`。"""
        wallet = _data(client, "/api/v1/platform/points")

        assert wallet["balance"] > 0


class TestCompositionIsDeclared:
    """數字有了，來源標示也要跟著出去。

    反例（官方帳號本人不帶組合標示）在 `tests/test_identity.py` 以單元測試守著——
    這裡打不到，因為 API 本來就不讓一個身分讀別人的帳號（會是 404）。
    """

    def test_summary_declares_the_demo_composition(self, client: TestClient) -> None:
        summary = _data(client, f"/api/v1/insights/{WANG_XIAOMING_ID}/summary")
        composition = summary["composition"]

        # 數字本身來自官方訂單……
        assert summary["source"] == "official_order_record"
        # ……但「為什麼算在王小明頭上」是我們指定的，必須講出來
        assert composition is not None
        assert composition["source"] == "demo_composition"
        assert composition["compositionNote"], "重用帳號一定要有一句人看得懂的說明"
        assert composition["composedFrom"] >= 1
        # 底下的帳號合併確實是官方雜湊做的，這件事可以照實說
        assert composition["resolvedByHash"] == 3

    def test_the_note_discloses_that_the_orders_are_reused(self, client: TestClient) -> None:
        """他的訂單與小圓／陳伯伯重疊——不講的話會被當成他自己的獨立紀錄。"""
        composition = _data(
            client, f"/api/v1/insights/{WANG_XIAOMING_ID}/summary",
        )["composition"]

        assert composition["source"] == "demo_composition"   # 不是 official，也不是 derived
        assert "重用" in composition["compositionNote"]
        assert "重疊" in composition["compositionNote"]
