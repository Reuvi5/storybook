"""
Where books are stored, so they persist between visits.

Two interchangeable backends with the same methods:

  AwsStorage   - production. Book records in a DynamoDB table, images in a private S3 bucket.
                 Used when S3_BUCKET and DYNAMODB_TABLE are set.
  LocalStorage - development. Everything in a local folder (local_data/), no AWS account needed.

A book record looks like:
  {
    "book_id": "3f2c...",            # random id, used in URLs
    "created_at": 1730000000,        # unix seconds
    "updated_at": 1730000042,
    "status": "generating" | "done" | "needs_retry" | "failed",
    "details": {"name": ..., "age": ..., ...},   # what the user typed in
    "images": {"character": {"status": "done"}, "page1": {"status": "drawing"}, ...}
  }
Image statuses: waiting -> drawing -> done | failed
"""

import json
import logging
import os
import re
import shutil
import threading
import time
from decimal import Decimal
from pathlib import Path

log = logging.getLogger("storybook.storage")

SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
SAFE_PK = re.compile(r"^[A-Za-z0-9_#-]{1,128}$")
SAFE_BLOB = re.compile(r"^(stories|books)/[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$")


def book_key(user_id, book_id, filename):
    """Where a book's files live: books/<user>/<book>/<file>."""
    _check(user_id, book_id)
    return f"books/{user_id}/{book_id}/{filename}"


def story_key(story_id, filename):
    """Where a story's shared files live (character bible, scene plates): stories/<story>/<file>."""
    _check(story_id)
    return f"stories/{story_id}/{filename}"


def _check_blob(key):
    if not SAFE_BLOB.match(key) or ".." in key:
        raise ValueError("bad key")


CONTENT_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".pdf": "application/pdf", ".json": "application/json"}


def content_type(key):
    return CONTENT_TYPES.get(os.path.splitext(key)[1], "application/octet-stream")


def image_file(name: str) -> tuple:
    """(file name, content type) for an image name like "photo", "character", "page1"."""
    if name == "photo":
        return "photo.jpg", "image/jpeg"
    return f"{name}.png", "image/png"


def _check(*ids):
    for value in ids:
        if not SAFE_ID.match(str(value)):
            raise ValueError("bad id")


