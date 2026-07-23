# LamaNotes release and rollback

This runbook defines the repository-side release contract. Host names, account
identifiers, credentials and the actual transport to production remain in the
private operations repository.

An application release must not be combined with a service rename, path
migration or authentication cutover. Do these as separate, backed-up changes.

## 1. Freeze the source

Run all repository commands from the LamaNotes repository root in PowerShell:

```powershell
$ErrorActionPreference = "Stop"

git status --short --branch
$commit = git rev-parse HEAD
$shortCommit = git rev-parse --short=12 HEAD
$dirty = git status --porcelain
if ($dirty) {
  throw "Release requires a clean worktree."
}
```

Record `$commit` in the release note. Do not build one commit and deploy
another.

## 2. Validate the exact commit

Install locked dependencies and run every automated layer:

```powershell
npm ci
npm test
npm run build

python -m pip install pipenv
pipenv sync --dev
$updateSigningKey = $env:LAMANOTES_UPDATE_SIGNING_KEY
if (-not $updateSigningKey) {
  throw "The Ed25519 update signing key path is missing."
}
$updatePublicKey = (
  pipenv run python `
    .\windows-client\installer\sign-update-manifest.py `
    public-key `
    --private-key $updateSigningKey
).Trim()
$env:PYTHONPATH = "server"
pipenv run python -m unittest discover -s server -p "test_*.py"
pipenv run flake8 server --ignore=E203,E501,W503
Remove-Item Env:PYTHONPATH

python -m compileall -q server windows-client

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\windows-client\build.ps1 `
  -Version $shortCommit `
  -Commit $commit `
  -UpdateSigningPublicKey $updatePublicKey

& .\windows-client\.venv\Scripts\python.exe `
  -m unittest discover -s windows-client -p "test_*.py"
```

Also run the PowerShell updater and migration checks on Win11:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\windows-client\test-apply-update.ps1

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\windows-client\test-legacy-migration.ps1
```

Changes affecting layout need a normal desktop window and a narrow-window
check. Changes affecting authentication need one full login, logout and login
cycle in an installed client.

STOP if any command fails. Do not publish a partial release.

## 3. Sign and package the Windows client

Official Windows releases should use Authenticode. Keep the certificate and its
private key outside this repository. With the certificate thumbprint and
timestamp service supplied through the release environment:

```powershell
if (-not $env:LAMANOTES_SIGNING_CERT_SHA1) {
  throw "The signing certificate thumbprint is missing."
}
if (-not $env:LAMANOTES_TIMESTAMP_URL) {
  throw "The timestamp service URL is missing."
}
if (-not $env:LAMANOTES_UPDATE_SIGNING_KEY) {
  throw "The Ed25519 update signing key path is missing."
}

$clientExe = ".\windows-client\dist\LamaNotes\LamaNotes.exe"
signtool sign `
  /sha1 $env:LAMANOTES_SIGNING_CERT_SHA1 `
  /fd SHA256 `
  /tr $env:LAMANOTES_TIMESTAMP_URL `
  /td SHA256 `
  $clientExe
signtool verify /pa /v $clientExe

powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\windows-client\installer\build-installer.ps1 `
  -Version $shortCommit `
  -SkipAppBuild `
  -UpdateSigningKeyPath $env:LAMANOTES_UPDATE_SIGNING_KEY
```

The packaging script writes the ZIP and `LamaNotes-update.json` under
`windows-client\installer\artifacts`.

For the first release that embeds an update-signing public key, install the
verified Authenticode-signed build manually. Do not bootstrap this trust change
through an unsigned in-app update. The same rule applies to a later key
rotation unless a separately reviewed dual-key migration is implemented.

Verify that the manifest describes the actual ZIP:

```powershell
$artifactRoot = ".\windows-client\installer\artifacts"
$manifestPath = Join-Path $artifactRoot "LamaNotes-update.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$packagePath = Join-Path $artifactRoot $manifest.file
$package = Get-Item -LiteralPath $packagePath
$packageHash = (
  Get-FileHash -LiteralPath $packagePath -Algorithm SHA256
).Hash.ToLowerInvariant()

if ($manifest.commit -ne $commit) {
  throw "Manifest commit does not match the frozen source."
}
if ([int64]$manifest.size -ne $package.Length) {
  throw "Manifest size does not match the Windows package."
}
if ($manifest.sha256.ToLowerInvariant() -ne $packageHash) {
  throw "Manifest hash does not match the Windows package."
}
```

STOP if signing or artifact verification fails.

## 4. Build the immutable server image

Build and inspect an image tagged with the same short commit:

```powershell
$image = "lamanotes:$shortCommit"
docker build --pull `
  --label "org.opencontainers.image.revision=$commit" `
  --tag $image `
  .
docker image inspect $image
```

Use the private operations workflow to transfer this exact image and the
verified Windows artifacts. Do not rebuild on the server.

## 5. Back up the runtime

The following shell commands run in the private production runtime directory.
They intentionally use variables instead of repository-owned host values:

```sh
set -eu

: "${LAMANOTES_RUNTIME_DIR:?set the production runtime directory}"
: "${LAMANOTES_BACKUP_ROOT:?set the backup root}"

