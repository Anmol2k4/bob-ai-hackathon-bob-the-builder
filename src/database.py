from __future__ import annotations
from copy import deepcopy
from typing import Any

from config import settings
from models import COLLECTIONS, RepositoryState


class MemoryRepository:
    def __init__(self, state: RepositoryState | None = None):
        self.state = state or RepositoryState()
        self.backend = "memory"

    def replace_all(self, state: RepositoryState) -> None:
        self.state = state

    def all(self, collection: str) -> list[dict[str, Any]]:
        # Shallow list copy — callers must not mutate individual dicts in place.
        # Use deepcopy only when a caller needs a fully independent copy.
        return list(getattr(self.state, collection))

    def find_one(self, collection: str, field: str, value: Any) -> dict[str, Any] | None:
        return next((item for item in getattr(self.state, collection) if item.get(field) == value), None)

    def find_many(self, collection: str, field: str | None = None, value: Any = None) -> list[dict[str, Any]]:
        items = getattr(self.state, collection)
        if field is None:
            return list(items)
        return [item for item in items if item.get(field) == value]

    def insert(self, collection: str, item: dict[str, Any]) -> dict[str, Any]:
        getattr(self.state, collection).append(item)
        return item

    def update(self, collection: str, field: str, value: Any, changes: dict[str, Any]) -> dict[str, Any] | None:
        items = getattr(self.state, collection)
        for item in items:
            if item.get(field) == value:
                item.update(changes)
                return item
        return None


class MongoRepository(MemoryRepository):
    """
    Write-through cache over MongoDB Atlas.

    ALL reads are served from the in-memory RepositoryState (zero network
    latency after startup). Writes (insert / update / replace_all) go to
    both the in-memory state AND MongoDB so the database stays in sync.

    Startup: loads every collection from Atlas once into self.state.
    """

    def __init__(self):
        super().__init__()
        self.backend = "mongodb"
        from pymongo import MongoClient
        self.client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
            # Keep a small connection pool — we don't need many connections
            maxPoolSize=5,
        )
        self.database = self.client[settings.mongodb_database]
        self.client.admin.command("ping")
        # ── Warm the in-memory cache from Atlas (one batch read per collection) ──
        self._warm_cache()

    def _warm_cache(self) -> None:
        """Load every collection from Atlas into self.state once at startup."""
        print("  Loading data from MongoDB Atlas...", flush=True)
        for collection in COLLECTIONS:
            docs = [
                {k: v for k, v in doc.items() if k != "_id"}
                for doc in self.database[collection].find({}, {"_id": 0})
            ]
            getattr(self.state, collection).extend(docs)
        total = sum(len(getattr(self.state, c)) for c in COLLECTIONS)
        print(f"  Cache warm: {total} documents loaded.", flush=True)

    def replace_all(self, state: RepositoryState) -> None:
        """Replace all data in both Atlas and the in-memory cache."""
        for collection in COLLECTIONS:
            target = self.database[collection]
            target.delete_many({})
            records = getattr(state, collection)
            if records:
                target.insert_many(deepcopy(records))
        # Update in-memory state
        self.state = state

    # ── Reads: served entirely from in-memory cache (MemoryRepository) ──
    # all(), find_one(), find_many() are inherited unchanged — no Atlas calls.

    def insert(self, collection: str, item: dict[str, Any]) -> dict[str, Any]:
        """Write to both Atlas and in-memory cache."""
        self.database[collection].insert_one(deepcopy(item))
        getattr(self.state, collection).append(item)
        return item

    def update(self, collection: str, field: str, value: Any, changes: dict[str, Any]) -> dict[str, Any] | None:
        """Write to both Atlas and in-memory cache."""
        self.database[collection].update_one({field: value}, {"$set": changes})
        # Update in-memory (reuse MemoryRepository logic)
        items = getattr(self.state, collection)
        for item in items:
            if item.get(field) == value:
                item.update(changes)
                return item
        return None


def create_repository() -> MemoryRepository:
    try:
        return MongoRepository()
    except Exception as error:
        print(f"MongoDB unavailable; using deterministic in-memory demo repository ({error.__class__.__name__}).")
        return MemoryRepository()
