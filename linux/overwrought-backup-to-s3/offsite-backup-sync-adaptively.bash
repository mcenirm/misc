#!/bin/bash
set -e
set -u
shopt -s dotglob nullglob

# The top of the folder tree to sync
BASE=/archive

# The timeout for each path
TIMEOUT=9h

# The actual command to run for each path
SYNCER=$(dirname -- "$BASH_SOURCE")/offsite-backup-sync-to-s3.bash


Usage () { cat >&2 <<EOF
Usage: $0 [OPTIONS]
Sync folder tree to S3, adapting if timeouts happened last time
Options:
  --base=...     absolute path to top folder to sync [$BASE]
  --timeout=...  argument to timeout command [$TIMEOUT]
  --syncer=...   actual sync command to run [$SYNCER]
EOF
}
while [ $# -gt 0 ]
do
  case "$1" in
    --help|-h|-\?) Usage ; exit ;;
    --base=*) BASE=${1#--base=} ;;
    --timeout=*) TIMEOUT=${1#--timeout=} ;;
    --syncer=*) SYNCER=${1#--syncer=} ;;
    -*) Usage ; exit 1 ;;
    *) Usage ; exit 1 ;;
  esac
  shift
done


# Parent-paths management functions
MARKER=yes
declare -A parents=( [.]="$MARKER" )
reduce_path () {
  printf '%s\n' "$1"
  [ . = "$1" ] || reduce_path "$(dirname "$1")"
}
parents_add () {
  local -a lineage
  local p

  mapfile -t lineage < <(reduce_path "$1")
  for p in "${lineage[@]}"
  do
    parents[$p]="$MARKER"
  done
}


# Prepare log location
name=$(basename -- "$0" .bash)
logdir=$(mktemp --tmpdir -d tmp."$name".XXXXXXXXXX)
chmod a+rx "$logdir"

# Check for log from previous run
prevlogdir=$(
    (
        echo $'0\tNONE'
        find "${logdir%.*}"* \
            -maxdepth 0 \
            -user "$EUID" \
            -printf '%T@\t%p\n'
    ) \
    | sort -n \
    | grep -F -B1 -e "$logdir" \
    | head -n1 \
    | cut -f2
)

# Check previous run
if [ NONE != "$prevlogdir" ]
then
  mapfile -t prevlogs < <( find "$prevlogdir" -type f -name '*.log' -printf '%P\n' )
  if [ "${#prevlogs[@]}" -gt 0 ]
  then
    for prevlog in "${prevlogs[@]}"
    do
      prevpath=${prevlog%.log}
      if grep -q '^rv=124$' "$prevlogdir/$prevlog"
      then
        # There was a timeout last time, so treat this path as a parent
        # (more jobs)
        parents_add "$prevpath"
      elif grep -q '^rv=' "$prevlogdir/$prevlog"
      then
        # There was a non-timeout problem last time, so add parent
        # (same number of jobs)
        parents_add "$(dirname "$prevpath")"
      else
        # There was no problem last time, so add grandparent
        # (fewer jobs)
        parents_add "$(dirname -- "$(dirname -- "$prevpath")")"
      fi
    done
  fi
fi

# Keep everything relative
cd -- "$BASE"

# Main loop
for parent in "${!parents[@]}"
do

  for child in "$parent"/*
  do
    child=${child#./}
    # Only process child if not in the list of parents
    if [ "${parents[$child]-no}" = no ]
    then
      log=$logdir/${child}.log
      mkdir -p -- "$(dirname -- "$log")"
      rv=0

      # Save original stdout,stderr as fd 11,12
      exec 11>&1 12>&2
      # Redirect stdout and stderr to log file
      exec >"$log" 2>&1

      time /usr/bin/timeout "$TIMEOUT" "$SYNCER" "$child" || rv=$?
      [ "$rv" -ne 0 ] && echo "rv=$rv"

      # Restore stdout,stderr
      exec 1>&11 2>&12 11>&- 12>&-

      if [ "$rv" -ne 0 ]
      then
        echo == "$child"
        cat -- "$log" | sed -e $'s/^.*\r//'
        echo ==
        echo
      fi
    fi
  done
done
