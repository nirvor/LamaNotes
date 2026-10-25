"""Renew only the owner's explicitly bound, read-only Quicknotes service lease."""
import json
import re
import time

from .store import canonical

LEASE_SECONDS = 30 * 24 * 60 * 60
RENEW_AFTER = 29 * 24 * 60 * 60


def refresh_focus_source(store):
    binding_path = store.root / "focus-quicknotes.json"
    try:
        if binding_path.is_symlink() or binding_path.stat().st_size > 4096:
            return {"connected": False}
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
        note_id, capability_id = binding["noteId"], binding["capabilityId"]
        if not re.fullmatch(r"ln-[a-f0-9]{32}", note_id) or not re.fullmatch(r"lg-[a-f0-9]{32}", capability_id):
            return {"connected": False}
    except (OSError, ValueError, KeyError, TypeError):
        return {"connected": False}

    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        capability = store.capability(capability_id, db)
        obj = db.execute("SELECT kind,active FROM objects WHERE id=?", (note_id,)).fetchone()
        if (not capability or capability["revoked"] or not obj or obj["kind"] != "note" or not obj["active"]
                or capability.get("clientId") != "focus-quicknotes" or capability.get("ownerId") != store.owner_id
                or capability.get("parentId") is not None or capability.get("jobId") is not None
                or capability.get("scopes") != ["notes:read"] or capability.get("noteIds") != [note_id]
                or capability.get("captureIds")):
            return {"connected": False}
        now = int(time.time())
        expires = capability["expiresAt"]
        renewed = expires < now + RENEW_AFTER
        if renewed:
            expires = now + LEASE_SECONDS
            payload = {key: value for key, value in capability.items() if key != "revoked"}
            payload["expiresAt"] = expires
            db.execute("UPDATE capabilities SET payload=? WHERE id=? AND revoked=0", (canonical(payload), capability_id))
        return {"connected": True, "noteId": note_id, "expiresAt": expires, "renewed": renewed}
