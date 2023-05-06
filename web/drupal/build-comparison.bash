#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

default_wildcard='??????????????/'
default_outdir=.

Usage () { cat >&2 <<EOF
Usage: $0 [YYYYMMDDHHMMSS ...]
Download versioned Drupal extensions for comparison
Where:
  YYYYMMDDHHMMSS    timestamped directory created by Drush
                    [all that match $default_wildcard]
Options:
  -f             force redownload
  -n             dry run
  -o <outdir>    where to place comparison directories [$default_outdir]
EOF
}

UsageExit () { Usage ; exit 1 ; }
Error () { if ! $quiet ; then printf 'Error: %s\n' "$*" >&2 ; fi ; }
ErrorExit () { Error "$*" ; exit 1 ; }
Verbose () {
  printf '++'
  printf ' %q' "$@"
  printf '\n'
}
Action () {
  Verbose "$@"
  if ! $dry_run
  then
    "$@"
  fi
}
ExtractFromInfo () {
  grep -P -o -m 1 -e '^\s*'"$1"'\s*=\s*"\K([^"]+)' -- "$2"
}

force=false
dry_run=false
outdir=$default_outdir
while getopts 'fno:' opt; do
  case "$opt" in
    f) force=true ;;
    n) dry_run=true ;;
    o) outdir=$OPTARG ;;
    *) UsageExit ;;
  esac
done
shift $((OPTIND-1))

if [ $# -eq 0 ]
then
  set -- $default_wildcard
fi

for tsdir in "$@"
do
  cmptsdir=$outdir/comparison-$(basename -- "$tsdir")
  if [ ! -d "$cmptsdir" ]
  then
    Action mkdir -pv -- "$cmptsdir"
  fi

  for extinfo in "$tsdir"/*/*/*.info
  do
    extdir=$(dirname -- "$extinfo")
    cmpextdir=$cmptsdir/${extdir#$tsdir}
    cmpdest=$(dirname -- "$cmpextdir")

    if [ -d "$cmpextdir" ]
    then
      if ! $force
      then
        continue
      else
        Action rm -rf -- "$cmpextdir"
      fi
    fi

    extproject=$(ExtractFromInfo project "$extinfo")
    extversion=$(ExtractFromInfo version "$extinfo")
    nondevversion=${extversion%-dev}

    dlcmd=(
        drush
        -y
        pm-download
        --destination="$cmpdest"
        --skip
    )
    if [ "$extversion" != "${nondevversion}" ]
    then
        continue
        #dlcmd+=( --dev )
    fi
    Action "${dlcmd[@]}" $extproject-$nondevversion
  done
done
