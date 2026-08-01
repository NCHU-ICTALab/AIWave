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
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
# dotenv 的 find_dotenv() 在以 stdin/heredoc 執行時會失敗，所以指定明確路徑
load_dotenv(ROOT / ".env")

TAIPEI_TIMEZONE = timezone(timedelta(hours=8))


def taipei_today() -> date:
    """產品的日曆基準；AWS 主機使用 UTC，也必須以台灣日期理解「今天／明天」。"""
    return datetime.now(TAIPEI_TIMEZONE).date()


def _env_date(name: str) -> date:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return taipei_today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return taipei_today()


# M4 六場景 Demo 的 provider → Partner API key 對應。
# fake upstream 以同一組 key 驗證;真實環境改由 PARTNER_PROVIDER_KEYS 覆蓋
# (格式 "vendor-a:key-a,vendor-b:key-b")。
DEFAULT_PARTNER_PROVIDER_KEYS: dict[str, str] = {
    "vendor-prince-electric": "aiwave-partner",
    "vendor-duskin": "aiwave-partner-duskin",
    "vendor-21plus": "aiwave-partner-21plus",
    "vendor-smile": "aiwave-partner-smile",
    "vendor-blackcat": "aiwave-partner-blackcat",
    "vendor-cosmed": "aiwave-partner-cosmed",
    "vendor-711-shop": "aiwave-partner-711shop",
    "vendor-uni-resort": "aiwave-partner-resort",
    "vendor-foodomo": "aiwave-partner-foodomo",
    "vendor-711-c2c": "aiwave-partner-711c2c",
    "vendor-iopenmall": "aiwave-partner-iopenmall",
    "vendor-ibon-ticket": "aiwave-partner-ibonticket",
}


def _env_provider_keys(name: str) -> dict[str, str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return dict(DEFAULT_PARTNER_PROVIDER_KEYS)
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        provider_id, _, key = pair.strip().partition(":")
        if provider_id and key:
            mapping[provider_id] = key
    return mapping or dict(DEFAULT_PARTNER_PROVIDER_KEYS)


@dataclass(frozen=True)
class Settings:
    api_url: str
    api_key: str
    model: str
    # LLM 供應來源：openai（NCHC 相容端點）或 bedrock（正式競賽環境；見 core/clients/bedrock.py）
    llm_provider: str
    bedrock_model_id: str
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
    provider_mode: str
    provider_id: str
    partner_mode: str
    partner_fake_url: str
    partner_real_url: str
    partner_api_key: str
    partner_timeout_seconds: float
    partner_provider_keys: dict[str, str]
    catalog_sync_on_startup: bool
    demo_reset_enabled: bool
    vendor_fake_control_key: str
    retail_fake_control_key: str

    @property
    def has_llm(self) -> bool:
        if self.llm_provider == "bedrock":
            return bool(self.bedrock_model_id)  # 憑證走 IAM task role，不需要 API key
        return bool(self.api_url and self.api_key and self.model)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_dir = Path(os.environ.get("DATA_DIR", ROOT / "tmp"))
    return Settings(
        api_url=os.environ.get("API_URL", ""),
        api_key=os.environ.get("API_KEY", ""),
        model=os.environ.get("MODEL", ""),
        llm_provider=os.environ.get("LLM_PROVIDER", "openai").strip().lower(),
        # 必須用 inference profile（us. 前綴）；競賽帳號直接用 foundation model ID 會被拒
        bedrock_model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6").strip(),
        # 正常運行跟隨台灣當天；競賽彩排或測試可用 DEMO_TODAY 固定時間。
        demo_today=_env_date("DEMO_TODAY"),
        inquiry_db_path=os.environ.get("INQUIRY_DB_PATH", str(data_dir / "life_ai_demo.sqlite3")),
        group_buy_db_path=os.environ.get("GROUP_BUY_DB_PATH", str(data_dir / "group_buys.sqlite3")),
        retail_upstream_url=os.environ.get("RETAIL_UPSTREAM_URL", "").strip(),
        upstream_timeout_seconds=float(os.environ.get("UPSTREAM_TIMEOUT_SECONDS", "2.0")),
        vendor_mode=os.environ.get("VENDOR_MODE", "fake").strip().lower(),
        vendor_fake_url=os.environ.get("VENDOR_FAKE_URL", "http://127.0.0.1:8020").strip(),
        vendor_real_url=os.environ.get("VENDOR_REAL_URL", "").strip(),
        vendor_api_token=os.environ.get("VENDOR_API_TOKEN", "").strip(),
        vendor_timeout_seconds=float(os.environ.get("VENDOR_TIMEOUT_SECONDS", "2.0")),
        provider_mode=os.environ.get("PROVIDER_MODE", "standard").strip().lower(),
        provider_id=os.environ.get("PROVIDER_ID", "vendor-prince-electric").strip(),
        partner_mode=os.environ.get("PARTNER_MODE", "fake").strip().lower(),
        partner_fake_url=os.environ.get("PARTNER_FAKE_URL", "http://127.0.0.1:8020").strip(),
        partner_real_url=os.environ.get("PARTNER_REAL_URL", "").strip(),
        partner_api_key=os.environ.get("PARTNER_API_KEY", "aiwave-partner").strip(),
        partner_timeout_seconds=float(os.environ.get("PARTNER_TIMEOUT_SECONDS", "2.0")),
        partner_provider_keys=_env_provider_keys("PARTNER_PROVIDER_KEYS"),
        catalog_sync_on_startup=os.environ.get("CATALOG_SYNC_ON_STARTUP", "true").strip().lower()
        in {"1", "true", "yes"},
        demo_reset_enabled=os.environ.get("DEMO_RESET_ENABLED", "true").strip().lower() in {"1", "true", "yes"},
        vendor_fake_control_key=os.environ.get("VENDOR_FAKE_CONTROL_KEY", "").strip(),
        retail_fake_control_key=os.environ.get("FAKE_CONTROL_KEY", "").strip(),
    )


def settings() -> Settings:
    """保留原本的呼叫形式（`settings()`），避免既有呼叫端全面改寫。"""
    return get_settings()
