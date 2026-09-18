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
    def __init__(self):
        super().__init__()
        self.backend = "mongodb"
        from pymongo import MongoClient
        # 5 000 ms — enough for MongoDB Atlas (~150-300 ms RTT) while still
        # failing fast for a genuinely absent local server
        self.client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
        self.database = self.client[settings.mongodb_database]
        self.client.admin.command("ping")

    def replace_all(self, state: RepositoryState) -> None:
        for collection in COLLECTIONS:
            target = self.database[collection]
            target.delete_many({})
            records = getattr(state, collection)
            if records:
                target.insert_many(deepcopy(records))
        self.state = state

    def all(self, collection: str) -> list[dict[str, Any]]:
        return [{key: value for key, value in item.items() if key != "_id"} for item in self.database[collection].find({}, {"_id": 0})]

    def find_one(self, collection: str, field: str, value: Any) -> dict[str, Any] | None:
        item = self.database[collection].find_one({field: value}, {"_id": 0})
        return item

    def find_many(self, collection: str, field: str | None = None, value: Any = None) -> list[dict[str, Any]]:
        query = {} if field is None else {field: value}
        return list(self.database[collection].find(query, {"_id": 0}))

    def insert(self, collection: str, item: dict[str, Any]) -> dict[str, Any]:
        self.database[collection].insert_one(deepcopy(item))
        return item

    def update(self, collection: str, field: str, value: Any, changes: dict[str, Any]) -> dict[str, Any] | None:
        self.database[collection].update_one({field: value}, {"$set": changes})
        return self.find_one(collection, field, value)


def create_repository() -> MemoryRepository:
    try:
        return MongoRepository()
    except Exception as error:
        print(f"MongoDB unavailable; using deterministic in-memory demo repository ({error.__class__.__name__}).")
        return MemoryRepository()
