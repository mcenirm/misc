#!/usr/bin/bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail

if [ $# -lt 1 ]
then
  echo >&2 "Usage: $0 hostname [...]"
  exit 1
fi

for d in passwd group
do
  os=()
  for h in "$@"
  do
    o=data/$h.$d
    ssh -ologlevel=error -nT "$h" getent "$d" | sort > "$o"
    os+=( "$o" )
  done
  wc -l "${os[@]}"
  o=data/$d
  cut -d: -f1 "${os[@]}" \
  | sort -u \
  | tr \\n \\0 \
  | xargs -0 -r getent "$d" -s sss \
  > "$o" || :
  wc -l "$o"
done
