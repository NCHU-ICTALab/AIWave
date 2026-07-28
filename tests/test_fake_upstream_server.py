"""Fake upstream 是可跑的 HTTP 合約，不是每個測試各自手寫回應。"""

from time import perf_counter

from fastapi.testclient import TestClient

from fake_upstreams.app import create_fake_upstream_app

CONTROL_KEY = "test-control-key"


def _control_headers() -> dict[str, str]:
    return {"X-Fake-Control-Key": CONTROL_KEY}


def test_demo_seed_can_inject_one_failure_and_reset():
    client = TestClient(create_fake_upstream_app(control_key=CONTROL_KEY))

    product = client.get("/v1/retail/products/resolve", params={"q": "吉伊卡哇限定杯"})
    assert product.status_code == 200
    assert product.json()["data"] == {"id": "limited-cup", "name": "吉伊卡哇限定杯"}
    assert product.json()["meta"]["dataSource"] == "fake_upstream:demo_seed_v1"

    injected = client.put("/__fake__/faults/next", headers=_control_headers(), json={
        "method": "GET", "path": "/v1/retail/inventory/limited-cup", "status": 503,
        "detail": "品牌庫存服務維護中", "delay_ms": 0,
    })
    assert injected.status_code == 200
    assert client.get("/v1/retail/inventory/limited-cup").status_code == 503

    recovered = client.get("/v1/retail/inventory/limited-cup")
    assert recovered.status_code == 200
    assert len(recovered.json()["data"]) == 3

    state = client.get("/__fake__/state", headers=_control_headers()).json()["data"]
    assert state["scenario"] == "demo_seed_v1"
    assert state["requestCount"] >= 4
    assert state["pendingFaults"] == []

    client.put("/__fake__/faults/next", headers=_control_headers(), json={
        "method": "GET", "path": "/v1/retail/inventory/limited-cup", "status": 504,
        "detail": "逾時", "delay_ms": 10,
    })
    reset = client.post("/__fake__/reset", headers=_control_headers())
    assert reset.json()["data"]["scenario"] == "demo_seed_v1"
    assert reset.json()["data"]["requestCount"] == 0
    assert reset.json()["data"]["pendingFaults"] == []
    assert client.get("/v1/retail/inventory/limited-cup").status_code == 200


def test_control_plane_is_not_public():
    client = TestClient(create_fake_upstream_app(control_key=CONTROL_KEY))

    assert client.get("/__fake__/state").status_code == 401
    assert client.post("/__fake__/reset").status_code == 401


def test_injected_success_latency_is_observable_and_only_applies_once():
    client = TestClient(create_fake_upstream_app(control_key=CONTROL_KEY))
    client.put("/__fake__/faults/next", headers=_control_headers(), json={
        "method": "GET", "path": "/v1/retail/inventory/limited-cup", "status": 200,
        "delay_ms": 40,
    })

    started = perf_counter()
    assert client.get("/v1/retail/inventory/limited-cup").status_code == 200
    delayed_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    assert client.get("/v1/retail/inventory/limited-cup").status_code == 200
    recovered_ms = (perf_counter() - started) * 1000

    assert delayed_ms >= 35
    assert recovered_ms < delayed_ms
