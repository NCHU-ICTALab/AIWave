"""M8 Agent 核心:確定性守門模組與協調器。

spec 15 §4/§4.2:Agent 負責理解、規劃、預填、比較、導覽與受控執行;
時間、服務存在性、金額、權限與訂單狀態一律由確定性模組裁決,LLM 不得繞過。
"""

from .grants import GrantError, SqliteGrantRepository
from .registry import RegistryResolution, ServiceRegistry
from .time_resolver import TimeResolution, TimeResolver

__all__ = [
    "GrantError",
    "RegistryResolution",
    "ServiceRegistry",
    "SqliteGrantRepository",
    "TimeResolution",
    "TimeResolver",
]
