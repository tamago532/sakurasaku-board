import json
import os
import secrets
import threading
import time
import uuid

THREADS_TABLE = "threads"
REPLIES_TABLE = "replies"
SETTINGS_TABLE = "settings"
THREAD_PK = "thread"
MAX_MS = 10**13


def _now_ms():
    return int(time.time() * 1000)


def new_thread_id():
    return f"{MAX_MS - _now_ms():013d}-{uuid.uuid4().hex[:8]}"


def new_reply_id():
    return f"{_now_ms():013d}-{uuid.uuid4().hex[:8]}"


class LocalStore:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.db_path = os.path.join(base_dir, "db.json")
        self.lock = threading.Lock()
        os.makedirs(base_dir, exist_ok=True)
        if not os.path.exists(self.db_path):
            self._write({"threads": {}, "replies": {}})

    def secret_key(self):
        with self.lock:
            db = self._read()
            if "secret" not in db:
                db["secret"] = secrets.token_hex(32)
                self._write(db)
            return db["secret"]

    def _read(self):
        with open(self.db_path, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, db):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False)

    def list_threads(self):
        with self.lock:
            threads = self._read()["threads"]
        return [dict(v, id=k) for k, v in sorted(threads.items())]

    def get_thread(self, tid):
        with self.lock:
            t = self._read()["threads"].get(tid)
        return dict(t, id=tid) if t else None

    def add_thread(self, data):
        tid = new_thread_id()
        with self.lock:
            db = self._read()
            db["threads"][tid] = data
            db["replies"][tid] = {}
            self._write(db)
        return tid

    def update_thread(self, tid, **fields):
        with self.lock:
            db = self._read()
            if tid in db["threads"]:
                db["threads"][tid].update(fields)
                self._write(db)

    def delete_thread(self, tid):
        with self.lock:
            db = self._read()
            db["threads"].pop(tid, None)
            replies = db["replies"].pop(tid, {})
            self._write(db)
        return [dict(v, id=k) for k, v in replies.items()]

    def list_replies(self, tid):
        with self.lock:
            replies = self._read()["replies"].get(tid, {})
        return [dict(v, id=k) for k, v in sorted(replies.items())]

    def get_reply(self, tid, rid):
        with self.lock:
            r = self._read()["replies"].get(tid, {}).get(rid)
        return dict(r, id=rid) if r else None

    def add_reply(self, tid, data):
        rid = new_reply_id()
        with self.lock:
            db = self._read()
            db["replies"].setdefault(tid, {})[rid] = data
            self._write(db)
        return rid

    def delete_reply(self, tid, rid):
        with self.lock:
            db = self._read()
            db["replies"].get(tid, {}).pop(rid, None)
            self._write(db)

    def _image_path(self, container, name):
        folder = os.path.join(self.base_dir, container)
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, name)

    def save_image(self, container, name, data, content_type):
        with open(self._image_path(container, name), "wb") as f:
            f.write(data)

    def load_image(self, container, name):
        path = self._image_path(container, name)
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    def image_exists(self, container, name):
        return os.path.exists(self._image_path(container, name))

    def delete_image(self, container, name):
        path = self._image_path(container, name)
        if os.path.exists(path):
            os.remove(path)


class AzureStore:
    def __init__(self, account_name):
        from azure.data.tables import TableServiceClient
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        credential = DefaultAzureCredential()
        tables = TableServiceClient(f"https://{account_name}.table.core.windows.net", credential=credential)
        self.threads = tables.create_table_if_not_exists(THREADS_TABLE)
        self.replies = tables.create_table_if_not_exists(REPLIES_TABLE)
        self.settings = tables.create_table_if_not_exists(SETTINGS_TABLE)
        self.blobs = BlobServiceClient(f"https://{account_name}.blob.core.windows.net", credential=credential)
        self._containers = set()

    def secret_key(self):
        from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

        try:
            return self.settings.get_entity("app", "secret")["value"]
        except ResourceNotFoundError:
            pass
        try:
            self.settings.create_entity({"PartitionKey": "app", "RowKey": "secret", "value": secrets.token_hex(32)})
        except ResourceExistsError:
            pass
        return self.settings.get_entity("app", "secret")["value"]

    @staticmethod
    def _clean(entity):
        data = {k: v for k, v in entity.items() if k not in ("PartitionKey", "RowKey")}
        data["id"] = entity["RowKey"]
        return data

    def list_threads(self):
        rows = self.threads.query_entities("PartitionKey eq @pk", parameters={"pk": THREAD_PK})
        return sorted((self._clean(e) for e in rows), key=lambda t: t["id"])

    def get_thread(self, tid):
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return self._clean(self.threads.get_entity(THREAD_PK, tid))
        except ResourceNotFoundError:
            return None

    def add_thread(self, data):
        tid = new_thread_id()
        self.threads.create_entity(dict(data, PartitionKey=THREAD_PK, RowKey=tid))
        return tid

    def update_thread(self, tid, **fields):
        from azure.data.tables import UpdateMode

        self.threads.update_entity(dict(fields, PartitionKey=THREAD_PK, RowKey=tid), mode=UpdateMode.MERGE)

    def delete_thread(self, tid):
        replies = self.list_replies(tid)
        for r in replies:
            self.replies.delete_entity(tid, r["id"])
        self.threads.delete_entity(THREAD_PK, tid)
        return replies

    def list_replies(self, tid):
        rows = self.replies.query_entities("PartitionKey eq @pk", parameters={"pk": tid})
        return sorted((self._clean(e) for e in rows), key=lambda r: r["id"])

    def get_reply(self, tid, rid):
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return self._clean(self.replies.get_entity(tid, rid))
        except ResourceNotFoundError:
            return None

    def add_reply(self, tid, data):
        rid = new_reply_id()
        self.replies.create_entity(dict(data, PartitionKey=tid, RowKey=rid))
        return rid

    def delete_reply(self, tid, rid):
        self.replies.delete_entity(tid, rid)

    def _container(self, name):
        client = self.blobs.get_container_client(name)
        if name not in self._containers:
            if not client.exists():
                client.create_container()
            self._containers.add(name)
        return client

    def save_image(self, container, name, data, content_type):
        from azure.storage.blob import ContentSettings

        self._container(container).upload_blob(
            name, data, overwrite=True, content_settings=ContentSettings(content_type=content_type)
        )

    def load_image(self, container, name):
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return self._container(container).download_blob(name).readall()
        except ResourceNotFoundError:
            return None

    def image_exists(self, container, name):
        return self._container(container).get_blob_client(name).exists()

    def delete_image(self, container, name):
        from azure.core.exceptions import ResourceNotFoundError

        try:
            self._container(container).delete_blob(name)
        except ResourceNotFoundError:
            pass


def get_store(local_dir):
    account_name = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
    if account_name:
        return AzureStore(account_name)
    return LocalStore(local_dir)
