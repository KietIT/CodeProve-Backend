#!/usr/bin/env bash
# Dump the CodeProve Postgres database and upload it to S3 (server-side
# encrypted). Meant to run daily from cron on the EC2 host; see docs/RUNBOOK.md.
#
#   scripts/backup_db.sh
#
# Config (.env or environment): BACKUP_S3_BUCKET (required), BACKUP_S3_PREFIX
# (default "postgres"), BACKUP_AWS_REGION, BACKUP_HEALTHCHECK_URL (optional
# dead-man's-switch ping, e.g. healthchecks.io), POSTGRES_USER, POSTGRES_DB,
# DB_CONTAINER (default codeprove_db).
#
# Exits non-zero on any failure, so cron mail / the healthcheck ping flags it.
# Retention is NOT handled here: an S3 lifecycle rule expires old dumps, so the
# EC2 role never needs delete rights on the backups.
set -Eeuo pipefail

LOG_TAG=backup
# shellcheck source=scripts/lib_db_backup.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib_db_backup.sh"

HEALTHCHECK_URL=""
WORK_DIR=""

ping_healthcheck() {
  # $1 = "" on success, "/fail" on failure. A failed ping must not mask the
  # backup's own result, so errors here are logged and ignored.
  [[ -n "$HEALTHCHECK_URL" ]] || return 0
  curl -fsS -m 10 --retry 3 -o /dev/null "${HEALTHCHECK_URL}$1" \
    || log "warning: healthcheck ping failed"
}

on_error() {
  local code=$?
  log "ERROR: backup failed (exit $code, line $1)" >&2
  ping_healthcheck /fail
  exit "$code"
}
trap 'on_error $LINENO' ERR
on_die() { ping_healthcheck /fail; }
cleanup() { [[ -z "$WORK_DIR" ]] || rm -rf "$WORK_DIR"; }
trap cleanup EXIT

main() {
  load_config
  require_s3
  HEALTHCHECK_URL="${BACKUP_HEALTHCHECK_URL:-$(env_get BACKUP_HEALTHCHECK_URL)}"
  require_cmds docker sha256sum
  [[ -z "$HEALTHCHECK_URL" ]] || require_cmds curl

  # Never let two runs (e.g. cron + a manual run) write at the same time.
  if command -v flock >/dev/null 2>&1; then
    exec 9>"${TMPDIR:-/tmp}/codeprove-db-backup.lock"
    flock -n 9 || die "another backup is already running"
  fi

  require_db_running

  local name file size sha
  WORK_DIR="$(mktemp -d)"
  chmod 700 "$WORK_DIR"

  name="${PG_DB}_$(date -u +%Y%m%dT%H%M%SZ).dump"
  file="$WORK_DIR/$name"

  log "dumping database $PG_DB from $DB_CONTAINER"
  # Custom format (-Fc) is compressed and lets pg_restore pick objects later.
  docker exec "$DB_CONTAINER" pg_dump -U "$PG_USER" -d "$PG_DB" -Fc >"$file"

  size="$(stat -c %s "$file" 2>/dev/null || wc -c <"$file")"
  [[ "$size" -gt 0 ]] || die "dump is empty"
  archive_is_valid "$file" || die "dump is not a readable pg_dump archive"
  sha="$(sha256_of "$file")"

  log "uploading $name ($size bytes) to $(s3_uri "$name")"
  aws s3 cp "$file" "$(s3_uri "$name")" "${AWS_REGION_ARG[@]}" \
    --sse AES256 --metadata "sha256=$sha" --only-show-errors

  # Read the object back so a silently truncated upload cannot pass as success.
  local remote_size
  remote_size="$(aws s3api head-object "${AWS_REGION_ARG[@]}" --bucket "$S3_BUCKET" \
    --key "$S3_PREFIX/$name" --query ContentLength --output text)"
  [[ "$remote_size" == "$size" ]] || die "uploaded size $remote_size != local size $size"

  log "backup OK: $(s3_uri "$name") ($size bytes, sha256 $sha)"
  ping_healthcheck ""
}

main "$@"
