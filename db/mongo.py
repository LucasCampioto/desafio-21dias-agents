from bson import ObjectId
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from config import get_settings

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = MongoClient(settings["mongodb_uri"])
    return _client


def get_db() -> Database:
    client = get_client()
    db_name = get_settings()["mongodb_uri"].rsplit("/", 1)[-1]
    if "?" in db_name:
        db_name = db_name.split("?", 1)[0]
    return client[db_name]


def get_collection(name: str) -> Collection:
    return get_db()[name]


def try_object_id(value: str | None) -> ObjectId | None:
    """Retorna ObjectId válido ou None (IDs inválidos não quebram o pipeline)."""
    if value is None or value == "":
        return None
    try:
        return ObjectId(value)
    except Exception:
        return None
