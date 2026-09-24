#!/usr/bin/env bash
# Inspect, verify, or restore CodeProve Postgres backups made by backup_db.sh.
#
#   scripts/restore_db.sh list                  # newest 20 backups in S3
#   scripts/restore_db.sh verify [KEY|latest]   # restore into a scratch DB, compare
#                                               # row counts, drop it (non-destructive)
#   scripts/restore_db.sh restore KEY|FILE      # REPLACE the live database
#
# KEY is a name shown by `list` (e.g. codeprove_20260924T190000Z.dump); FILE is a
# local pg_dump archive (e.g. the safety dump a previous restore left in $HOME).
# `restore` keeps a safety dump of the current database in $HOME, stops the
# backend, recreates the database, and restarts the backend only on success.
set -Eeuo pipefail

LOG_TAG=restore
# shellcheck source=scripts/lib_db_backup.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib_db_backup.sh"

BACKEND_CONTAINER="${BACKEND_CONTAINER:-codeprove_backend}"
SCRATCH_DB=""
BACKEND_STOPPED=0
RESTORE_OK=0
SAFETY_DUMP=""
WORK_DIR=""
KEY=""
ARCHIVE=""

cleanup() {
  if [[ -n "$SCRATCH_DB" ]]; then
    psql_in postgres "DROP DATABASE IF EXISTS \"$SCRATCH_DB\"" >/dev/null 2>&1 || true
  fi
  if [[ "$BACKEND_STOPPED" == 1 ]]; then
    if [[ "$RESTORE_OK" == 1 ]]; then
      log "starting $BACKEND_CONTAINER"
      docker start "$BACKEND_CONTAINER" >/dev/null || log "ERROR: could not start $BACKEND_CONTAINER" >&2
    else
      # Starting the backend on a half-restored database would let alembic
      # create an empty schema and hide the failure, so leave it stopped.
      log "ERROR: restore failed; $BACKEND_CONTAINER is left STOPPED on purpose." >&2
      log "roll back with: $0 restore $SAFETY_DUMP" >&2
    fi
  fi
  [[ -z "$WORK_DIR" ]] || rm -rf "$WORK_DIR"
}
trap cleanup EXIT
trap 'log "ERROR: failed at line $LINENO" >&2' ERR

usage() {
  sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-1}"
}

list_keys() {
  # Keys embed a UTC timestamp, so lexical order is chronological.
  aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" "${AWS_REGION_ARG[@]}" \
    | awk '{print $4}' | grep -E '\.dump$' | LC_ALL=C sort || true
}

# Functions that can `die` return results through globals (KEY, ARCHIVE), not
# stdout: calling them inside $(...) would run `die` in a subshell, where it
# can only end that subshell.

# resolve_key KEY|latest -> sets KEY (validated S3 object name).
resolve_key() {
  require_s3
  KEY="${1:-latest}"
  if [[ "$KEY" == "latest" ]]; then
    KEY="$(list_keys | tail -n 1)"
    [[ -n "$KEY" ]] || die "no backups found under s3://$S3_BUCKET/$S3_PREFIX/"
  fi
  [[ "$KEY" =~ ^[A-Za-z0-9._-]+\.dump$ ]] || die "invalid backup key: $KEY"
}

# fetch KEY -> sets ARCHIVE to a local copy in $WORK_DIR, checked against the
# sha256 recorded at upload.
fetch() {
  require_s3
  local key="$1" expected actual
  ARCHIVE="$WORK_DIR/$key"
  log "downloading $(s3_uri "$key")"
  aws s3 cp "$(s3_uri "$key")" "$ARCHIVE" "${AWS_REGION_ARG[@]}" --only-show-errors
  expected="$(aws s3api head-object "${AWS_REGION_ARG[@]}" --bucket "$S3_BUCKET" \
    --key "$S3_PREFIX/$key" --query 'Metadata.sha256' --output text)"
  actual="$(sha256_of "$ARCHIVE")"
  if [[ -n "$expected" && "$expected" != "None" ]]; then
    [[ "$expected" == "$actual" ]] || die "checksum mismatch for $key (expected $expected, got $actual)"
  else
    log "warning: $key has no sha256 metadata; skipping checksum check"
  fi
}

