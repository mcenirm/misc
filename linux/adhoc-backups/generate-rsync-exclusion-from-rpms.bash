#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

non_root_warning='Not running this as root might result in an incomplete exclusion list due to permissions.'

Usage () {
  cat >&2 <<EOF
Usage: $0 [FILE]
Generate rsync exclusion list for unchanged files from RPMs
Where:
  FILE    use a file with the output from "rpm -V"
          instead of running "rpm -V" (use "-" for stdin)
Options:
  --show       show "rpm -V" command that would be used and exit
Note: ${non_root_warning}
EOF
}

UsageExit () { Usage ; exit 1 ; }

rpm_v_cmd=(
  rpm
  --verify
  --all
  --verbose
  --nodeps
  --nodigest
  --noscripts
  --nosignature
  --nouser
  --nogroup
  --nomtime
  --nomode
  --nordev
  --nocaps
)

show=false
while [ $# -gt 0 ]
do
  case "$1" in
    --) shift ; break ;;
    --show) show=true ; shift ;;
    -) break ;;
    -*) UsageExit ;;
    *) break ;;
  esac
done

if $show
then
  printf ' %q' "${rpm_v_cmd[@]}" ; echo
  exit 0
fi

if [ $# -gt 1 ]
then
  UsageExit
fi

if ! [ -O / ]
then
  echo >&2 "Warning: ${non_root_warning}"
fi

(
  # Determine source of input
  if [ $# -eq 0 ]
  then
    "${rpm_v_cmd[@]}"
  else
    cat -- "$1"
  fi
) | (
  # Keep only unchanged items
  sed -n -e 's#^\.\.\.\.\.\.\.\.\.  [ acdlmn] /#/#p'
) | (
  # For regular files and symlinks,
  # print exclusion rules based on real paths to item
  declare -A realparentcache
  setrealparent () {
    if [ "${realparentcache[$parent]+EXISTS}" ]
    then
      realparent=${realparentcache[$parent]}
    else
      realparent=$(readlink -f -- "$parent")
      realparentcache[$parent]=$realparent
    fi
  }
  while read -r path
  do
    if [ -f "$path" -o -L "$path" ]
    then
      name=${path##*/}
      parent=${path%/*} ; parent=${parent:=/}
      setrealparent
      realpath=$realparent/$name
      case "$realpath" in
        //*) realpath=${realpath#/} ;;
      esac
      printf '%s %s\n' - "$realpath"
    fi
  done
) | (
  # Sort and remove duplicates
  sort -u
) | (
  # Escape wildcards according to Use rsync's idiosyncratic rule
  sed -E -e '/[[*?]/s/([[*?\\])/\\\1/g'
)
