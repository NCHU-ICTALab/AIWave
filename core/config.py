"""設定載入（.env）。

本機用 NCHC OpenAI 相容端點（Gemma）；最終部署改 Bedrock Claude，只換 LlmClient
實作，見 [ADR-0004]。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    api_url: str
    api_key: str
    model: str


def settings() -> Settings:
    return Settings(
        api_url=os.environ.get("API_URL", ""),
        api_key=os.environ.get("API_KEY", ""),
        model=os.environ.get("MODEL", ""),
    )
