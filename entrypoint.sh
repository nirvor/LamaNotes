#!/bin/sh

[ "$EXEC_TOOL" ] || EXEC_TOOL=gosu
LAMANOTES_HOST=${LAMANOTES_HOST:-${FLATNOTES_HOST:-0.0.0.0}}
LAMANOTES_PORT=${LAMANOTES_PORT:-${FLATNOTES_PORT:-8080}}
LAMANOTES_PATH=${LAMANOTES_PATH:-${FLATNOTES_PATH:-/data}}

set -e

echo "\
======================================
========= Welcome to LamaNotes =======
======================================

Fast local editing with an explicit,
private HTML note library.
"

lamanotes_command="python -m \
                  uvicorn \
                  main:app \
                  --app-dir server \
                  --host ${LAMANOTES_HOST} \
                  --port ${LAMANOTES_PORT} \
                  --proxy-headers \
                  --forwarded-allow-ips '*'"

if [ `id -u` -eq 0 ] && [ `id -g` -eq 0 ]; then
    echo Setting file permissions...
    chown -R ${PUID}:${PGID} ${LAMANOTES_PATH}

    echo Starting LamaNotes as user ${PUID}...
    exec ${EXEC_TOOL} ${PUID}:${PGID} ${lamanotes_command}

else
    echo "A user was set by docker, skipping file permission changes."
    echo Starting LamaNotes as user $(id -u)...
    exec ${lamanotes_command}
fi
