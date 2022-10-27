#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

Usage () { cat >&2 <<EOF
Usage: $0 name:oldid:newid [...]
Migrate UID/GID
Where:
  name    name of the user/group
  oldid   old uid/gid
  newid   new uid/gid
Options:
  -q      do not show progress
EOF
}

UsageExit () { Usage ; exit 1 ; }


migrate_cmd=( ./migrate_uid_gid.bash )
while [ $# -gt 0 ]
do
  case "$1" in
    --) shift ; break ;;
    -q) migrate_cmd+=( -q ) ; shift ; break ;;
    -*) UsageExit ;;
    *) break ;;
  esac
done
[ $# -ge 1 ] || UsageExit

mkdir -pv logs

lgs=()
for db in group passwd
do
  lg=logs/$(hostname -s).$db.$(date +%s.%F).log
  "${migrate_cmd[@]}" $db "$@" > "$lg"
  lgs+=( "$lg" )
done
wc -l "${lgs[@]}"
