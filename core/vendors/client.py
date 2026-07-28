"""廠商 API adapter seam。

平台只知道 ``VendorClient``；fake 與 real 都走 HTTP，切換時不改業務規則。
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx


class VendorClientError(RuntimeError):
    """網路、上游錯誤或成功回應不符合契約。"""


class VendorClient(Protocol):
    connector_mode: str

    def search_vendors(self, **criteria: Any) -> dict[str, Any]: ...
    def get_vendor(self, vendor_id: str) -> dict[str, Any]: ...
    def list_offerings(self, **criteria: Any) -> dict[str, Any]: ...
    def get_availability(self, *, vendor_id: str, service_id: str, date: str | None = None) -> dict[str, Any]: ...
    def create_inquiry(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]: ...
    def list_inquiries(self, **criteria: Any) -> dict[str, Any]: ...
    def get_inquiry(self, inquiry_id: str) -> dict[str, Any]: ...
    def create_quote(self, inquiry_id: str, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]: ...
    def list_quotes(self, inquiry_id: str) -> dict[str, Any]: ...
    def create_order(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]: ...
    def list_orders(self, **criteria: Any) -> dict[str, Any]: ...
    def get_order(self, order_id: str) -> dict[str, Any]: ...
    def append_order_event(self, order_id: str, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]: ...


class _HttpVendorClient:
    connector_mode = "http"

    def __init__(
        self, *, base_url: str, client: httpx.Client | None = None,
        timeout_seconds: float = 2.0, api_token: str = "",
    ) -> None:
        if not base_url.strip():
            raise ValueError("Vendor API base URL 不可空白")
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token.strip()
        self.client = client or httpx.Client(base_url=self.base_url, timeout=timeout_seconds)

    def _request(
        self, method: str, path: str, *, params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None, idempotency_key: str | None = None,
        expected: type = dict,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        cleaned_params = {key: value for key, value in (params or {}).items() if value is not None}
        try:
            response = self.client.request(method, path, params=cleaned_params or None, json=json, headers=headers)
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            raise VendorClientError(f"廠商 API 無法連線：{exc}") from exc
        if response.status_code >= 400:
            try:
                body = response.json()
                message = body.get("error", {}).get("message") or body.get("detail")
            except (ValueError, TypeError, AttributeError):
                message = None
            raise VendorClientError(str(message or f"廠商 API 回應 {response.status_code}"))
        try:
            payload = response.json()
            data = payload["data"]
            meta = payload["meta"]
            if not isinstance(meta, dict) or not isinstance(data, expected):
                raise TypeError
            data_source = meta.get("dataSource")
            if not isinstance(data_source, str) or not data_source:
                raise TypeError
            return {"data": data, "meta": meta}
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise VendorClientError("廠商 API 成功回應不符合 OpenAPI 契約") from exc

    @staticmethod
    def _validate_rows(payload: dict[str, Any], required: set[str]) -> dict[str, Any]:
        rows = payload["data"]
        if any(not isinstance(row, dict) or not required <= row.keys() for row in rows):
            raise VendorClientError("廠商 API 成功回應不符合 OpenAPI 契約")
        return payload

    @staticmethod
    def _validate_object(payload: dict[str, Any], required: set[str]) -> dict[str, Any]:
        row = payload["data"]
        if not required <= row.keys():
            raise VendorClientError("廠商 API 成功回應不符合 OpenAPI 契約")
        return payload

    def search_vendors(self, **criteria: Any) -> dict[str, Any]:
        payload = self._request("GET", "/v1/vendors", params=criteria, expected=list)
        return self._validate_rows(payload, {"id", "name", "serviceIds", "rating", "reviewCount", "source"})

    def get_vendor(self, vendor_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/v1/vendors/{vendor_id}")
        return self._validate_object(payload, {"id", "name", "serviceIds", "source"})

    def list_offerings(self, **criteria: Any) -> dict[str, Any]:
        payload = self._request("GET", "/v1/offerings", params=criteria, expected=list)
        return self._validate_rows(payload, {"id", "vendorId", "serviceId", "basePrice", "slots"})

    def get_availability(self, *, vendor_id: str, service_id: str, date: str | None = None) -> dict[str, Any]:
        payload = self._request("GET", "/v1/availability", params={
            "vendorId": vendor_id, "serviceId": service_id, "date": date,
        }, expected=list)
        return self._validate_rows(payload, {"date", "slot", "available", "remainingCapacity"})

    def create_inquiry(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        result = self._request("POST", "/v1/inquiries", json=payload, idempotency_key=idempotency_key)
        return self._validate_object(result, {"id", "serviceId", "status", "version"})

    def list_inquiries(self, **criteria: Any) -> dict[str, Any]:
        result = self._request("GET", "/v1/inquiries", params=criteria, expected=list)
        return self._validate_rows(result, {"id", "serviceId", "status", "version"})

    def get_inquiry(self, inquiry_id: str) -> dict[str, Any]:
        result = self._request("GET", f"/v1/inquiries/{inquiry_id}")
        return self._validate_object(result, {"id", "serviceId", "status", "version"})

    def create_quote(self, inquiry_id: str, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        result = self._request(
            "POST", f"/v1/inquiries/{inquiry_id}/quotes", json=payload, idempotency_key=idempotency_key,
        )
        return self._validate_object(result, {"id", "inquiryId", "vendorId", "total", "status"})

    def list_quotes(self, inquiry_id: str) -> dict[str, Any]:
        result = self._request("GET", f"/v1/inquiries/{inquiry_id}/quotes", expected=list)
        return self._validate_rows(result, {"id", "inquiryId", "vendorId", "total", "status"})

    def create_order(self, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        result = self._request("POST", "/v1/orders", json=payload, idempotency_key=idempotency_key)
        return self._validate_object(result, {"id", "inquiryId", "quoteId", "status", "version", "events"})

    def list_orders(self, **criteria: Any) -> dict[str, Any]:
        result = self._request("GET", "/v1/orders", params=criteria, expected=list)
        return self._validate_rows(result, {"id", "inquiryId", "quoteId", "status", "version", "events"})

    def get_order(self, order_id: str) -> dict[str, Any]:
        result = self._request("GET", f"/v1/orders/{order_id}")
        return self._validate_object(result, {"id", "status", "version", "events"})

    def append_order_event(self, order_id: str, payload: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
        result = self._request(
            "POST", f"/v1/orders/{order_id}/events", json=payload, idempotency_key=idempotency_key,
        )
        return self._validate_object(result, {"id", "status", "version", "events"})


class MockVendorClient(_HttpVendorClient):
    """連獨立 fake server 的 HTTP adapter。"""

    connector_mode = "mock_http"


class RealVendorClient(_HttpVendorClient):
    """連未來正式合作廠商 API 的 HTTP adapter。"""

    connector_mode = "real_http"

    def __init__(self, *, api_token: str, **kwargs: Any) -> None:
        if not api_token.strip():
            raise ValueError("VENDOR_MODE=real 時必須提供 VENDOR_API_TOKEN")
        super().__init__(api_token=api_token, **kwargs)


def build_vendor_client(
    *, mode: str, fake_url: str, real_url: str, api_token: str, timeout_seconds: float,
) -> VendorClient:
    normalized = mode.strip().lower()
    if normalized == "fake":
        return MockVendorClient(base_url=fake_url, timeout_seconds=timeout_seconds)
    if normalized == "real":
        return RealVendorClient(base_url=real_url, api_token=api_token, timeout_seconds=timeout_seconds)
    raise ValueError("VENDOR_MODE 只接受 fake 或 real")
