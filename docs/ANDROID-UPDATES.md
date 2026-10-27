# Private Android updates

The existing client-update directory also holds `LamaDroid-update.json` and
the APK it references. `/api/android-client-update` serves the signed envelope.
`/api/android-client-update/download` serves only its verified package. Both
are served through the existing private Tailscale Notes origin on port 8092.
The public Notes hostname returns 404 for these routes. They expose no Notes
data or account credentials and need no extra native account.

The same router has a fixed second product mapping for the standalone
`org.thuber.lamashare` package. `/api/android-share-client-update` serves
`LamaShare-update.json`, and `/api/android-share-client-update/download` serves
its verified `LamaShare-<version>.apk` (initial release `LamaShare-0.1.0.apk`).
These routes use the same private port8092 boundary and return404 on
`notes.thuber.org`. The manifest must match its own package identity, APK
prefix/version, hash/size and fixed relative download path. It cannot select
the other app, an arbitrary file or an external download URL. Payloads are
returned unchanged for the native signature check. No new server credential
or signing authority is introduced.

Metadata is signed with LamaDroid's existing release key. The Android client
pins its public key, verifies the signed payload and package hash, then checks
package identity, a higher version code and the installed APK signer before
opening Android's installer. Installation remains a user action.
LamaShare uses that same signer trust through its shared native foundation,
with its own package identity and feed path. Publishing either feed does not
replace the other feed or the Windows update manifest.

Publish the immutable APK first and atomically replace the envelope last.
Retain its predecessor. Android and Windows metadata are separate files, so a
Windows update publication does not replace Android metadata. Never publish a
fixture APK. The first update from pre-updater versions still needs the direct
download link. Later versions use Settings -> App updates.