# ---------------------------------------------------------------------------
# Local folder (development)
# ---------------------------------------------------------------------------
class LocalStorage:
    kind = "local"

    def __init__(self, root: Path):
        self.root = Path(root)
        self.lock = threading.Lock()  # book.json is rewritten by several threads at once

    def _user_dir(self, user_id):
        _check(user_id)
        return self.root / "users" / user_id

    def _book_dir(self, user_id, book_id):
        _check(user_id, book_id)
        return self._user_dir(user_id) / "books" / book_id

    def _read(self, path: Path):
        return json.loads(path.read_text()) if path.is_file() else None

    def _write(self, path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(path)

    # users
    def save_user(self, user: dict):
        with self.lock:
            path = self._user_dir(user["id"]) / "profile.json"
            profile = self._read(path) or {"first_login": int(time.time())}
            profile.update({"email": user["email"], "name": user.get("name", ""), "last_login": int(time.time())})
            self._write(path, profile)

    # books
    def create_book(self, user_id, book: dict):
        with self.lock:
            self._write(self._book_dir(user_id, book["book_id"]) / "book.json", book)

    def get_book(self, user_id, book_id):
        try:
            return self._read(self._book_dir(user_id, book_id) / "book.json")
        except ValueError:
            return None

    def list_books(self, user_id):
        books_dir = self._user_dir(user_id) / "books"
        if not books_dir.is_dir():
            return []
        books = [self._read(d / "book.json") for d in books_dir.iterdir() if (d / "book.json").is_file()]
        return sorted(books, key=lambda b: b["created_at"], reverse=True)

    def set_image_status(self, user_id, book_id, name, status, error=None, **extra):
        with self.lock:
            path = self._book_dir(user_id, book_id) / "book.json"
            book = self._read(path)
            if book is None:
                return
            book["images"][name] = {"status": status, **({"error": error} if error else {}), **extra}
            book["updated_at"] = int(time.time())
            self._write(path, book)

    def update_book(self, user_id, book_id, **fields):
        with self.lock:
            path = self._book_dir(user_id, book_id) / "book.json"
            book = self._read(path)
            if book is None:
                return
            book.update(fields)
            book["updated_at"] = int(time.time())
            self._write(path, book)

    def delete_book(self, user_id, book_id):
        with self.lock:
            shutil.rmtree(self._book_dir(user_id, book_id), ignore_errors=True)
            shutil.rmtree(self.root / "blobs" / "books" / user_id / book_id, ignore_errors=True)

    # images
    def put_image(self, user_id, book_id, name, data: bytes):
        file_name, _ = image_file(name)
        path = self._book_dir(user_id, book_id) / file_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_image(self, user_id, book_id, name):
        file_name, _ = image_file(name)
        path = self._book_dir(user_id, book_id) / file_name
        return path.read_bytes() if path.is_file() else None

    def image_url(self, user_id, book_id, name):
        return None  # the app serves local images itself

    # generic files (blobs) and records, used for story assets and book files
    def put_blob(self, key, data: bytes):
        _check_blob(key)
        path = self.root / "blobs" / key
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def get_blob(self, key):
        _check_blob(key)
        path = self.root / "blobs" / key
        return path.read_bytes() if path.is_file() else None

    def blob_url(self, key):
        return None  # the app serves local files itself

    def _record_path(self, pk, sk):
        if not SAFE_PK.match(pk) or not SAFE_PK.match(sk):
            raise ValueError("bad key")
        return self.root / "records" / pk.replace("#", "_") / (sk.replace("#", "_") + ".json")

    def put_record(self, pk, sk, item: dict):
        with self.lock:
            self._write(self._record_path(pk, sk), {**item, "sk": sk})

    def get_record(self, pk, sk):
        return self._read(self._record_path(pk, sk))

    def query_records(self, pk, prefix=""):
        folder = self._record_path(pk, "x").parent
        if not folder.is_dir():
            return []
        out = [self._read(f) for f in sorted(folder.glob("*.json"))]
        return [r for r in out if r and r["sk"].startswith(prefix)]

    def add_counters(self, pk, sk, **amounts):
        """Atomically add numbers to a record (creates it if missing)."""
        with self.lock:
            path = self._record_path(pk, sk)
            rec = self._read(path) or {"sk": sk}
            for k, v in amounts.items():
                rec[k] = rec.get(k, 0) + v
            self._write(path, rec)

    # wallet
    def _wallet_path(self, user_id):
        return self._user_dir(user_id) / "wallet.json"

    def _wallet(self, user_id):
        return self._read(self._wallet_path(user_id)) or {"balance_cents": 0, "txns": {}}

    def get_balance(self, user_id):
        return self._wallet(user_id)["balance_cents"]

    def add_txn(self, user_id, txn: dict, deposit_id=None):
        """Apply one ledger entry and change the balance by txn["amount_cents"], all or nothing.
        Returns "ok", "duplicate" (already recorded), or "insufficient" (would go below zero /
        over the deposit's refundable amount)."""
        with self.lock:
            w = self._wallet(user_id)
            if txn["txn_id"] in w["txns"]:
                return "duplicate"
            new_balance = w["balance_cents"] + txn["amount_cents"]
            if new_balance < 0:
                return "insufficient"
            if deposit_id:
                dep = w["txns"].get(deposit_id)
                refund = -txn["amount_cents"]
                if not dep or dep.get("refunded_cents", 0) + refund > dep["amount_cents"]:
                    return "insufficient"
                dep["refunded_cents"] = dep.get("refunded_cents", 0) + refund
            w["balance_cents"] = new_balance
            w["txns"][txn["txn_id"]] = txn
            self._write(self._wallet_path(user_id), w)
            return "ok"

    def update_txn(self, user_id, txn_id, **fields):
        with self.lock:
            w = self._wallet(user_id)
            if txn_id in w["txns"]:
                w["txns"][txn_id].update(fields)
                self._write(self._wallet_path(user_id), w)

    def get_txn(self, user_id, txn_id):
        return self._wallet(user_id)["txns"].get(txn_id)

    def list_txns(self, user_id):
        return sorted(self._wallet(user_id)["txns"].values(), key=lambda t: t["created_at"], reverse=True)


# ---------------------------------------------------------------------------
# AWS (production): DynamoDB for records, S3 for images
# ---------------------------------------------------------------------------
def _plain(value):
    """DynamoDB returns numbers as Decimal; turn them back into ints/floats."""
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def _dynamo_safe(value):
    """DynamoDB doesn't take Python floats: store them as Decimal."""
    if isinstance(value, float):
        return Decimal(str(round(value, 4)))
    if isinstance(value, dict):
        return {k: _dynamo_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_dynamo_safe(v) for v in value]
    return value


class AwsStorage:
    """
    DynamoDB table: partition key "user_id" (String), sort key "sk" (String).
      sk = "PROFILE"          -> the user's profile
      sk = "BOOK#<book_id>"   -> one book
    S3 bucket (private): books/<user_id>/<book_id>/<image file>
    """
    kind = "aws"

    def __init__(self, table_name: str, bucket: str, region: str):
        import boto3
        from botocore.config import Config

        pool = Config(max_pool_connections=40)  # 20 pages run at once; the default of 10 makes them queue
        self.table = boto3.resource("dynamodb", region_name=region, config=pool).Table(table_name)
        # Use the bucket's own regional address (e.g. s3.us-east-2.amazonaws.com). Otherwise the
        # temporary image links point at the global S3 address, which rejects them for buckets
        # outside us-east-1, and pictures don't show on the page.
        self.s3 = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=f"https://s3.{region}.amazonaws.com",
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}, max_pool_connections=40),
        )
        self.bucket = bucket

    @staticmethod
    def _key(user_id, book_id):
        _check(user_id, book_id)
        return {"user_id": user_id, "sk": f"BOOK#{book_id}"}

    @staticmethod
    def _strip(item):
        if not item:
            return None
        item = _plain(dict(item))
        item.pop("user_id", None)
        item.pop("sk", None)
        return item

    def _s3_key(self, user_id, book_id, name):
        _check(user_id, book_id)
        return f"books/{user_id}/{book_id}/{image_file(name)[0]}"

    # users
    def save_user(self, user: dict):
        _check(user["id"])
        now = int(time.time())
        self.table.update_item(
            Key={"user_id": user["id"], "sk": "PROFILE"},
            UpdateExpression="SET email = :e, #n = :n, last_login = :t, first_login = if_not_exists(first_login, :t)",
            ExpressionAttributeNames={"#n": "name"},
            ExpressionAttributeValues={":e": user["email"], ":n": user.get("name", ""), ":t": now},
        )

    # books
    def create_book(self, user_id, book: dict):
        self.table.put_item(Item=_dynamo_safe({**self._key(user_id, book["book_id"]), **book}))

    def get_book(self, user_id, book_id):
        try:
            key = self._key(user_id, book_id)
        except ValueError:
            return None
        return self._strip(self.table.get_item(Key=key).get("Item"))

    def list_books(self, user_id):
        from boto3.dynamodb.conditions import Key

        _check(user_id)
        items, kwargs = [], {
            "KeyConditionExpression": Key("user_id").eq(user_id) & Key("sk").begins_with("BOOK#")
        }
        while True:
            resp = self.table.query(**kwargs)
            items += resp.get("Items", [])
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        books = [self._strip(i) for i in items]
        return sorted(books, key=lambda b: b["created_at"], reverse=True)

    def set_image_status(self, user_id, book_id, name, status, error=None, **extra):
        # Updates just this one image's entry, so parallel pages don't overwrite each other.
        value = _dynamo_safe({"status": status, **({"error": error} if error else {}), **extra})
        self.table.update_item(
            Key=self._key(user_id, book_id),
            UpdateExpression="SET #imgs.#img = :v, #upd = :t",
            ExpressionAttributeNames={"#imgs": "images", "#img": name, "#upd": "updated_at"},
            ExpressionAttributeValues={":v": value, ":t": int(time.time())},
        )

    def update_book(self, user_id, book_id, **fields):
        fields["updated_at"] = int(time.time())
        names = {f"#f{i}": k for i, k in enumerate(fields)}
        values = {f":v{i}": _dynamo_safe(v) for i, v in enumerate(fields.values())}
        sets = ", ".join(f"#f{i} = :v{i}" for i in range(len(fields)))
        self.table.update_item(
            Key=self._key(user_id, book_id),
            UpdateExpression=f"SET {sets}",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def delete_book(self, user_id, book_id):
        prefix = self._s3_key(user_id, book_id, "x").rsplit("/", 1)[0] + "/"
        resp = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        objects = [{"Key": o["Key"]} for o in resp.get("Contents", [])]
        if objects:
            self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})
        self.table.delete_item(Key=self._key(user_id, book_id))

    # images
    def put_image(self, user_id, book_id, name, data: bytes):
        self.s3.put_object(
            Bucket=self.bucket,
            Key=self._s3_key(user_id, book_id, name),
            Body=data,
            ContentType=image_file(name)[1],
        )

    def get_image(self, user_id, book_id, name):
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=self._s3_key(user_id, book_id, name))
        except self.s3.exceptions.NoSuchKey:
            return None
        return obj["Body"].read()

    def image_url(self, user_id, book_id, name):
        """A temporary (15-minute) link to a private image, so the bucket never has to be public."""
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": self._s3_key(user_id, book_id, name)},
            ExpiresIn=900,
        )

    # generic files (blobs) and records, used for story assets and book files
    def put_blob(self, key, data: bytes):
        _check_blob(key)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type(key))

    def get_blob(self, key):
        _check_blob(key)
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.s3.exceptions.NoSuchKey:
            return None

    def blob_url(self, key, expires=900):
        _check_blob(key)
        return self.s3.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires)

    def put_record(self, pk, sk, item: dict):
        if not SAFE_PK.match(pk) or not SAFE_PK.match(sk):
            raise ValueError("bad key")
        self.table.put_item(Item=_dynamo_safe({**item, "user_id": pk, "sk": sk}))

    def get_record(self, pk, sk):
        item = self.table.get_item(Key={"user_id": pk, "sk": sk}).get("Item")
        if not item:
            return None
        item = _plain(dict(item))
        item.pop("user_id", None)
        return item

    def query_records(self, pk, prefix=""):
        from boto3.dynamodb.conditions import Key

        cond = Key("user_id").eq(pk) & Key("sk").begins_with(prefix) if prefix else Key("user_id").eq(pk)
        items, kwargs = [], {"KeyConditionExpression": cond}
        while True:
            resp = self.table.query(**kwargs)
            items += resp.get("Items", [])
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        out = []
        for i in items:
            i = _plain(dict(i))
            i.pop("user_id", None)
            out.append(i)
        return out

    def add_counters(self, pk, sk, **amounts):
        """Atomically add numbers to a record (DynamoDB ADD; creates it if missing)."""
        if not SAFE_PK.match(pk) or not SAFE_PK.match(sk):
            raise ValueError("bad key")
        names = {f"#a{i}": k for i, k in enumerate(amounts)}
        values = {f":a{i}": _dynamo_safe(v) for i, v in enumerate(amounts.values())}
        self.table.update_item(
            Key={"user_id": pk, "sk": sk},
            UpdateExpression="ADD " + ", ".join(f"#a{i} :a{i}" for i in range(len(amounts))),
            ExpressionAttributeNames=names, ExpressionAttributeValues=values,
        )

    # wallet
    # The balance lives on the PROFILE item (balance_cents). Every ledger entry is its own item,
    # sk = "TXN#<txn_id>". A balance change and its ledger entry are written in ONE DynamoDB
    # transaction, so they can never disagree, the balance can never go below zero, and the
    # same Stripe payment can never be credited twice.
    def get_balance(self, user_id):
        _check(user_id)
        item = self.table.get_item(Key={"user_id": user_id, "sk": "PROFILE"}).get("Item") or {}
        return int(item.get("balance_cents", 0))

    def add_txn(self, user_id, txn: dict, deposit_id=None):
        from botocore.exceptions import ClientError

        _check(user_id, txn["txn_id"])
        av = dict  # the table's client converts plain Python values to DynamoDB types itself
        amount = txn["amount_cents"]
        balance_update = {
            "TableName": self.table.name,
            "Key": av({"user_id": user_id, "sk": "PROFILE"}),
            "UpdateExpression": "SET balance_cents = if_not_exists(balance_cents, :zero) + :amt",
            "ExpressionAttributeValues": av({":zero": 0, ":amt": amount}),
        }
        if amount < 0:  # a debit: only if there's enough money
            balance_update["ConditionExpression"] = "balance_cents >= :need"
            balance_update["ExpressionAttributeValues"].update(av({":need": -amount}))
        items = [
            {"Update": balance_update},
            {"Put": {
                "TableName": self.table.name,
                "Item": av({"user_id": user_id, "sk": f"TXN#{txn['txn_id']}", **txn}),
                "ConditionExpression": "attribute_not_exists(sk)",
            }},
        ]
        if deposit_id:  # a refund: never more than what's left of that deposit
            _check(deposit_id)
            items.append({"Update": {
                "TableName": self.table.name,
                "Key": av({"user_id": user_id, "sk": f"TXN#{deposit_id}"}),
                "UpdateExpression": "SET refunded_cents = if_not_exists(refunded_cents, :zero) + :r",
                # deposits are always created with refunded_cents = 0
                "ConditionExpression": "attribute_exists(sk) AND refunded_cents <= :limit",
                "ExpressionAttributeValues": av({":zero": 0, ":r": -amount,
                                                 ":limit": self._deposit_limit(user_id, deposit_id, -amount)}),
            }})
        try:
            self.table.meta.client.transact_write_items(TransactItems=items)
            return "ok"
        except ClientError as e:
            if e.response["Error"]["Code"] != "TransactionCanceledException":
                raise
            reasons = [r.get("Code") for r in e.response.get("CancellationReasons", [])]
            if len(reasons) > 1 and reasons[1] == "ConditionalCheckFailed":
                return "duplicate"
            return "insufficient"

    def _deposit_limit(self, user_id, deposit_id, refund):
        """refunded_cents may be at most (deposit amount - this refund) before the refund is added."""
        dep = self.get_txn(user_id, deposit_id)
        return (dep["amount_cents"] - refund) if dep else -1

    def update_txn(self, user_id, txn_id, **fields):
        _check(user_id, txn_id)
        names = {f"#f{i}": k for i, k in enumerate(fields)}
        values = {f":v{i}": v for i, v in enumerate(fields.values())}
        self.table.update_item(
            Key={"user_id": user_id, "sk": f"TXN#{txn_id}"},
            UpdateExpression="SET " + ", ".join(f"#f{i} = :v{i}" for i in range(len(fields))),
            ConditionExpression="attribute_exists(sk)",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def get_txn(self, user_id, txn_id):
        _check(user_id, txn_id)
        item = self.table.get_item(Key={"user_id": user_id, "sk": f"TXN#{txn_id}"}).get("Item")
        return self._strip(item)

    def list_txns(self, user_id):
        from boto3.dynamodb.conditions import Key

        _check(user_id)
        items, kwargs = [], {"KeyConditionExpression": Key("user_id").eq(user_id) & Key("sk").begins_with("TXN#")}
        while True:
            resp = self.table.query(**kwargs)
            items += resp.get("Items", [])
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return sorted((self._strip(i) for i in items), key=lambda t: t["created_at"], reverse=True)


def get_storage():
    bucket = os.environ.get("S3_BUCKET")
    table = os.environ.get("DYNAMODB_TABLE")
    if bucket and table:
        region = os.environ.get("AWS_REGION", "us-east-1")
        log.info("storage=aws table=%s bucket=%s region=%s", table, bucket, region)
        return AwsStorage(table, bucket, region)
    root = Path(os.environ.get("LOCAL_DATA_DIR", Path(__file__).parent / "local_data"))
    log.warning("storage=local folder=%s (set S3_BUCKET and DYNAMODB_TABLE to use AWS)", root)
    return LocalStorage(root)
