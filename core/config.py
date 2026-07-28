"""設定載入。

**所有可能隨部署環境改變的東西都必須經過這裡**，而且都能用環境變數覆寫——
這是 [ADR-0018] 要上 AWS 的前提：容器裡沒有 `.env`，只有環境變數；
資料庫路徑在本機是 `tmp/*.sqlite3`，在雲端會變成 RDS 連線字串。
程式碼裡任何一處寫死路徑，都是移植時會炸掉的地方。

本機用 NCHC OpenAI 相容端點（Gemma）；最終部署改 Bedrock Claude，只換 `LlmClient`
實作，見 [ADR-0004]。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
# dotenv 的 find_dotenv() 在以 stdin/heredoc 執行時會失敗，所以指定明確路徑
load_dotenv(ROOT / ".env")

#: demo 用的固定「今天」。相對日期解析與驗證要能重現，不能隨機器時鐘漂移。
DEFAULT_DEMO_TODAY = date(2026, 7, 25)


def _env_date(name: str, fallback: date) -> date:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return fallback
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return fallback


@dataclass(frozen=True)
class Settings:
    api_url: str
    api_key: str
    model: str
    demo_today: date
    inquiry_db_path: str
    group_buy_db_path: str
    retail_upstream_url: str
    upstream_timeout_seconds: float
    vendor_mode: str
    vendor_fake_url: str
    vendor_real_url: str
    vendor_api_token: str
    vendor_timeout_seconds: float

    @property
    def has_llm(self) -> bool:
        return bool(self.api_url and self.api_key and self.model)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_dir = Path(os.environ.get("DATA_DIR", ROOT / "tmp"))
    return Settings(
        api_url=os.environ.get("API_URL", ""),
        api_key=os.environ.get("API_KEY", ""),
        model=os.environ.get("MODEL", ""),
        demo_today=_env_date("DEMO_TODAY", DEFAULT_DEMO_TODAY),
        inquiry_db_path=os.environ.get("INQUIRY_DB_PATH", str(data_dir / "life_ai_demo.sqlite3")),
        group_buy_db_path=os.environ.get("GROUP_BUY_DB_PATH", str(data_dir / "group_buys.sqlite3")),
        retail_upstream_url=os.environ.get("RETAIL_UPSTREAM_URL", "").strip(),
        upstream_timeout_seconds=float(os.environ.get("UPSTREAM_TIMEOUT_SECONDS", "2.0")),
        vendor_mode=os.environ.get("VENDOR_MODE", "fake").strip().lower(),
        vendor_fake_url=os.environ.get("VENDOR_FAKE_URL", "http://127.0.0.1:8020").strip(),
        vendor_real_url=os.environ.get("VENDOR_REAL_URL", "").strip(),
        vendor_api_token=os.environ.get("VENDOR_API_TOKEN", "").strip(),
        vendor_timeout_seconds=float(os.environ.get("VENDOR_TIMEOUT_SECONDS", "2.0")),
    )


def settings() -> Settings:
    """保留原本的呼叫形式（`settings()`），避免既有呼叫端全面改寫。"""
    return get_settings()
