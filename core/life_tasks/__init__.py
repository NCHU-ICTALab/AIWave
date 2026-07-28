"""跨服務、一次確認、可追蹤的生活任務。"""

from .repository import LifeTaskRepositoryError, SqliteLifeTaskRepository
from .service import (
    DEMO_CONTACT,
    DEMO_HOME,
    LifeTaskError,
    LifeTaskNotApplicable,
    LifeTaskService,
    LifeTaskUpstreamError,
)

__all__ = [
    "DEMO_CONTACT", "DEMO_HOME", "LifeTaskError", "LifeTaskNotApplicable",
    "LifeTaskRepositoryError", "LifeTaskService", "LifeTaskUpstreamError",
    "SqliteLifeTaskRepository",
]
