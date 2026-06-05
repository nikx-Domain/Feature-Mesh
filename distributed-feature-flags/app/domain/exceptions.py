class DomainException(Exception):
    """Base class for all domain exceptions."""
    pass


class EntityNotFoundException(DomainException):
    """Raised when an expected entity is not found."""
    def __init__(self, message: str = "Entity not found"):
        self.message = message
        super().__init__(self.message)


class EntityAlreadyExistsException(DomainException):
    """Raised when attempting to create an entity that already exists."""
    def __init__(self, message: str = "Entity already exists"):
        self.message = message
        super().__init__(self.message)


class PermissionDeniedException(DomainException):
    """Raised when a user does not have permission to perform an action."""
    def __init__(self, message: str = "Permission denied"):
        self.message = message
        super().__init__(self.message)


class AuthenticationException(DomainException):
    """Raised when authentication fails."""
    def __init__(self, message: str = "Authentication failed"):
        self.message = message
        super().__init__(self.message)
