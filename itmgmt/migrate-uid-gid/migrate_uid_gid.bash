#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

Usage () { cat >&2 <<EOF
Usage: $0 [passwd|group] name:oldid:newid [...]
Migrate UID/GID
Where:
  passwd  migrate users
  group   migrate groups
  name    name of the user/group
  oldid   old uid/gid
  newid   new uid/gid
Options:
  -q      do not show progress
EOF
}

UsageExit () { Usage ; exit 1 ; }

GetFileID_passwd () { stat --printf=%u -- "$1" ; }
GetFileID_group  () { stat --printf=%g -- "$1" ; }

_FindFiles () { find 2>/dev/null "$1" -xdev -printf "$2"' %y %p\n' || : ; }
FindFiles_passwd () { _FindFiles "$1" %U ; }
FindFiles_group  () { _FindFiles "$1" %G ; }

FixFile_passwd () { chown -c --from="$1" "$2" "$3" ; }
FixFile_group  () { chown -c --from=:"$1" :"$2" "$3" ; }

ChangeID_passwd () { lusermod  --uid="$2" "$1" ; }
ChangeID_group  () { lgroupmod --gid="$2" "$1" ; }


show_progress=true
while [ $# -gt 0 ]
do
  case "$1" in
    --) shift ; break ;;
    -q) show_progress=false ; shift ; break ;;
    -*) UsageExit ;;
    *) break ;;
  esac
done
[ $# -ge 1 ] || UsageExit
case "$1" in
  passwd) dbname=passwd ;;
  group) dbname=group ;;
  *) UsageExit ;;
esac
shift
[ $# -ge 1 ] || UsageExit

declare -A name_map
declare -A id_map

for entry in "$@"
do
  IFS=: read -r name oldid newid <<<"$entry"
  curid=$(getent $dbname "$name" | cut -d: -f3 || echo MISSING)
  case "$curid" in
    MISSING) echo >&2 "SKIPPING: $dbname unknown name: $entry" ;;
    $oldid)
      id_map[$oldid]=$newid
      name_map[$name]=$oldid
      ;;
    *) echo >&2 "SKIPPING: $dbname id mismatch: $curid != $entry" ;;
  esac
done

mountpoints=()
declare -A iused_map
while read -r dev fstype inodes iused ifree iusep mountpoint
do
  case "$fstype" in
    ext4|xfs) : ;;
    *) continue ;;
  esac
  case "$mountpoint" in
    /boot) continue ;;
    *) : ;;
  esac
  mountpoints+=( "$mountpoint" )
  iused_map[$mountpoint]=$iused
done < <(df -ilPT)
if [ "${#mountpoints[@]}" -lt 1 ]
then
  echo >&2 "Warning: NO LOCAL FILESYSTEMS"
  exit 0
fi

declare -A found_ids=()
for mountpoint in "${mountpoints[@]}"
do
  iused=${iused_map[$mountpoint]}
  count=0
  modcount=0
  progress=0
  while read -r fid ftype item
  do
    let ++count
    let "progress = 100 * $count / $iused" || :
    $show_progress && echo >&2 -n "$progress% - $mountpoint"$'\r'
    case "$ftype" in l) continue ;; esac
    [ "${id_map[$fid]+EXISTS}" = EXISTS ] || continue
    let ++modcount
    let ++found_ids[$fid]
    FixFile_$dbname "$fid" "${id_map[$fid]}" "$item"
  done < <(FindFiles_$dbname "$mountpoint")
  $show_progress && echo >&2
done

for name in "${!name_map[@]}"
do
  oldid=${name_map[$name]}
  if [ "${found_ids[$oldid]+EXISTS}" = EXISTS ]
  then
    newid=${id_map[$oldid]}
    ChangeID_$dbname "$name" "$newid"
  fi
done
