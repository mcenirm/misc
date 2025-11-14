#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

default_status_dir=${TMPDIR:-/tmp}/$(basename -- "${BASH_SOURCE[0]}" .bash).$USER
Usage () { cat >&2 <<EOF
Usage: $0 command [args...]
Run command and report any differences since last time
Options
  --status-dir=...      path to directory with status files
                        [$default_status_dir]
EOF
}

UsageExit () { Usage ; exit 1 ; }


status_dir=$default_status_dir
while (( $# > 0 ))
do
  case "$1" in
    --) shift ; break ;;
    --status-dir=*) status_dir=${1#*=} ; shift ;;
    -*) UsageExit ;;
    *) break ;;
  esac
done
if (( $# > 0 ))
then
  cmd=$1
  shift
else
  UsageExit
fi
args=( "$@" )

if ! real_cmd=$(type -P -- "$cmd")
then
  printf >&2 'Error: Not a program: %q\n' "$cmd"
  exit 1
fi


name=$(basename -- "$real_cmd")
read argshash _ <<<"$( printf '%q\n' "${args[@]}" | md5sum )"
slug=status.$name.$argshash
latest_symink=$status_dir/$slug.latest
now=$(date '+%Y-%m-%d %H:%M:%S')
current_name=$slug.$(date -d "$now" +%Y%m%d-%H%M%S).txt
current=$status_dir/$current_name


mkdir -pv -- "$status_dir"

if [[ -L $latest_symink ]]
then
  previous=$(readlink --canonicalize-existing -- "$latest_symink")
  need_diff=true
elif [[ -e $latest_symink ]]
then
  printf >&2 'Error: latest exists but is not symlink: %q\n' "$latest_symink"
  ls >&2 -ld -- "$latest_symink"
  exit 1
else
  need_diff=false
fi


( "$real_cmd" "${args[@]}" ) > "$current"
ln -sf -- "$current_name" "$latest_symink"

if $need_diff
then
  if ! diff -q -- "$previous" "$current" > /dev/null
  then
    printf '== %s\n' "$now"
    printf '==' ; printf ' %q' "$real_cmd" "${args[@]}" ; printf '\n'
    printf '\n'
    diff -u -- "$previous" "$current" || :
    printf '\n'
  fi
fi