cd "$LAMANOTES_RUNTIME_DIR"
release_id="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$LAMANOTES_BACKUP_ROOT/$release_id"
install -d -m 0700 "$backup_dir"

cp -a .env docker-compose.yml docker-compose.override.yml Caddyfile "$backup_dir/"
tar -C "$LAMANOTES_RUNTIME_DIR" -czf "$backup_dir/data.tar.gz" data
if [ -d client-updates ]; then
  tar -C "$LAMANOTES_RUNTIME_DIR" \
    -czf "$backup_dir/client-updates.tar.gz" client-updates
fi

printf '%s\n' "$backup_dir"
```

Keep the printed backup path with the release record. STOP if any backup
command fails.

## 6. Validate and deploy the app

Set the immutable image in the private runtime environment, then validate the
effective Compose configuration:

```sh
set -eu

: "${LAMANOTES_RUNTIME_DIR:?set the production runtime directory}"
: "${LAMANOTES_IMAGE:?set the immutable image tag}"

cd "$LAMANOTES_RUNTIME_DIR"
docker image inspect "$LAMANOTES_IMAGE" >/dev/null
docker compose config --quiet
docker compose run --rm --no-deps caddy \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker compose up -d --force-recreate lamanotes
docker inspect \
  --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
  lamanotes
```

Wait for `healthy`. Then verify both configured routes and compare the
authenticated Library count with the pre-release count:

```sh
set -eu

: "${LAMANOTES_PUBLIC_ORIGIN:?set the public HTTPS origin}"
: "${LAMANOTES_TAILNET_ORIGIN:?set the administrative HTTPS origin}"
: "${LAMANOTES_RELEASE_READ_TOKEN:?set a temporary scoped read token}"
: "${LAMANOTES_EXPECTED_NOTE_COUNT:?set the pre-release note count}"

curl --fail --silent --show-error "$LAMANOTES_TAILNET_ORIGIN/health"
curl --fail --silent --show-error "$LAMANOTES_PUBLIC_ORIGIN/health"

actual_note_count="$(
  curl --fail --silent --show-error \
    -H "Authorization: Bearer $LAMANOTES_RELEASE_READ_TOKEN" \
    "$LAMANOTES_PUBLIC_ORIGIN/api/index" |
    python3 -c 'import json, sys; print(len(json.load(sys.stdin)))'
)"
test "$actual_note_count" = "$LAMANOTES_EXPECTED_NOTE_COUNT"
```

Do not print or store the token in the release note. If the app or either route
is unhealthy, rollback before publishing the Windows manifest.

Recreate Caddy only when its configuration or image actually changed. Validate
the staged Caddy configuration before doing so.

## 7. Publish the Windows update

Copy the verified ZIP first. Make it visible atomically, verify its server-side
hash and size, and only then replace the manifest:

```sh
set -eu

: "${LAMANOTES_RUNTIME_DIR:?set the production runtime directory}"
: "${LAMANOTES_RELEASE_DIR:?set the directory containing transferred artifacts}"

cd "$LAMANOTES_RUNTIME_DIR"
manifest_source="$LAMANOTES_RELEASE_DIR/LamaNotes-update.json"
package_name="$(
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8-sig"))["file"])' \
    "$manifest_source"
)"
expected_hash="$(
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8-sig"))["sha256"])' \
    "$manifest_source"
)"
expected_size="$(
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8-sig"))["size"])' \
    "$manifest_source"
)"

install -d -m 0755 client-updates
install -m 0644 \
  "$LAMANOTES_RELEASE_DIR/$package_name" \
  "client-updates/$package_name.pending"
test "$(stat -c %s "client-updates/$package_name.pending")" = "$expected_size"
test "$(sha256sum "client-updates/$package_name.pending" | awk '{print $1}')" = "$expected_hash"
mv -f "client-updates/$package_name.pending" "client-updates/$package_name"

install -m 0644 "$manifest_source" "client-updates/LamaNotes-update.json.pending"
mv -f \
  "client-updates/LamaNotes-update.json.pending" \
  "client-updates/LamaNotes-update.json"
```

After publication, verify the manifest response, package download, reported
size and SHA-256 from a separate client. Then complete one update in the
installed Win11 application and confirm restart, authentication and local-file
editing.

## 8. Rollback

For an application-only rollback, restore the previous runtime configuration
from the named backup and recreate the services:

```sh
set -eu

: "${LAMANOTES_RUNTIME_DIR:?set the production runtime directory}"
: "${LAMANOTES_ROLLBACK_DIR:?set the verified backup directory}"

cd "$LAMANOTES_RUNTIME_DIR"
cp -a "$LAMANOTES_ROLLBACK_DIR/.env" .
cp -a "$LAMANOTES_ROLLBACK_DIR/docker-compose.yml" .
cp -a "$LAMANOTES_ROLLBACK_DIR/docker-compose.override.yml" .
cp -a "$LAMANOTES_ROLLBACK_DIR/Caddyfile" .
docker compose config --quiet
docker compose up -d --force-recreate
```

Restore `data.tar.gz` only when application rollback is not sufficient and
after an explicit decision that newer Library changes may be discarded.

For Windows rollback, restore the previous package first and its previous
manifest last, using the same atomic publication order as above. Keep the
failed package for diagnosis but do not leave its manifest active.

Finally repeat health, Library-count, login and installed-client checks.
