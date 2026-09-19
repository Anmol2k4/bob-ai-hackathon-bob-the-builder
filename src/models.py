from dataclasses import dataclass, field
from typing import Any


ROLES = {"STUDY_MANAGER", "SITE_COORDINATOR", "AUDITOR", "SYSTEM_ADMIN"}


@dataclass
class User:
    user_id: str
    name: str
    email: str
    password_hash: str
    role: str
    site_id: str | None = None


@dataclass
class RepositoryState:
    users: list[dict[str, Any]] = field(default_factory=list)
    medicines: list[dict[str, Any]] = field(default_factory=list)
    trials: list[dict[str, Any]] = field(default_factory=list)
    sites: list[dict[str, Any]] = field(default_factory=list)
    patients: list[dict[str, Any]] = field(default_factory=list)
    protocols: list[dict[str, Any]] = field(default_factory=list)
    visits: list[dict[str, Any]] = field(default_factory=list)
    medications: list[dict[str, Any]] = field(default_factory=list)
    deviations: list[dict[str, Any]] = field(default_factory=list)
    risk_scores: list[dict[str, Any]] = field(default_factory=list)
    capa_records: list[dict[str, Any]] = field(default_factory=list)
    audit_events: list[dict[str, Any]] = field(default_factory=list)
    risk_history: list[dict[str, Any]] = field(default_factory=list)


COLLECTIONS = tuple(RepositoryState.__dataclass_fields__)
