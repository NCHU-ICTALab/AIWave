"""合作廠商 API adapter 與同源媒合服務。"""

from .client import (
    MockVendorClient,
    RealVendorClient,
    VendorClient,
    VendorClientError,
    build_vendor_client,
)
from .service import VendorService

__all__ = [
    "MockVendorClient", "RealVendorClient", "VendorClient", "VendorClientError",
    "VendorService", "build_vendor_client",
]
