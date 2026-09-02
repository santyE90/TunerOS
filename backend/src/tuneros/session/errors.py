"""Small error hierarchy for portable TunerOS raw-CAN sessions."""


class SessionError(Exception):
    """Base session error."""


class SessionFormatError(SessionError):
    """Raised when a session artifact is malformed."""


class SessionVersionError(SessionFormatError):
    """Raised when an artifact uses an unsupported format version."""


class SessionIntegrityError(SessionFormatError):
    """Raised when counts, hashes, or ordering do not agree."""


class SessionDbcMismatchError(SessionIntegrityError):
    """Raised when replay would use a different DBC schema."""


class SessionRecordingError(SessionError):
    """Raised when a recorder lifecycle or write fails."""
