"""Versioned Core Alpha persistence migrations."""

from metaos.core_alpha.persistence.migrations.v0001_foundation import MIGRATION
from metaos.core_alpha.persistence.migrations.v0002_case_scope import (
    MIGRATION as CASE_SCOPE_MIGRATION,
)

MIGRATIONS = (MIGRATION, CASE_SCOPE_MIGRATION)

__all__ = ["MIGRATIONS"]
