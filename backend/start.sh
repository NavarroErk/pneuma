#!/bin/sh

PUID=${PUID:-1000}
PGID=${PGID:-1000}

# set data folders perms to PUID:PGID if not already done
for dir in /app/uploads /app/logs /app/db; do
    mkdir -p "$dir"
    if [ "$(stat -c %u:%g "$dir")" != "$PUID:$PGID" ]; then
        echo "Setting owner of $dir to $PUID:$PGID"
        chown -R "$PUID:$PGID" "$dir"
    fi
done

export HOME=/tmp

# drop root and start the app as PUID:PGID
exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups uv run --no-sync fastapi run --host 0.0.0.0 --port 6650