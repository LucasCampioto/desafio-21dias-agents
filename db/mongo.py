from bson import ObjectId
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from urllib.parse import urlparse

from config import get_settings, require_production_mongo

_client: MongoClient | None = None
DEFAULT_DB_NAME = "test"


def get_client() -> MongoClient:
    global _client
    if _client is None:
        require_production_mongo()
        settings = get_settings()
        _client = MongoClient(
            settings["mongodb_uri"],
            serverSelectionTimeoutMS=4000,
            connectTimeoutMS=4000,
            socketTimeoutMS=8000,
            maxPoolSize=5,
        )
    return _client


def resolve_db_name(uri: str) -> str:
    """Extrai o nome do DB da URI; se vier vazio (…mongodb.net/?…), usa o padrão do projeto."""
    try:
        parsed = urlparse(uri)
        path = (parsed.path or "").lstrip("/")
        if path:
            return path.split("/")[0] or DEFAULT_DB_NAME
    except Exception:
        pass

    tail = uri.rsplit("/", 1)[-1]
    if "?" in tail:
        tail = tail.split("?", 1)[0]
    return tail.strip() or DEFAULT_DB_NAME


def get_db() -> Database:
    client = get_client()
    db_name = resolve_db_name(get_settings()["mongodb_uri"])
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
