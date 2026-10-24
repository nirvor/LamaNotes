# LamaDroid updates

The existing client-update directory also holds `LamaDroid-update.json` and
the APK it references. `/api/android-client-update` serves the signed envelope.
`/api/android-client-update/download` serves only its verified package. Both
are public download routes and expose no Notes data or account credentials.

Metadata is signed with LamaDroid's existing release key. The Android client
pins its public key, verifies the signed payload and package hash, then checks
package identity, a higher version code and the installed APK signer before
opening Android's installer. Installation remains a user action.

Publish the immutable APK first and atomically replace the envelope last.
Retain its predecessor. Android and Windows metadata are separate files, so a
Windows update publication does not replace Android metadata. Never publish a
fixture APK. The first update from pre-updater versions still needs the direct
download link. Later versions use Settings -> App updates.
