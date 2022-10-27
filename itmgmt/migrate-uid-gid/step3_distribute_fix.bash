#!/usr/bin/bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail

if [ $# -lt 1 ]
then
  echo >&2 "Usage: $0 hostname [...]"
  exit 1
fi

here=$(cd -- "$(dirname -- "$BASH_SOURCE")" && /bin/pwd)

for h in "$@"
do
  ssh -ologlevel=error -nT "$h" mkdir -pv "$here/data"
  for s in migrate_uid_gid.bash wrapper_migrate.bash
  do
    rsync -ai {,"$h":}"$here/$s"
  done
  for d in passwd group
  do
    rsync -ai {,"$h":}"$here/data/$h.$d.migrate"
  done
done
