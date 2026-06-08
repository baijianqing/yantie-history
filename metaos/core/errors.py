"""Shared exceptions for MetaOS Lite."""


class MetaOSError(Exception):
    """Base class for application-level errors."""


class ConfigurationError(MetaOSError):
    """Raised when required configuration is missing or invalid."""


class WorkspaceError(MetaOSError):
    """Raised when the local workspace cannot be prepared or read."""


class JobNotFoundError(WorkspaceError):
    """Raised when a job id does not exist in the local database."""


class SourceNotFoundError(WorkspaceError):
    """Raised when a source id does not exist in the local database."""


class AssetNotFoundError(WorkspaceError):
    """Raised when an asset id does not exist in the local database."""


class KnowledgeItemNotFoundError(WorkspaceError):
    """Raised when a knowledge item id does not exist in the local database."""


class UnsupportedDocumentError(MetaOSError):
    """Raised when a document type is not supported by the current parser."""


class EmbeddingProviderError(MetaOSError):
    """Raised when local or remote embedding generation fails."""
