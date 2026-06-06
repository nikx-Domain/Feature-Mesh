class SDKException(Exception):
    """Base exception for all SDK errors."""
    pass

class SDKNetworkException(SDKException):
    """Raised when there are network issues communicating with the backend."""
    pass

class SDKInitializationException(SDKException):
    """Raised when the SDK fails to initialize properly."""
    pass
