class AuthenticationError(Exception):
    """Base exception for authentication and authorization failures."""

    default_message = "Authentication failed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)


class InvalidCredentialsError(AuthenticationError):
    default_message = "Invalid credentials."


class InvalidTokenError(AuthenticationError):
    default_message = "Invalid authentication token."


class ExpiredTokenError(InvalidTokenError):
    default_message = "Authentication token has expired."


class InactiveAccountError(AuthenticationError):
    default_message = "Account is unavailable."


class PermissionDeniedError(AuthenticationError):
    default_message = "Permission denied."


class SecurityConfigurationError(AuthenticationError):
    default_message = "Security configuration is invalid."