# source_archive KEY|FILE|latest -> sets ARCHIVE to a validated local archive.
source_archive() {
  if [[ -f "$1" ]]; then
    ARCHIVE="$1"
  else
    resolve_key "$1"
    fetch "$KEY"
  fi
  archive_is_valid "$ARCHIVE" || die "$1 is not a readable pg_dump archive"
}

restore_into() {
  # --no-owner/--no-privileges: the archive's roles may not exist on this server.
  docker exec -i "$DB_CONTAINER" pg_restore -U "$PG_USER" -d "$1" \
    --no-owner --no-privileges --exit-on-error <"$2"
}

cmd_verify() {
  source_archive "${1:-latest}"
  SCRATCH_DB="${PG_DB}_restore_check"

  log "restoring into scratch database $SCRATCH_DB"
  psql_in postgres "DROP DATABASE IF EXISTS \"$SCRATCH_DB\""
  psql_in postgres "CREATE DATABASE \"$SCRATCH_DB\""
  restore_into "$SCRATCH_DB" "$ARCHIVE"

  log "row counts (backup vs. live database):"
  LC_ALL=C join -t '|' -a 1 -a 2 -e '-' -o 0,1.2,2.2 \
    <(table_counts "$SCRATCH_DB" | LC_ALL=C sort) <(table_counts "$PG_DB" | LC_ALL=C sort) \
    | awk -F'|' 'BEGIN { printf "  %-24s %12s %12s\n", "table", "backup", "live" }
                 { printf "  %-24s %12s %12s\n", $1, $2, $3 }'
  log "verify OK: backup restores cleanly (scratch database is dropped on exit)"
}

cmd_restore() {
  local answer
  [[ -n "${1:-}" ]] || die "restore needs an explicit KEY or FILE (see: $0 list)"
  source_archive "$1"

  cat <<EOF

  This REPLACES database "$PG_DB" with: $1
  The backend ($BACKEND_CONTAINER) is stopped during the restore.
  A safety dump of the current database is written to \$HOME first.

EOF
  read -r -p "  Type the database name ($PG_DB) to continue: " answer
  [[ "$answer" == "$PG_DB" ]] || die "confirmation did not match; nothing was changed"

  SAFETY_DUMP="$HOME/${PG_DB}_pre_restore_$(date -u +%Y%m%dT%H%M%SZ).dump"
  log "writing safety dump to $SAFETY_DUMP"
  (umask 077 && docker exec "$DB_CONTAINER" pg_dump -U "$PG_USER" -d "$PG_DB" -Fc >"$SAFETY_DUMP")
  archive_is_valid "$SAFETY_DUMP" || die "safety dump is unreadable; aborting before any change"

  log "stopping $BACKEND_CONTAINER"
  docker stop "$BACKEND_CONTAINER" >/dev/null
  BACKEND_STOPPED=1

  log "recreating database $PG_DB"
  psql_in postgres "DROP DATABASE \"$PG_DB\" WITH (FORCE)"
  psql_in postgres "CREATE DATABASE \"$PG_DB\" OWNER \"$PG_USER\""
  restore_into "$PG_DB" "$ARCHIVE"
  RESTORE_OK=1

  log "restore OK: $PG_DB replaced from $1 (safety dump: $SAFETY_DUMP)"
}

main() {
  local cmd="${1:-}"
  [[ -n "$cmd" ]] || usage
  shift
  [[ "$cmd" == "-h" || "$cmd" == "--help" ]] && usage 0
  load_config
  require_cmds docker sha256sum join
  case "$cmd" in
    list)
      require_s3
      list_keys | tail -n 20
      ;;
    verify | restore)
      require_db_running
      WORK_DIR="$(mktemp -d)"
      chmod 700 "$WORK_DIR"
      "cmd_$cmd" "$@"
      ;;
    *) usage ;;
  esac
}

main "$@"
