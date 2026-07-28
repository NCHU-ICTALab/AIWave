"""社區領域：住戶共享範圍下的團購與聯合服務。"""

from .joint_service import (
    ASSIGNED,
    COLLECTING,
    COMPLETED,
    DRAFT,
    IN_PROGRESS,
    PROPOSAL_REVIEW,
    JointServiceError,
    JointServiceRepository,
    SqliteJointServiceRepository,
)

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
    "ASSIGNED",
    "COLLECTING",
    "COMPLETED",
    "DRAFT",
    "IN_PROGRESS",
    "PROPOSAL_REVIEW",
    "JointServiceError",
    "JointServiceRepository",
    "SqliteJointServiceRepository",
]
