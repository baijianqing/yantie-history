"""Public exports for Core Alpha shared contracts."""

from metaos.core_alpha.contracts import decision as _decision
from metaos.core_alpha.contracts import execution as _execution
from metaos.core_alpha.contracts import internal as _internal
from metaos.core_alpha.contracts import judgment as _judgment
from metaos.core_alpha.contracts import scope as _scope

from metaos.core_alpha.contracts.common import (
    AggregateReadParams,
    AggregateRevisionReference,
    CodeIdentifier,
    CommandContext,
    CommandMetadata,
    CommandResponse,
    Consistency,
    ConsistencySource,
    Error,
    ErrorResponse,
    HashValue,
    IdempotencyKey,
    ListResponse,
    NonEmptyString,
    NonNegativeInt,
    OpaqueCursor,
    OpenCodeValue,
    PageInfo,
    PaginationParams,
    QueryResponse,
    ResourceId,
    ResourceReference,
    Revision,
    StrictContractModel,
    UtcDateTime,
)
from metaos.core_alpha.contracts.decision import *  # noqa: F403
from metaos.core_alpha.contracts.execution import *  # noqa: F403
from metaos.core_alpha.contracts.internal import *  # noqa: F403
from metaos.core_alpha.contracts.judgment import *  # noqa: F403
from metaos.core_alpha.contracts.scope import *  # noqa: F403

__all__ = [
    "AggregateReadParams",
    "AggregateRevisionReference",
    "CodeIdentifier",
    "CommandContext",
    "CommandMetadata",
    "CommandResponse",
    "Consistency",
    "ConsistencySource",
    "Error",
    "ErrorResponse",
    "HashValue",
    "IdempotencyKey",
    "ListResponse",
    "NonEmptyString",
    "NonNegativeInt",
    "OpaqueCursor",
    "OpenCodeValue",
    "PageInfo",
    "PaginationParams",
    "QueryResponse",
    "ResourceId",
    "ResourceReference",
    "Revision",
    "StrictContractModel",
    "UtcDateTime",
    *_scope.__all__,
    *_execution.__all__,
    *_judgment.__all__,
    *_decision.__all__,
    *_internal.__all__,
]

if len(__all__) != len(set(__all__)):
    raise RuntimeError("Core Alpha contract exports contain duplicate names")
