# Shared helpers for backup_db.sh / restore_db.sh. Source it, don't run it.
# Config is read from <repo>/.env (parsed, never sourced/executed); any value
# already set in the environment wins, so cron or a shell can override it.

# Bash drops `set -e` inside $(...) by default, so a failure there would let the
# script carry on with an empty value. Make command substitutions fail fast too.
shopt -s inherit_errexit

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_DIR/.env}"

log() { printf '%s [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${LOG_TAG:-db}" "$*"; }
# die runs the caller's optional on_die hook (e.g. a failure ping) before exiting;
# `exit` does not fire an ERR trap, so the hook is the only way to observe it.
die() {
  log "ERROR: $*" >&2
  if declare -F on_die >/dev/null; then on_die || true; fi
  exit 1
}

# env_get KEY -> last KEY=value in .env, surrounding quotes stripped ("" if absent).
env_get() {
  [[ -f "$ENV_FILE" ]] || return 0
  local line
  line="$(grep -E "^$1=" "$ENV_FILE" | tail -n 1 || true)"
  line="${line#*=}"
  line="${line%\"}"; line="${line#\"}"
  line="${line%\'}"; line="${line#\'}"
  printf '%s' "$line"
}

load_config() {
  DB_CONTAINER="${DB_CONTAINER:-codeprove_db}"
  PG_USER="${POSTGRES_USER:-$(env_get POSTGRES_USER)}"; PG_USER="${PG_USER:-codeprove}"
  PG_DB="${POSTGRES_DB:-$(env_get POSTGRES_DB)}"; PG_DB="${PG_DB:-codeprove}"
  S3_BUCKET="${BACKUP_S3_BUCKET:-$(env_get BACKUP_S3_BUCKET)}"
  S3_PREFIX="${BACKUP_S3_PREFIX:-$(env_get BACKUP_S3_PREFIX)}"; S3_PREFIX="${S3_PREFIX:-postgres}"
  S3_PREFIX="${S3_PREFIX%/}"
  AWS_REGION_ARG=()
  local region="${BACKUP_AWS_REGION:-$(env_get BACKUP_AWS_REGION)}"
  [[ -n "$region" ]] && AWS_REGION_ARG=(--region "$region")
  [[ -n "$S3_BUCKET" ]] || die "BACKUP_S3_BUCKET is not set (in .env or the environment)"
  return 0
}

require_cmds() {
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || die "required command not found: $c"
  done
}

require_db_running() {
  local running
  running="$(docker inspect -f '{{.State.Running}}' "$DB_CONTAINER" 2>/dev/null || true)"
  [[ "$running" == "true" ]] || die "container $DB_CONTAINER is not running"
}

# psql_in DB SQL -> run SQL inside the db container (unix socket, no password).
# No -i: the SQL comes from -c, and an attached stdin could swallow the script's.
psql_in() {
  docker exec -e PGOPTIONS='-c client_min_messages=warning' "$DB_CONTAINER" psql -U "$PG_USER" -d "$1" -v ON_ERROR_STOP=1 -X -q -At -c "$2"
}

# table_counts DB -> "table|rows" for every table in the public schema.
table_counts() {
  psql_in "$1" "SELECT table_name || '|' || (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM public.%I', table_name), false, true, '')))[1]::text FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
}

# archive_is_valid FILE -> pg_restore can read the archive's table of contents.
archive_is_valid() {
  docker exec -i "$DB_CONTAINER" pg_restore --list >/dev/null <"$1"
}

sha256_of() { sha256sum "$1" | awk '{print $1}'; }

s3_uri() { printf 's3://%s/%s/%s' "$S3_BUCKET" "$S3_PREFIX" "$1"; }
