# Security

## Reporting

Please report a suspected vulnerability through a private GitHub security
advisory for this repository. Do not open a public issue containing tokens,
credentials, private note content, host names or deployment details.

## Runtime boundaries

- The normal deployment is a controlled single-user service behind HTTPS.
- Caddy is the public edge. The application container has no direct public
  port.
- Library APIs require an authenticated session or a hashed, scoped API token
  unless the deployment deliberately selects `none` or `read_only` auth.
- The `/note-assets` route is intentionally readable without application
  authentication. Do not place private material there unless this exposure is
  acceptable.
- Windows update metadata and packages are readable without a Library session
  so an installed client can update before login.

Password sessions use an HttpOnly, Secure, SameSite-Strict cookie in the hosted
client. The Windows client uses a bearer session protected with Windows DPAPI.
Google OAuth secrets remain server-side; the native handoff uses the system
browser, loopback-only callback validation, signed state and PKCE.

## Local Windows data

DPAPI protects the persistent authentication token, not every local application
file. The WebView2 profile may contain:

- bounded cached Library notes and index metadata;
- unsaved drafts;
- recently opened local file paths;
- route, scroll and window state; and
- normal browser storage and logs.

Treat the Windows account and `%LOCALAPPDATA%\LamaNotes` as part of the trusted
local boundary. Logout clears the active session, but uninstall keeps WebView2
data unless removal of user data is requested explicitly.

## Update trust

Official Windows builds embed an Ed25519 update public key. Their update
manifests must be signed by the corresponding private key, which stays outside
this repository. The client also rejects non-HTTPS remote update origins,
cross-origin package URLs and cross-origin redirects, then verifies package
size and SHA-256 before replacement.

Development and legacy builds without an embedded update public key accept an
unsigned manifest for compatibility. Establish the signed trust boundary with
a manually verified installer before relying on in-app signed updates. Use the
release and rollback procedure in `docs/RELEASE.md`; do not copy a private
signing key into the source tree, build output or production runtime.

Rotating the Ed25519 key requires a manually verified installer or a separate
dual-key migration release. An ordinary manifest cannot replace the public key
trusted by an already installed client.

## Repository contents

Secrets, Library contents, local editor files and production configuration do
not belong in this repository.
