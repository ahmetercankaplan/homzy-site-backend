import copy
import re
from typing import Any, Dict, List, Optional


def _get_value(doc: Dict[str, Any], dotted_key: str) -> Any:
    """Support dotted paths like 'agent_info.id'."""
    parts = dotted_key.split(".")
    value: Any = doc
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def _matches(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
    """Very small subset of Mongo style matching used in this API."""
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(doc, sub) for sub in expected):
                return False
            continue

        actual = _get_value(doc, key)
        if isinstance(expected, dict):
            if "$regex" in expected:
                pattern = expected["$regex"]
                flags = re.IGNORECASE if expected.get("$options", "") == "i" else 0
                if not isinstance(actual, str) or not re.search(pattern, actual, flags):
                    return False
            if "$gte" in expected and (actual is None or actual < expected["$gte"]):
                return False
            if "$lte" in expected and (actual is None or actual > expected["$lte"]):
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
        else:
            if actual != expected:
                return False
    return True


def _apply_projection(doc: Dict[str, Any], projection: Optional[Dict[str, int]]) -> Dict[str, Any]:
    if not projection:
        return copy.deepcopy(doc)

    result = copy.deepcopy(doc)
    for key, include in projection.items():
        if include == 0 and key in result:
            result.pop(key, None)
    return result


class FakeCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self.docs = docs

    async def to_list(self, limit: int) -> List[Dict[str, Any]]:
        return self.docs[:limit]


class FakeCollection:
    def __init__(self, initial: Optional[List[Dict[str, Any]]] = None):
        self.data: List[Dict[str, Any]] = initial or []

    async def find_one(self, query: Dict[str, Any], projection: Optional[Dict[str, int]] = None) -> Optional[Dict[str, Any]]:
        for doc in self.data:
            if _matches(doc, query):
                return _apply_projection(doc, projection)
        return None

    async def insert_one(self, document: Dict[str, Any]) -> None:
        self.data.append(copy.deepcopy(document))

    async def delete_one(self, query: Dict[str, Any]) -> None:
        self.data = [doc for doc in self.data if not _matches(doc, query)]

    async def delete_many(self, query: Dict[str, Any]) -> None:
        self.data = [doc for doc in self.data if not _matches(doc, query)]

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> None:
        for idx, doc in enumerate(self.data):
            if _matches(doc, query):
                if "$set" in update:
                    new_doc = copy.deepcopy(doc)
                    for key, value in update["$set"].items():
                        new_doc[key] = value
                    self.data[idx] = new_doc
                return

    async def count_documents(self, query: Dict[str, Any]) -> int:
        return len([doc for doc in self.data if _matches(doc, query)])

    def find(self, query: Dict[str, Any], projection: Optional[Dict[str, int]] = None) -> "FakeCursor":
        filtered = [_apply_projection(doc, projection) for doc in self.data if _matches(doc, query)]
        return FakeCursor(filtered)


class InMemoryDB:
    """Tiny drop-in replacement for motor's database object used in this app."""

    def __init__(self, properties: List[Dict[str, Any]], plans: List[Dict[str, Any]]):
        self.properties = FakeCollection(properties)
        self.favorites = FakeCollection([])
        self.sessions = FakeCollection([])
        self.users = FakeCollection([])
        self.viewing_requests = FakeCollection([])
        self.plans = FakeCollection(plans)

    def close(self) -> None:  # parity with AsyncIOMotorClient.close
        return None
