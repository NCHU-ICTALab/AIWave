"""官方資料檔載入共用工具。

`raw_data/` 的部分 JSON 是「多個頂層物件串接」而非單一 JSON 文件（例如
`縣市區域範例資料.json`、`相關主檔設定.json`），標準 `json.load` 會在第二個物件處
拋 Extra data。此模組負責逐一解析並依資料表名合併。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from core.config import ROOT

RAW_DATA = ROOT / "raw_data"


def iter_json_objects(text: str) -> Iterator[object]:
    """逐一解析串接在同一個檔案裡的 JSON 物件。"""
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text):
        while index < len(text) and text[index] not in "{[":
            index += 1
        if index >= len(text):
            break
        obj, index = decoder.raw_decode(text, index)
        yield obj


def load_tables(path: Path) -> dict[str, list[dict]]:
    """把官方檔案讀成 {資料表名: 列陣列}。"""
    merged: dict[str, list[dict]] = {}
    for obj in iter_json_objects(path.read_text(encoding="utf-8")):
        if isinstance(obj, dict):
            for table, rows in obj.items():
                if isinstance(rows, list):
                    merged.setdefault(table, []).extend(rows)
    return merged


def load_rows(path: Path) -> list[dict]:
    """讀出單純的列陣列（檔案本身就是一個 JSON 陣列時使用）。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    for value in data.values():
        if isinstance(value, list):
            return value
    return []


@lru_cache(maxsize=1)
def service_master() -> dict[int, dict]:
    """官方服務項目主檔 `cms_homepage_service`（含服務商名稱）。"""
    tables = load_tables(RAW_DATA / "相關主檔設定.json")
    vendors = {row["id"]: row.get("name", "") for row in tables.get("cms_homepage_service_vendor", [])}
    return {
        row["id"]: {**row, "vendor_name": vendors.get(row.get("service_vendor_id"), "")}
        for row in tables.get("cms_homepage_service", [])
    }
