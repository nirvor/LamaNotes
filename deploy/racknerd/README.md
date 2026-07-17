# RackNerd deployment

The production deployment keeps two routes to the same private app container:

- `https://notes.thuber.org` is the normal HTTPS route for Windows and Android.
- The Tailnet endpoint on port `8092` remains available for administration and rollback.

Only Caddy publishes ports. The LamaNotes container stays on the Compose network
and reads its secrets from `/srv/flatnotes/.env`. Passwords use an Argon2id hash;
automation uses hashed, scoped API tokens. Raw credentials are never stored in
this repository.

The public ports bind to the RackNerd IPv4 address explicitly because Tailscale
owns port 443 on the Tailnet address. Caddy stores public certificates in named
volumes and reads the existing Tailnet certificate from `/data/certs`.

## Rollout

1. Build and smoke-test the exact Git commit as a tagged local Docker image.
2. Back up `.env`, Compose, Caddy, and `data` under `/srv/backups`.
3. Validate `docker compose config` and `caddy validate` with staged files.
4. Recreate the app, verify the Tailnet route, then recreate Caddy.
5. Verify public TLS, password login, cookie attributes, API-token access, note
   count, and the Tailnet fallback.

## Rollback

Restore the timestamped `docker-compose.yml`, `docker-compose.override.yml`,
`Caddyfile`, and `.env` backups in `/srv/flatnotes`, then run:

```sh
docker compose config --quiet
docker compose up -d --force-recreate flatnotes caddy
```

The previous image remains local during the canary period. DNS can be removed
independently without affecting the Tailnet route.
