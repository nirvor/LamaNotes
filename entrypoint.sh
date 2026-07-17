#!/bin/sh

[ "$EXEC_TOOL" ] || EXEC_TOOL=gosu
[ "$FLATNOTES_HOST" ] || FLATNOTES_HOST=0.0.0.0
[ "$FLATNOTES_PORT" ] || FLATNOTES_PORT=8080

set -e

echo "\
======================================
======== Welcome to NirvNotes ========
======================================

HTML-first, flat-folder notes for a
clean personal knowledge workflow.

──────────────────────────────────────
"

nirvnotes_command="python -m \
                  uvicorn \
                  main:app \
                  --app-dir server \
                  --host ${FLATNOTES_HOST} \
                  --port ${FLATNOTES_PORT} \
                  --proxy-headers \
                  --forwarded-allow-ips '*'"

if [ `id -u` -eq 0 ] && [ `id -g` -eq 0 ]; then
    echo Setting file permissions...
    chown -R ${PUID}:${PGID} ${FLATNOTES_PATH}

    echo Starting NirvNotes as user ${PUID}...
    exec ${EXEC_TOOL} ${PUID}:${PGID} ${nirvnotes_command}

else
    echo "A user was set by docker, skipping file permission changes."
    echo Starting NirvNotes as user $(id -u)...
    exec ${nirvnotes_command}
fi
