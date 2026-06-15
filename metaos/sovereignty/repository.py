"""SQLite repositories for the MetaOS Alpha user sovereignty layer."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from metaos.core.schemas import utc_now
from metaos.sovereignty.schemas import (
    AttentionBudget,
    CognitiveConstitution,
    CurrentRole,
    Intent,
    IntentHorizon,
    IntentStatus,
    NotToDoItem,
    NotToDoScope,
)
from metaos.workspace.database import connect, initialize_database


SOVEREIGNTY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cognitive_constitutions (
    id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    principles_json TEXT NOT NULL,
    decision_rules_json TEXT NOT NULL DEFAULT '[]',
    attention_rules_json TEXT NOT NULL DEFAULT '[]',
    not_to_do_defaults_json TEXT NOT NULL DEFAULT '[]',
    risk_preferences_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cognitive_constitutions_updated_at
    ON cognitive_constitutions(updated_at);

CREATE TABLE IF NOT EXISTS intents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    horizon TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL,
    success_criteria_json TEXT NOT NULL DEFAULT '[]',
    constraints_json TEXT NOT NULL DEFAULT '[]',
    constitution_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_intents_status ON intents(status);
CREATE INDEX IF NOT EXISTS idx_intents_priority ON intents(priority);
CREATE INDEX IF NOT EXISTS idx_intents_updated_at ON intents(updated_at);

CREATE TABLE IF NOT EXISTS current_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    responsibilities_json TEXT NOT NULL DEFAULT '[]',
    allowed_focus_json TEXT NOT NULL DEFAULT '[]',
    forbidden_focus_json TEXT NOT NULL DEFAULT '[]',
    active_from TEXT NOT NULL,
    active_to TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_current_roles_active_to ON current_roles(active_to);
CREATE INDEX IF NOT EXISTS idx_current_roles_updated_at ON current_roles(updated_at);

CREATE TABLE IF NOT EXISTS attention_budgets (
    id TEXT PRIMARY KEY,
    budget_date TEXT NOT NULL,
    total_minutes INTEGER NOT NULL,
    research_minutes INTEGER NOT NULL,
    build_minutes INTEGER NOT NULL,
    review_minutes INTEGER NOT NULL,
    content_minutes INTEGER NOT NULL,
    hard_limits_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attention_budgets_date ON attention_budgets(budget_date);
CREATE INDEX IF NOT EXISTS idx_attention_budgets_updated_at ON attention_budgets(updated_at);

CREATE TABLE IF NOT EXISTS not_to_do_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL,
    active INTEGER NOT NULL,
    expires_at TEXT,
    related_intent_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_not_to_do_items_active ON not_to_do_items(active);
CREATE INDEX IF NOT EXISTS idx_not_to_do_items_scope ON not_to_do_items(scope);
CREATE INDEX IF NOT EXISTS idx_not_to_do_items_updated_at ON not_to_do_items(updated_at);
"""


class SovereigntyRecordNotFoundError(KeyError):
    """Raised when a sovereignty record cannot be found."""


def initialize_sovereignty_database(database_path: Path | None = None) -> Path:
    db_path = initialize_database(database_path)
    with connect(db_path) as connection:
        connection.executescript(SOVEREIGNTY_SCHEMA_SQL)
    return db_path


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_load(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    return json.loads(value)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _optional_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _date(value: str) -> date:
    return date.fromisoformat(value)


class CognitiveConstitutionRepository:
    def __init__(self, database_path: Path | None = None):
        self.database_path = initialize_sovereignty_database(database_path)

    def add(self, constitution: CognitiveConstitution) -> CognitiveConstitution:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO cognitive_constitutions (
                    id, version, principles_json, decision_rules_json,
                    attention_rules_json, not_to_do_defaults_json,
                    risk_preferences_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    constitution.id,
                    constitution.version,
                    _json_dump(constitution.principles),
                    _json_dump(constitution.decision_rules),
                    _json_dump(constitution.attention_rules),
                    _json_dump(constitution.not_to_do_defaults),
                    _json_dump(constitution.risk_preferences),
                    constitution.created_at.isoformat(),
                    constitution.updated_at.isoformat(),
                ),
            )
        return constitution

    def get(self, constitution_id: str) -> CognitiveConstitution:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM cognitive_constitutions WHERE id = ?",
                (constitution_id,),
            ).fetchone()
        if row is None:
            raise SovereigntyRecordNotFoundError(f"CognitiveConstitution not found: {constitution_id}")
        return CognitiveConstitution(
            id=row["id"],
            version=row["version"],
            principles=_json_load(row["principles_json"], []),
            decision_rules=_json_load(row["decision_rules_json"], []),
            attention_rules=_json_load(row["attention_rules_json"], []),
            not_to_do_defaults=_json_load(row["not_to_do_defaults_json"], []),
            risk_preferences=_json_load(row["risk_preferences_json"], {}),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    def list(self, limit: int = 50) -> list[CognitiveConstitution]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT id FROM cognitive_constitutions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self.get(row["id"]) for row in rows]


