"""Inquiry persistence boundary."""

from .repository import InquiryRepository, SqliteInquiryRepository

__all__ = ["InquiryRepository", "SqliteInquiryRepository"]
