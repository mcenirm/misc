#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

Usage () { cat >&2 <<EOF
Usage: $0 foo [bar ...]
Some sort of vague description about this script
Where:
  foo    a foo
  bar    some bars
Options:
  -q     quiet
  -n     dry run
EOF
}

UsageExit () { Usage ; exit 1 ; }

# here=$(cd -- "$(dirname -- "$BASH_SOURCE")" && /bin/pwd)
#  OR
# cd -- "$(dirname -- "$BASH_SOURCE")"

dry_run=false
quiet=false
while [ $# -gt 0 ]
do
  case "$1" in
    --) shift ; break ;;
    -q) quiet=true ; shift ;;
    -n) dry_run=true ; shift ;;
    -*) UsageExit ;;
    *) break ;;
  esac
done
#if [ $# -gt 0 ]
#then
#  foo=$1
#  shift
#else
#  UsageExit
#fi
#if [ $# -gt 0 ]
#then
#  bars=( "$@" )
#else
#  bars=()
#fi

...
