"""Shared Core Alpha API and application command contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Generic, TypeAlias, TypeVar

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StringConstraints,
    model_validator,
)


def _require_utc(value: datetime) -> datetime:
    offset = value.utcoffset()
    if offset is None:
        raise ValueError("datetime must include a UTC timezone")
    if offset != timedelta(0):
        raise ValueError("datetime must use UTC offset +00:00")
    return value.astimezone(timezone.utc)


NonEmptyString: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]
CodeIdentifier: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[a-z][a-z0-9_]*$",
        strict=True,
    ),
]
ResourceId: TypeAlias = NonEmptyString
Revision: TypeAlias = Annotated[int, Field(strict=True, ge=1)]
NonNegativeInt: TypeAlias = Annotated[int, Field(strict=True, ge=0)]
HashValue: TypeAlias = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        pattern=r"^[a-z][a-z0-9_-]*:[0-9a-f]+$",
        strict=True,
    ),
]
OpaqueCursor: TypeAlias = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4096, strict=True),
]
IdempotencyKey: TypeAlias = NonEmptyString
UtcDateTime: TypeAlias = Annotated[datetime, AfterValidator(_require_utc)]


class StrictContractModel(BaseModel):
    """Base model for closed JSON objects in the frozen API contract."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OpenCodeValue(StrictContractModel):
    code: NonEmptyString
    registry_version: NonEmptyString


class ResourceReference(StrictContractModel):
    resource_type: CodeIdentifier
    resource_id: ResourceId


class CommandContext(StrictContractModel):
    command_id: ResourceId
    actor_type: OpenCodeValue
    actor_id: ResourceId
    idempotency_key: IdempotencyKey
    correlation_id: ResourceId
    causation_id: ResourceId
    trace_id: ResourceId


class ConsistencySource(str, Enum):
    authoritative_store = "authoritative_store"
    projection = "projection"


class AggregateRevisionReference(StrictContractModel):
    aggregate_type: CodeIdentifier
    aggregate_id: ResourceId
    revision: Revision


class Consistency(StrictContractModel):
    source: ConsistencySource
    primary_aggregate: AggregateRevisionReference | None
    affected_aggregates: list[AggregateRevisionReference]
    projection_checkpoint: OpaqueCursor | None
    is_stale: StrictBool
    observed_at: UtcDateTime

    @model_validator(mode="after")
    def validate_source_and_aggregates(self) -> "Consistency":
        if self.source == ConsistencySource.authoritative_store:
            if self.projection_checkpoint is not None:
                raise ValueError("authoritative consistency cannot include a projection checkpoint")
            if self.is_stale:
                raise ValueError("authoritative consistency cannot be stale")
        elif self.projection_checkpoint is None:
            raise ValueError("projection consistency requires a projection checkpoint")

        aggregate_keys: set[tuple[str, str]] = set()
        if self.primary_aggregate is not None:
            aggregate_keys.add(
                (
                    self.primary_aggregate.aggregate_type,
                    self.primary_aggregate.aggregate_id,
                )
            )
        for aggregate in self.affected_aggregates:
            key = (aggregate.aggregate_type, aggregate.aggregate_id)
            if key in aggregate_keys:
                raise ValueError("aggregate references must be unique across consistency metadata")
            aggregate_keys.add(key)
        return self


class CommandMetadata(StrictContractModel):
    command_id: ResourceId
    trace_id: ResourceId
    idempotency_key: IdempotencyKey
    idempotent_replay: StrictBool


class PageInfo(StrictContractModel):
    next_cursor: OpaqueCursor | None


class AggregateReadParams(StrictContractModel):
    minimum_revision: Revision | None = None
    consistency_wait_ms: Annotated[int, Field(strict=True, ge=0, le=5000)] = 0


class PaginationParams(StrictContractModel):
    cursor: OpaqueCursor | None = None
    limit: Annotated[int, Field(strict=True, ge=1, le=200)] = 50
    minimum_checkpoint: OpaqueCursor | None = None
    consistency_wait_ms: Annotated[int, Field(strict=True, ge=0, le=5000)] = 0


class Error(StrictContractModel):
    code: CodeIdentifier
    message: NonEmptyString
    details: dict[str, JsonValue]
    trace_id: ResourceId
    retryable: StrictBool


class ErrorResponse(StrictContractModel):
    error: Error


DataT = TypeVar("DataT")


class CommandResponse(StrictContractModel, Generic[DataT]):
    data: DataT
    command: CommandMetadata
    consistency: Consistency

    @model_validator(mode="after")
    def validate_authoritative_command_result(self) -> "CommandResponse[DataT]":
        if self.consistency.source != ConsistencySource.authoritative_store:
            raise ValueError("command responses must come from the authoritative store")
        if self.consistency.primary_aggregate is None:
            raise ValueError("command responses require a primary aggregate")
        return self


class QueryResponse(StrictContractModel, Generic[DataT]):
    data: DataT
    consistency: Consistency


class ListResponse(StrictContractModel, Generic[DataT]):
    data: list[DataT]
    page: PageInfo
    consistency: Consistency

    @model_validator(mode="after")
    def validate_projection_list(self) -> "ListResponse[DataT]":
        if self.consistency.source != ConsistencySource.projection:
            raise ValueError("list responses must identify their projection checkpoint")
        if self.consistency.primary_aggregate is not None:
            raise ValueError("list responses cannot have a primary aggregate")
        return self

