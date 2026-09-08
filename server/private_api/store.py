import hashlib
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException

SCOPES = frozenset(
    {
        "notes:read",
        "notes:create",
        "notes:update",
        "references:read",
        "captures:read",
        "captures:create",
        "assets:read",
        "assets:create",
        "capabilities:delegate",
    }
)
AUDIENCE = "lamanotes-private-v1"


def opaque_id(prefix):
    return prefix + "-" + secrets.token_hex(16)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def missing():
    raise HTTPException(404, "Object unavailable.")


class PrivateStore:
    def __init__(self, root, owner_id="personal-owner"):
        self.root = Path(root).resolve() / ".private"
        self.root.mkdir(mode=0o700, exist_ok=True)
        self.assets = self.root / "assets"
        self.assets.mkdir(mode=0o700, exist_ok=True)
        self.owner_id = owner_id
        self.path = self.root / "integration.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS capabilities (
                    id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS objects (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                    creator TEXT, active INTEGER NOT NULL DEFAULT 1,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    actor TEXT NOT NULL, operation TEXT NOT NULL,
                    key TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    PRIMARY KEY (actor, operation, key)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS reserved_object
                    ON receipts(operation, object_id);
                CREATE TABLE IF NOT EXISTS reader_sessions (
                    digest TEXT PRIMARY KEY, capability_id TEXT NOT NULL,
                    note_id TEXT NOT NULL, expires_at INTEGER NOT NULL
                );
            """)
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def envelope(self, **values):
        return {
            "integrationVersion": 1,
            "domain": "personal",
            "ownerId": self.owner_id,
            **values,
        }

    def capability(self, capability_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM capabilities WHERE id=?", (capability_id,)
            ).fetchone()
        return (
            {**json.loads(row["payload"]), "revoked": bool(row["revoked"])}
            if row
            else None
        )

    def validate_chain(self, capability):
        seen = set()
        while capability:
            if (
                capability["capabilityId"] in seen
                or len(seen) > 8
                or capability["revoked"]
                or capability["expiresAt"] <= time.time()
            ):
                raise HTTPException(401, "Capability unavailable.")
            seen.add(capability["capabilityId"])
            parent = capability.get("parentId")
            if not parent:
                return
            capability = self.capability(parent)
            if not capability:
                break
        raise HTTPException(401, "Capability unavailable.")

    def authenticate(self, token):
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.connect() as db:
            row = db.execute(
                "SELECT id FROM capabilities WHERE digest=?", (digest,)
            ).fetchone()
        if not row:
            raise HTTPException(401, "Capability unavailable.")
        capability = self.capability(row["id"])
        self.validate_chain(capability)
        return capability

    @staticmethod
    def require(actor, scope):
        if actor is not None and scope not in actor["scopes"]:
            raise HTTPException(403, "Operation not granted.")

    def create_capability(self, actor, request):
        self.require(actor, "capabilities:delegate")
        scopes = set(request.scopes)
        if not scopes <= SCOPES:
            raise HTTPException(422, "Unknown capability scope.")
        expires = int(time.time()) + request.expires_in
        if actor:
            self.validate_chain(actor)
            if (
                not scopes <= set(actor["scopes"])
                or expires > actor["expiresAt"]
                or request.client_id != actor["clientId"]
                or (actor["jobId"] and request.job_id != actor["jobId"])
            ):
                raise HTTPException(
                    403, "Delegation must narrow the parent capability."
                )
        for value in request.note_ids:
            self.get_allowed(actor, value, "note")
        for value in request.capture_ids:
            self.get_allowed(actor, value, "capture")
        capability_id = opaque_id("lg")
        payload = self.envelope(
            capabilityId=capability_id,
            audience=AUDIENCE,
            clientId=request.client_id,
            jobId=request.job_id,
            expiresAt=expires,
            scopes=sorted(scopes),
            noteIds=sorted(set(request.note_ids)),
            captureIds=sorted(set(request.capture_ids)),
            parentId=actor["capabilityId"] if actor else None,
        )
        token = "lmp_" + secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute(
                "INSERT INTO capabilities(id,digest,payload) VALUES(?,?,?)",
                (
                    capability_id,
                    hashlib.sha256(token.encode()).hexdigest(),
                    canonical(payload),
                ),
            )
        return {**payload, "token": token}

    def list_capabilities(self):
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload,revoked FROM capabilities"
            ).fetchall()
        return [
            {**json.loads(row["payload"]), "revoked": bool(row["revoked"])}
            for row in rows
        ]

    def revoke_capability(self, actor, capability_id):
        candidate = self.capability(capability_id)
        if not candidate or (
            actor
            and not self.descendant(
                candidate["capabilityId"], actor["capabilityId"]
            )
        ):
            missing()
        with self.connect() as db:
            db.execute(
                "UPDATE capabilities SET revoked=1 WHERE id=?",
                (capability_id,),
            )

    def descendant(self, child, parent):
        seen = set()
        while child and child not in seen and len(seen) < 10:
            if child == parent:
                return True
            seen.add(child)
            cap = self.capability(child)
            child = cap.get("parentId") if cap else None
        return False

    def object(self, object_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM objects WHERE id=?", (object_id,)
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "kind": row["kind"],
            "creator": row["creator"],
            "active": bool(row["active"]),
            "payload": json.loads(row["payload"]),
        }

    def put_object(self, object_id, kind, payload, actor=None):
        with self.connect() as db:
            db.execute(
                "INSERT INTO objects(id,kind,creator,payload) VALUES(?,?,?,?)",
                (
                    object_id,
                    kind,
                    actor["capabilityId"] if actor else None,
                    canonical(payload),
                ),
            )

    def activate(self, object_id, active):
        with self.connect() as db:
            db.execute(
                "UPDATE objects SET active=? WHERE id=?",
                (int(active), object_id),
            )

    def update_payload(self, object_id, payload):
        with self.connect() as db:
            db.execute(
                "UPDATE objects SET payload=? WHERE id=?",
                (canonical(payload), object_id),
            )

    def allowed(self, actor, obj):
        if not obj or not obj["active"]:
            return False
        if actor is None:
            return True
        field = {"note": "noteIds", "capture": "captureIds"}.get(obj["kind"])
        if field and obj["id"] in actor[field]:
            return True
        if obj["creator"] and self.descendant(
            obj["creator"], actor["capabilityId"]
        ):
            return True
        creator = self.capability(obj["creator"]) if obj["creator"] else None
        if (
            creator
            and actor.get("jobId")
            and actor["jobId"] == creator["jobId"]
            and actor["clientId"] == creator["clientId"]
        ):
            return True
        if obj["kind"] == "asset":
            for parent in self.objects():
                if (
                    parent["kind"] in {"note", "capture"}
                    and obj["id"] in parent["payload"].get("assetIds", [])
                    and self.allowed(actor, parent)
                ):
                    return True
        return False

    def get_allowed(self, actor, object_id, kind):
        obj = self.object(object_id)
        if not obj or obj["kind"] != kind or not self.allowed(actor, obj):
            missing()
        return obj

    def objects(self, kind=None):
        with self.connect() as db:
            rows = (
                db.execute(
                    "SELECT id FROM objects WHERE kind=?", (kind,)
                ).fetchall()
                if kind
                else db.execute("SELECT id FROM objects").fetchall()
            )
        return [self.object(row["id"]) for row in rows]

    def replay(self, actor, operation, key, payload):
        actor_id = self.receipt_actor(actor)
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM receipts "
                "WHERE actor=? AND operation=? AND key=?",
                (actor_id, operation, key),
            ).fetchone()
        if row and row["fingerprint"] != fingerprint(payload):
            raise HTTPException(
                409, "Idempotency key already used for different input."
            )
        return row["object_id"] if row else None

    def reserved(self, object_id):
        with self.connect() as db:
            return (
                db.execute(
                    "SELECT 1 FROM receipts WHERE object_id=?", (object_id,)
                ).fetchone()
                is not None
            )

    def create_reader(self, actor, note_id, expires_in):
        if actor is None:
            raise HTTPException(403, "Use a narrow private read capability.")
        self.require(actor, "notes:read")
        self.require(actor, "assets:read")
        self.validate_chain(actor)
        self.get_allowed(actor, note_id, "note")
        token = secrets.token_urlsafe(32)
        expires = min(int(time.time()) + expires_in, actor["expiresAt"])
        with self.connect() as db:
            db.execute(
                "DELETE FROM reader_sessions WHERE expires_at<=?",
                (int(time.time()),),
            )
            db.execute(
                "INSERT INTO reader_sessions VALUES(?,?,?,?)",
                (
                    hashlib.sha256(token.encode()).hexdigest(),
                    actor["capabilityId"],
                    note_id,
                    expires,
                ),
            )
        return token, expires

    def reader(self, token, note_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM reader_sessions WHERE digest=?",
                (hashlib.sha256((token or "").encode()).hexdigest(),),
            ).fetchone()
        if (
            not row
            or row["note_id"] != note_id
            or row["expires_at"] <= time.time()
        ):
            raise HTTPException(401, "Reader session unavailable.")
        actor = self.capability(row["capability_id"])
        self.validate_chain(actor)
        self.get_allowed(actor, note_id, "note")
        return actor

    def remember(self, actor, operation, key, payload, object_id):
        with self.connect() as db:
            db.execute(
                "INSERT INTO receipts VALUES(?,?,?,?,?)",
                (
                    self.receipt_actor(actor),
                    operation,
                    key,
                    fingerprint(payload),
                    object_id,
                ),
            )

    @staticmethod
    def receipt_actor(actor):
        if actor and actor.get("jobId"):
            return canonical([actor["clientId"], actor["jobId"]])
        return actor["capabilityId"] if actor else "owner"
