"""Versioned Core Alpha persistence migrations."""

from metaos.core_alpha.persistence.migrations.v0001_foundation import MIGRATION

MIGRATIONS = (MIGRATION,)

__all__ = ["MIGRATIONS"]
