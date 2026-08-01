"""M8 Agent 端到端(Platform API 層)。

產品路徑只有一條:llm_factory(正式 = .env 的真實模型)。
測試在這裡注入「腳本 LLM」是為了讓 CI 可重現;真 LLM 的實跑證據
另由交付時的實站驗收提供(見 docs/testing/demo-runbook.md M8 節)。
守門(Registry/TimeResolver/Grant)完全不經 LLM,行為在兩種模式下相同。
"""

from __future__ import annotations

import json
from datetime import date

from fastapi.testclient import TestClient

from api.app import create_app
from core.providers import StandardProviderConnector
from fake_upstreams.partner_app import create_partner_fake_app
from fake_upstreams.partner_seed import DEFAULT_PARTNER_KEYS

CONTROL_KEY = "m8-agent-control"


class ScriptedLlm:
    """測試替身:照劇本回應;劇本用完丟例外(模擬模型故障)。"""

    def __init__(self, responses: list[object]) -> None:
        self._responses = list(responses)

    def chat(self, messages, *, temperature=0.0, max_tokens=512) -> str:
        return json.dumps(self.json(messages), ensure_ascii=False)

    def json(self, messages, *, temperature=0.0, max_tokens=512) -> object:
        if not self._responses:
            raise RuntimeError("scripted llm exhausted")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def make_stack(tmp_path, llm_responses: list[object]):
    upstream = TestClient(create_partner_fake_app(control_key=CONTROL_KEY))
    connectors = {
        provider_id: StandardProviderConnector(
            base_url="http://partner-fake", api_key=key, client=upstream,
        )
        for provider_id, key in DEFAULT_PARTNER_KEYS.items()
    }
    llm = ScriptedLlm(llm_responses)
    client = TestClient(create_app(
        demo_db_path=tmp_path / "m8.sqlite3",
        llm_factory=lambda: llm,
        provider_connectors=connectors,
        today=date(2026, 7, 30),  # 與 partner seed 基準日對齊,讓「明天」可驗證
    ))
    synced = client.post("/api/v1/platform/catalog/sync", headers=bearer("aiwave-admin"))
    assert synced.json()["data"]["status"] == "ok"
    return client, upstream


def send(client, payload: dict) -> dict:
    response = client.post("/api/v1/platform/agent/messages", headers=bearer("aiwave"), json=payload)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_single_scene_flow_reaches_a_real_booking_via_grant(tmp_path):
    """單場景:理解→真目錄提案→選定→補欄位→授權→送單;與手動同一筆資料。"""
    client, upstream = make_stack(tmp_path, [
        {"subtasks": [{"goal": "修理浴室的燈", "serviceHint": "修繕", "datePhrase": "明天"}]},
        {"values": {"problem": "浴室的燈不亮", "address": "台北市信義區松勤街 1 號",
                     "phone": "0912345678"}},
    ])

    first = send(client, {"message": "浴室的燈不亮了,想找人明天來修"})
    session = first["session"]
    assert "理解需求" in first["stages"] and "查詢可用方案與時段" in first["stages"]
    subtask = session["subtasks"][0]
    assert subtask["domain"] == "home_repair"
    assert subtask["time"]["date"] == "2026-07-31"          # TimeResolver 裁決,非 LLM
    assert subtask["proposals"], "提案必須來自真實目錄"
    assert all(item["slot"] for item in subtask["proposals"])  # 不提沒有空檔的方案

    picked = send(client, {"session_id": session["id"], "action": {
        "type": "select_option", "subtaskId": subtask["id"],
        "optionId": subtask["proposals"][0]["id"],
    }})
    session = picked["session"]
    subtask = session["subtasks"][0]
    assert subtask["draftId"] and subtask["missingFields"]  # 預填草稿+誠實開口要欄位

    filled = send(client, {"session_id": session["id"],
                           "message": "浴室的燈不亮,地址台北市信義區松勤街 1 號,電話 0912345678"})
    session = filled["session"]
    assert session["awaiting"] == "grant" and session["grantId"]
    grant = client.get(
        f"/api/v1/platform/agent/grants/{session['grantId']}", headers=bearer("aiwave"),
    ).json()["data"]
    assert grant["status"] == "proposed" and grant["budgetLimit"] >= 1200

    done = send(client, {"session_id": session["id"], "action": {"type": "approve_grant"}})
    session = done["session"]
    subtask = session["subtasks"][0]
    assert subtask["status"] == "submitted" and subtask["subjectType"] == "booking"

    # 與手動完全同一份資料:會員訂單清單能看到、payment 已成立、廠商端收到
    bookings = client.get("/api/v1/platform/bookings", headers=bearer("aiwave")).json()["data"]
    assert [row["id"] for row in bookings] == [subtask["subjectId"]]
    assert bookings[0]["details"]["problem"] == "浴室的燈不亮"
    partner_rows = client.get("/api/v1/platform/bookings", headers=bearer("aiwave")).json()
    remote = upstream.get(
        "/partner/v1/bookings", headers=bearer(DEFAULT_PARTNER_KEYS["vendor-prince-electric"]),
    ).json()["data"]
    assert len(remote) == 1

    # 重複核准不會建立第二筆(submit 冪等)
    again = send(client, {"session_id": session["id"], "action": {"type": "approve_grant"}})
    bookings = client.get("/api/v1/platform/bookings", headers=bearer("aiwave")).json()["data"]
    assert len(bookings) == 1


