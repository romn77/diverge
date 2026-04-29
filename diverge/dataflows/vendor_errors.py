class VendorError(Exception):
    """Base error for vendor integration failures."""


class VendorRetryableError(VendorError):
    """Temporary issue that should trigger fallback."""


class VendorAuthError(VendorError):
    """Authentication or permission issue for the current vendor."""


class VendorNotSupportedError(VendorError):
    """The vendor does not support this operation."""


class VendorDataEmptyError(VendorError):
    """The vendor returned no useful data."""
