class FlowIAError(Exception):
    """Base exception for FlowIA."""
    pass

class DoubleBookingError(FlowIAError):
    """Raised when trying to book a slot that is already taken."""
    pass

class BusinessLogicError(FlowIAError):
    """Raised for generic business logic failures (e.g. scheduling outside business hours)."""
    pass

class ResourceNotFoundError(FlowIAError):
    """Raised when a requested resource (like professional or service) is not found."""
    pass

class PermissionDeniedError(FlowIAError):
    """Raised when an authenticated user lacks permission for a resource."""
    pass
