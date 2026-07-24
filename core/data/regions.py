"""縣市/行政區名稱 ↔ 官方代碼解析（用官方 sys_county / sys_district 範例資料）。

地區題（type 5）由 LLM 抽出口語地名（如「台北市大同區」），再經此解析為官方
county_code / district_code。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from core.config import ROOT

_DATA = ROOT / "raw_data" / "縣市區域範例資料.json"

# 官方競賽檔是範例子集，縣市主檔含台中市、行政區明細卻缺部分台中區域。
# 使用 namespaced code 補 P0 場景，不偽裝成官方 sys_district 原始列。
_DEMO_DISTRICT_EXTENSIONS = [
    {"county_code": "08", "code": "seed-taichung-xitun", "name": "西屯區"},
    {"county_code": "08", "code": "seed-taichung-beitun", "name": "北屯區"},
]


def _normalize_name(value: str) -> str:
    return (value or "").strip().replace("臺", "台")


def _iter_objects(text: str):
    """檔案可能是多個 JSON 物件串接，逐一解析。"""
    dec = json.JSONDecoder()
    i = 0
    while i < len(text):
        while i < len(text) and text[i] not in "{[":
            i += 1
        if i >= len(text):
            break
        obj, j = dec.raw_decode(text, i)
        yield obj
        i = j


@lru_cache(maxsize=1)
def _tables() -> tuple[dict[str, str], list[dict]]:
    counties: dict[str, str] = {}
    districts: list[dict] = []
    text = _DATA.read_text(encoding="utf-8")
    merged: dict[str, list] = {}
    for obj in _iter_objects(text):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, list):
                    merged.setdefault(k, []).extend(v)
    for c in merged.get("sys_county", []):
        counties[c["code"]] = c["name"]
    districts = list(merged.get("sys_district", []))
    existing = {(item.get("county_code"), item.get("name")) for item in districts}
    districts.extend(
        item for item in _DEMO_DISTRICT_EXTENSIONS
        if (item["county_code"], item["name"]) not in existing
    )
    return counties, districts


def resolve(district_name: str, county_name: str | None = None) -> dict | None:
    """回傳 {county_code, county_name, district_code, district_name} 或 None（找不到/歧義）。"""
    counties, districts = _tables()
    dn = _normalize_name(district_name)
    cn = _normalize_name(county_name or "")
    matches = [d for d in districts if _normalize_name(str(d.get("name") or "")) == dn]
    if cn:
        matches = [d for d in matches if _normalize_name(counties.get(d.get("county_code"), "")) == cn]
    if len(matches) != 1:
        return None
    d = matches[0]
    return {
        "county_code": d["county_code"],
        "county_name": counties.get(d["county_code"]),
        "district_code": d["code"],
        "district_name": d["name"],
    }
