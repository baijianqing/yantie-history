"""Versioned Core Alpha persistence migrations."""

from metaos.core_alpha.persistence.migrations.v0001_foundation import MIGRATION
from metaos.core_alpha.persistence.migrations.v0002_case_scope import (
    MIGRATION as CASE_SCOPE_MIGRATION,
)
from metaos.core_alpha.persistence.migrations.v0003_run_evidence import (
    MIGRATION as RUN_EVIDENCE_MIGRATION,
)

MIGRATIONS = (MIGRATION, CASE_SCOPE_MIGRATION, RUN_EVIDENCE_MIGRATION)

__all__ = ["MIGRATIONS"]
