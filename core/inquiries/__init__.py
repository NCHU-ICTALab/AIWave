"""諮詢單持久化邊界。"""

from .repository import (
    CANCELLED,
    COMPLETED,
    CONFIRMED,
    PENDING_QUOTE,
    QUOTED,
    STATUS_LABEL,
    InquiryRepository,
    InquiryTransitionError,
    SqliteInquiryRepository,
)

__all__ = [
    "CANCELLED",
    "COMPLETED",
    "CONFIRMED",
    "PENDING_QUOTE",
    "QUOTED",
    "STATUS_LABEL",
    "InquiryRepository",
    "InquiryTransitionError",
    "SqliteInquiryRepository",
]
