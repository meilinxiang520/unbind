class UnbindException(Exception):
    """Base exception for unbind errors."""
    pass


class UnsupportedFormatException(UnbindException):
    """No converter available for this format."""
    pass


class FileConversionException(UnbindException):
    """A converter accepted but failed to convert."""

    def __init__(self, attempts: list):
        self.attempts = attempts
        msgs = [f"{a.converter.__class__.__name__}: {a.exc_info[1]}" for a in attempts]
        super().__init__("All conversion attempts failed:\n" + "\n".join(msgs))


class MissingDependencyException(UnbindException):
    """A required dependency is not installed."""
    pass


class FailedConversionAttempt:
    """Record of a single failed conversion attempt."""

    def __init__(self, converter, exc_info):
        self.converter = converter
        self.exc_info = exc_info
