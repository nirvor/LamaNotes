# RackNerd deployment

The files in this directory define the LamaNotes target layout. Migrating an
existing installation to these service, container and asset-path names is a
separate backed-up operation. Do not mix that infrastructure rename with a
normal application release.

The production deployment keeps two routes to the same private app container:

- `https://notes.thuber.org` is the normal HTTPS route for Windows and Android.
- The Tailnet endpoint on port `8092` remains available for administration and rollback.

Only Caddy publishes ports. The LamaNotes container stays on the Compose
network and reads its secrets from the private runtime environment file.
Interactive login can use the single-user Google OAuth path, with the password
path kept temporarily for rollback. Passwords use an Argon2id hash; automation
uses hashed, scoped API tokens. Raw credentials are never stored in this
repository.

The Google OAuth client remains server-side. The Windows app opens the system
browser and uses a PKCE-bound loopback handoff; the client secret must never be
copied into the Windows package. Required environment names and the staged
cutover are documented in
`C:\Users\thoma\Desktop\work\VPS-Config\GOOGLE-AUTH-CUTOVER.md`.
Use the exact email only for the controlled bootstrap login, then bind the
observed Google account identifier through `NIRVNOTES_GOOGLE_ALLOWED_SUB`.

The public ports bind to the RackNerd IPv4 address explicitly because Tailscale
owns port 443 on the Tailnet address. Caddy stores public certificates in named
volumes and reads the existing Tailnet certificate from `/data/certs`.

## Rollout

1. Build and smoke-test the exact Git commit as a tagged local Docker image.
   Set `LAMANOTES_IMAGE` to that immutable tag for Compose.
2. Back up `.env`, Compose, Caddy, and `data` under `/srv/backups`.
3. Validate `docker compose config` and `caddy validate` with staged files.
4. Recreate the app, verify the Tailnet route, then recreate Caddy.
5. Verify public TLS, Google login, the temporary password fallback, cookie
   attributes, API-token access, note count, and the Tailnet fallback.
6. Verify one complete login/logout/login cycle in the installed Win11 app.
   Confirm that Google opens in the system browser and that the DPAPI-protected
   NirvNotes session survives an app restart.

## Rollback

Restore the timestamped `docker-compose.yml`, `docker-compose.override.yml`,
`Caddyfile`, and environment backups in the production runtime directory, then
run:

```sh
docker compose config --quiet
docker compose up -d --force-recreate
```

The previous image remains local during the canary period. DNS can be removed
independently without affecting the Tailnet route.