class IntentRepository:
    def __init__(self, database_path: Path | None = None):
        self.database_path = initialize_sovereignty_database(database_path)

    def add(self, intent: Intent) -> Intent:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO intents (
                    id, title, description, horizon, status, priority,
                    success_criteria_json, constraints_json, constitution_id,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    intent.id,
                    intent.title,
                    intent.description,
                    intent.horizon.value,
                    intent.status.value,
                    intent.priority,
                    _json_dump(intent.success_criteria),
                    _json_dump(intent.constraints),
                    intent.constitution_id,
                    intent.created_at.isoformat(),
                    intent.updated_at.isoformat(),
                ),
            )
        return intent

    def get(self, intent_id: str) -> Intent:
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT * FROM intents WHERE id = ?", (intent_id,)).fetchone()
        if row is None:
            raise SovereigntyRecordNotFoundError(f"Intent not found: {intent_id}")
        return Intent(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            horizon=IntentHorizon(row["horizon"]),
            status=IntentStatus(row["status"]),
            priority=row["priority"],
            success_criteria=_json_load(row["success_criteria_json"], []),
            constraints=_json_load(row["constraints_json"], []),
            constitution_id=row["constitution_id"],
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    def list(self, limit: int = 50, *, status: IntentStatus | None = None) -> list[Intent]:
        sql = "SELECT id FROM intents"
        params: list[Any] = []
        if status is not None:
            sql += " WHERE status = ?"
            params.append(status.value)
        sql += " ORDER BY priority ASC, updated_at DESC LIMIT ?"
        params.append(limit)
        with connect(self.database_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self.get(row["id"]) for row in rows]

    def update_active(self, intent_id: str) -> Intent:
        self.get(intent_id)
        now = utc_now().isoformat()
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE intents
                SET status = ?, updated_at = ?
                WHERE status = ? AND id != ?
                """,
                (IntentStatus.paused.value, now, IntentStatus.active.value, intent_id),
            )
            connection.execute(
                "UPDATE intents SET status = ?, updated_at = ? WHERE id = ?",
                (IntentStatus.active.value, now, intent_id),
            )
        return self.get(intent_id)


class CurrentRoleRepository:
    def __init__(self, database_path: Path | None = None):
        self.database_path = initialize_sovereignty_database(database_path)

    def add(self, role: CurrentRole) -> CurrentRole:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO current_roles (
                    id, name, responsibilities_json, allowed_focus_json,
                    forbidden_focus_json, active_from, active_to, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    role.id,
                    role.name,
                    _json_dump(role.responsibilities),
                    _json_dump(role.allowed_focus),
                    _json_dump(role.forbidden_focus),
                    role.active_from.isoformat(),
                    role.active_to.isoformat() if role.active_to else None,
                    role.created_at.isoformat(),
                    role.updated_at.isoformat(),
                ),
            )
        return role

    def get(self, role_id: str) -> CurrentRole:
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT * FROM current_roles WHERE id = ?", (role_id,)).fetchone()
        if row is None:
            raise SovereigntyRecordNotFoundError(f"CurrentRole not found: {role_id}")
        return CurrentRole(
            id=row["id"],
            name=row["name"],
            responsibilities=_json_load(row["responsibilities_json"], []),
            allowed_focus=_json_load(row["allowed_focus_json"], []),
            forbidden_focus=_json_load(row["forbidden_focus_json"], []),
            active_from=_dt(row["active_from"]),
            active_to=_optional_dt(row["active_to"]),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    def list(self, limit: int = 50, *, active_only: bool = False) -> list[CurrentRole]:
        sql = "SELECT id FROM current_roles"
        params: list[Any] = []
        if active_only:
            sql += " WHERE active_to IS NULL"
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with connect(self.database_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self.get(row["id"]) for row in rows]

    def update_active(self, role_id: str) -> CurrentRole:
        self.get(role_id)
        now = utc_now().isoformat()
        with connect(self.database_path) as connection:
            connection.execute(
                """
                UPDATE current_roles
                SET active_to = ?, updated_at = ?
                WHERE active_to IS NULL AND id != ?
                """,
                (now, now, role_id),
            )
            connection.execute(
                "UPDATE current_roles SET active_to = NULL, updated_at = ? WHERE id = ?",
                (now, role_id),
            )
        return self.get(role_id)


class AttentionBudgetRepository:
    def __init__(self, database_path: Path | None = None):
        self.database_path = initialize_sovereignty_database(database_path)

    def add(self, budget: AttentionBudget) -> AttentionBudget:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO attention_budgets (
                    id, budget_date, total_minutes, research_minutes, build_minutes,
                    review_minutes, content_minutes, hard_limits_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    budget.id,
                    budget.date.isoformat(),
                    budget.total_minutes,
                    budget.research_minutes,
                    budget.build_minutes,
                    budget.review_minutes,
                    budget.content_minutes,
                    _json_dump(budget.hard_limits),
                    budget.created_at.isoformat(),
                    budget.updated_at.isoformat(),
                ),
            )
        return budget

    def get(self, budget_id: str) -> AttentionBudget:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM attention_budgets WHERE id = ?",
                (budget_id,),
            ).fetchone()
        if row is None:
            raise SovereigntyRecordNotFoundError(f"AttentionBudget not found: {budget_id}")
        return AttentionBudget(
            id=row["id"],
            date=_date(row["budget_date"]),
            total_minutes=row["total_minutes"],
            research_minutes=row["research_minutes"],
            build_minutes=row["build_minutes"],
            review_minutes=row["review_minutes"],
            content_minutes=row["content_minutes"],
            hard_limits=_json_load(row["hard_limits_json"], {}),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    def list(self, limit: int = 50) -> list[AttentionBudget]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT id FROM attention_budgets ORDER BY budget_date DESC, updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self.get(row["id"]) for row in rows]

    def get_by_date(self, budget_date: date) -> list[AttentionBudget]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT id FROM attention_budgets WHERE budget_date = ? ORDER BY updated_at DESC",
                (budget_date.isoformat(),),
            ).fetchall()
        return [self.get(row["id"]) for row in rows]


class NotToDoRepository:
    def __init__(self, database_path: Path | None = None):
        self.database_path = initialize_sovereignty_database(database_path)

    def add(self, item: NotToDoItem) -> NotToDoItem:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO not_to_do_items (
                    id, title, reason, scope, active, expires_at,
                    related_intent_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.title,
                    item.reason,
                    item.scope.value,
                    1 if item.active else 0,
                    item.expires_at.isoformat() if item.expires_at else None,
                    item.related_intent_id,
                    item.created_at.isoformat(),
                    item.updated_at.isoformat(),
                ),
            )
        return item

    def get(self, item_id: str) -> NotToDoItem:
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT * FROM not_to_do_items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise SovereigntyRecordNotFoundError(f"NotToDoItem not found: {item_id}")
        return NotToDoItem(
            id=row["id"],
            title=row["title"],
            reason=row["reason"],
            scope=NotToDoScope(row["scope"]),
            active=bool(row["active"]),
            expires_at=_optional_dt(row["expires_at"]),
            related_intent_id=row["related_intent_id"],
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    def list(self, limit: int = 50, *, active: bool | None = None) -> list[NotToDoItem]:
        sql = "SELECT id FROM not_to_do_items"
        params: list[Any] = []
        if active is not None:
            sql += " WHERE active = ?"
            params.append(1 if active else 0)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with connect(self.database_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self.get(row["id"]) for row in rows]

    def update_active(self, item_id: str, *, active: bool) -> NotToDoItem:
        self.get(item_id)
        now = utc_now().isoformat()
        with connect(self.database_path) as connection:
            connection.execute(
                "UPDATE not_to_do_items SET active = ?, updated_at = ? WHERE id = ?",
                (1 if active else 0, now, item_id),
            )
        return self.get(item_id)


class SovereigntyRepository:
    def __init__(self, database_path: Path | None = None):
        self.database_path = initialize_sovereignty_database(database_path)
        self.constitutions = CognitiveConstitutionRepository(self.database_path)
        self.intents = IntentRepository(self.database_path)
        self.roles = CurrentRoleRepository(self.database_path)
        self.attention_budgets = AttentionBudgetRepository(self.database_path)
        self.not_to_do = NotToDoRepository(self.database_path)