def test_cross_scene_goal_becomes_two_drafts_under_one_grant(tmp_path):
    """跨場景:一句話→兩個子任務→兩張 agent 草稿→一張授權涵蓋→兩筆訂單。"""
    client, _ = make_stack(tmp_path, [
        {"subtasks": [
            {"goal": "找人來全室清潔", "serviceHint": "清潔", "datePhrase": "這週末"},
            {"goal": "訂四人餐廳", "serviceHint": "訂位", "datePhrase": "這週末"},
        ]},
        {"values": {"address": "台北市信義區松勤街 1 號", "phone": "0912345678"}},
        {"values": {"party_size": "4", "contact_name": "林小圓", "phone": "0912345678"}},
    ])

    first = send(client, {"message": "爸媽這週末要來,幫我安排家裡清潔,週末也想訂四人餐廳"})
    session = first["session"]
    assert len(session["subtasks"]) == 2
    assert {item["domain"] for item in session["subtasks"]} == {"home_cleaning", "dining_reservation"}

    for subtask in list(session["subtasks"]):
        result = send(client, {"session_id": session["id"], "action": {
            "type": "select_option", "subtaskId": subtask["id"],
            "optionId": subtask["proposals"][0]["id"],
        }})
        session = result["session"]
        current = next(item for item in session["subtasks"] if item["id"] == subtask["id"])
        if current["missingFields"]:
            filled = send(client, {"session_id": session["id"], "message": "補充資料如下"})
            session = filled["session"]

    assert session["grantId"], "兩個子任務備齊後應提出一張涵蓋兩者的授權"
    grant = client.get(
        f"/api/v1/platform/agent/grants/{session['grantId']}", headers=bearer("aiwave"),
    ).json()["data"]
    assert len(grant["providerIds"]) == 2

    done = send(client, {"session_id": session["id"], "action": {"type": "approve_grant"}})
    session = done["session"]
    assert all(item["status"] == "submitted" for item in session["subtasks"])
    bookings = client.get("/api/v1/platform/bookings", headers=bearer("aiwave")).json()["data"]
    assert len(bookings) == 2


def test_ambiguous_laundry_clarifies_and_llm_failure_degrades_honestly(tmp_path):
    client, _ = make_stack(tmp_path, [
        {"subtasks": [{"goal": "洗衣服", "serviceHint": "洗衣服", "datePhrase": ""}]},
        RuntimeError("model exploded"),  # 第二輪:模型故障
        RuntimeError("model exploded"),  # 重試也故障
    ])
    first = send(client, {"message": "我想洗衣服"})
    session = first["session"]
    subtask = session["subtasks"][0]
    assert subtask["status"] == "clarify" and subtask["clarifyOptions"]
    assert session["awaiting"] == "clarify"

    # 模型完全故障 → 誠實降級,不假裝理解
    second = send(client, {"session_id": session["id"], "message": "那幫我找家事服務"})
    reply = second["session"]["messages"][-1]["content"]
    assert "沒有把握" in reply or "無法解析" in reply

    # 釐清選項是結構化動作,不經 LLM,故障中仍可前進
    third = send(client, {"session_id": session["id"], "action": {
        "type": "clarify_option", "subtaskId": subtask["id"],
        "domain": "home_cleaning", "label": "到府家事服務(含洗衣)",
    }})
    assert third["session"]["subtasks"][0]["proposals"]


def test_manual_handoff_shares_the_same_draft_and_user_edits_win(tmp_path):
    """中途切手動:同一張草稿在精靈端補完(source=user),Agent 端直接用它送單。"""
    client, _ = make_stack(tmp_path, [
        {"subtasks": [{"goal": "修水電", "serviceHint": "修繕", "datePhrase": "明天"}]},
    ])
    first = send(client, {"message": "明天找人修水電"})
    session = first["session"]
    subtask = session["subtasks"][0]
    picked = send(client, {"session_id": session["id"], "action": {
        "type": "select_option", "subtaskId": subtask["id"],
        "optionId": subtask["proposals"][0]["id"],
    }})
    session = picked["session"]
    draft_id = session["subtasks"][0]["draftId"]

    # 手動精靈端:同一份草稿逐欄修改(user 來源優先於 agent)
    draft = client.get(f"/api/v1/platform/task-drafts/{draft_id}", headers=bearer("aiwave")).json()["data"]
    updated = client.patch(
        f"/api/v1/platform/task-drafts/{draft_id}",
        headers=bearer("aiwave"),
        json={"expected_version": draft["version"], "source": "user", "values": {
            "problem": "廚房插座沒電", "address": "台北市信義區虎林街 22 號", "phone": "0933222111",
        }},
    )
    assert updated.status_code == 200

    # 回到 Agent:欄位已齊(由手動補的),直接進入授權並送單
    poke = send(client, {"session_id": session["id"], "message": "都填好了,幫我送出"})
    session = poke["session"]
    assert session["grantId"], "手動補完欄位後 Agent 應接續提出授權"
    done = send(client, {"session_id": session["id"], "action": {"type": "approve_grant"}})
    booking_id = done["session"]["subtasks"][0]["subjectId"]
    booking = client.get(
        f"/api/v1/platform/bookings/{booking_id}", headers=bearer("aiwave"),
    ).json()["data"]
    assert booking["details"]["problem"] == "廚房插座沒電"  # user 值贏過 agent


def test_sessions_are_workspace_isolated_and_restorable(tmp_path):
    client, _ = make_stack(tmp_path, [
        {"subtasks": [{"goal": "修水電", "serviceHint": "修繕", "datePhrase": ""}]},
    ])
    first = send(client, {"message": "找人修水電"})
    session_id = first["session"]["id"]
    # 重新整理/側欄:latest 取回同一段對話
    latest = client.get("/api/v1/platform/agent/sessions/latest", headers=bearer("aiwave")).json()["data"]
    assert latest["id"] == session_id
    # 其他會員看不到(隔離)
    other = client.get(
        f"/api/v1/platform/agent/sessions/{session_id}", headers=bearer("aiwave-chen"),
    )
    assert other.status_code == 404
