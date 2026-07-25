"""社區領域：住戶共享範圍下的集體服務（目前為團購）。"""

from .group_buy import (
    CLOSED,
    FULFILLED,
    OPEN,
    STATUS_LABEL,
    GroupBuyError,
    GroupBuyRepository,
    SqliteGroupBuyRepository,
)

__all__ = [
    "CLOSED",
    "FULFILLED",
    "OPEN",
    "STATUS_LABEL",
    "GroupBuyError",
    "GroupBuyRepository",
    "SqliteGroupBuyRepository",
]
