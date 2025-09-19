class UserAlreadyExistsError(Exception):
    pass

class DomainMismatchError(Exception):
    pass

class DatabaseError(Exception):
    pass

class RegistrationError(Exception):
    pass
    """Raised when a database operation fails during registration."""

class DomainAlreadyRegisteredError(Exception):
    """Raised when a user attempts to self-register under a domain
    that already has an admin."""
    pass

class UnexpectedRegistrationError(RegistrationError):
    """Raised for unexpected errors during registration."""
