# Quicknotes as a Focus source

The connection uses one explicitly enrolled HTML note with a stable Notes ID.
The flat Library stays authoritative. No Notes are copied into Focus, and no
tag or pin grants reading access. The shopping list, Shared collection and
Research Notes do not become sources through this connection.

## Owner setup

1. Back up Notes before adding the stable ID or changing integration metadata.
2. Enroll the selected Quicknotes HTML through the existing owner-only
   `/api/private/v1/grants/notes` operation and its current expectedVersion.
   Keep the returned stable noteId. Enrollment preserves the note and its tags.
3. Create one root capability with clientId `focus-quicknotes`, scopes exactly
   `["notes:read"]`, noteIds exactly `[selectedNoteId]`, no captures/job/parent
   and expiresIn 2592000. Do not reuse a Research or broad owner credential.
4. Store `{noteId, capabilityId}` at
   `/srv/lamanotes/data/.private/focus-quicknotes.json`, owner 1000:1000, mode 600.
5. Store `{noteId, token}` at
   `/srv/nirvstart/data/.focus-quicknotes.json`, owner 10001:10001, mode 600. The
   token is the one-time capability secret. Keep it out of logs, Slack,
   repositories, URLs and the Dot workspace. Use an atomic protected file write.

Focus uses its configured internal Notes API base and matching personal owner
identity. Its authenticated GET `/api/focus/v1/hiwi/notes/quicknotes` accepts
no note selection and fetches only this ID. It returns fresh plain text,
noteId, version, canonical link and readAt. No index/search/write or credential
operation is exposed. The existing Focus helper can read that relative route
with the Dot's already installed Focus token. No new VM token or schedule is
needed.

## Ordinary use and expiry

After a successful home index load, Notes calls the owner-only fixed-binding
refresh. Requests are coalesced and throttled in the client. A missing/offline
connection does not add a toast or delay the home page. The server validates
the dedicated lease and active enrollment in one transaction, renews only when
fewer than 29 days remain and never extends past a fresh 30-day lease. It keeps
the same token and selection. An expired unrevoked lease can recover on the
owner's next use. This is finite access, not an indefinite background grant.

The existing weekday Focus routine can review the fresh response. It reports
Notes checked only after content review and records unavailable access
honestly. It keeps the existing proposal-only behaviour and excludes consulting
or professional project material. One useful source link can accompany a
proposal. A fetch alone does not mark the morning preparation complete.

## Revocation and acceptance

The existing owner capability revoke or note-enrollment revoke disables the
source. Ordinary Notes use cannot revive either. Removing the Focus source
configuration also disables proxy access. Renewing any other service grants
no access to this note.

Verify the exact note read with the dedicated token, a 404 for another enrolled
private note, anonymous proxy 401, current version after a note edit, no source
token in the Focus response, no Notes write route and unavailability after
revocation. Verify the Dot's actual content review through its existing task.
Metadata configuration and a successful API read alone are not Dot acceptance.
