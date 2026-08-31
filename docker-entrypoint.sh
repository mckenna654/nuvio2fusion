#!/bin/sh
set -eu

# Docker/Unraid can create a new bind mount owned by root. Prepare only this
# service's data directory, then run the application without root privileges.
if [ "$(id -u)" = 0 ]; then
    mkdir -p "$NUVIO2FUSION_DATA_DIR"
    chown nuvio2fusion:nuvio2fusion "$NUVIO2FUSION_DATA_DIR"
    chmod 700 "$NUVIO2FUSION_DATA_DIR"
    for file in "$NUVIO2FUSION_DATA_DIR"/bridge.sqlite3*; do
        if [ -f "$file" ] && [ ! -L "$file" ]; then
            chown nuvio2fusion:nuvio2fusion "$file"
            chmod 600 "$file"
        fi
    done
    exec gosu nuvio2fusion "$@"
fi
exec "$@"
