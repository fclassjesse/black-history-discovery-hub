#!/usr/bin/env bash
# Loads the local demo data into the live database, then replaces every partner password with a new private one.
# Usage (from anywhere):  scripts/go_live_restore.sh "postgresql://...External Database URL from Render..."
set -euo pipefail

DB_URL="${1:-}"
if [[ -z "$DB_URL" ]]; then
  echo "Usage: scripts/go_live_restore.sh \"<External Database URL from Render>\"" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
PGB=".venv/lib/python3.12/site-packages/pgserver/pginstall/bin"
DUMP=".cache/bhdh-live.dump"

# 1. fresh copy of the local database (the embedded local Postgres must be running: `make db`)
echo "→ Copying local data…"
"$PGB/pg_dump" "postgresql://postgres@127.0.0.1:54329/bhdh" -Fc --no-owner --no-privileges \
  --exclude-table-data=search_log -f "$DUMP"

# 2. load it into the live database
echo "→ Loading into the live database (about a minute)…"
# hosted Postgres refuses a few ownership-only statements (e.g. COMMENT ON EXTENSION); those errors are harmless,
# so success is judged by the record count instead of pg_restore's exit code
"$PGB/pg_restore" --no-owner --no-privileges -d "$DB_URL" "$DUMP" 2> .cache/restore-errors.log || true
LOCAL=$("$PGB/psql" "postgresql://postgres@127.0.0.1:54329/bhdh" -Atc "select count(*) from records;")
COUNT=$("$PGB/psql" "$DB_URL" -Atc "select count(*) from records;" 2>/dev/null || echo 0)
echo "  records on the live site: $COUNT (local: $LOCAL)"
if [[ "$COUNT" != "$LOCAL" ]]; then
  echo "✗ The load did not finish. Errors are in backend/.cache/restore-errors.log — share that file with Claude." >&2
  exit 1
fi

# 3. the README publishes the demo passwords, so every live login gets a new private one
echo "→ Choose the partner password for the live site (at least 14 characters; it is not shown)."
HASH=$(uv run --no-sync python -c "
import getpass, sys
from app.security import hash_password
pw = getpass.getpass('New partner password: ')
if len(pw) < 14: sys.exit('Too short: use at least 14 characters.')
if getpass.getpass('Type it again: ') != pw: sys.exit('The two passwords differ.')
print(hash_password(pw))")
UPDATED=$("$PGB/psql" "$DB_URL" -Atqc "update users set password_hash = '$HASH' returning 1;" | wc -l | tr -d ' ')
echo "  partner logins updated: $UPDATED"
echo "✓ Done. Open your bhdh-web address and sign in with the new password."
