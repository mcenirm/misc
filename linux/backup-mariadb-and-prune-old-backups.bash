#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

default_destination=/var/lib/mariadb-backups
default_date_spec=backup.%Y-%m-%d-%H-%M-%S
default_keep_count=10
default_prune_days=5
default_dbuser=root

Usage () { cat >&2 <<EOF
Usage: $0
Backup MariaDB data files and prune old backups
Options:
  -d <dest>   where to place backups   [$default_destination]
  -k <count>  min # of backups to keep [$default_keep_count]
  -n          dry run
  -p <days>   prune after # days       [$default_prune_days]
  -q          quiet
  -s <spec>   backup dir date format   [$default_date_spec]
  -u <user>   database user            [$default_dbuser]
EOF
}

UsageExit () { Usage ; exit 1 ; }
Error () { if ! $quiet ; then printf 'Error: %s\n' "$*" >&2 ; fi ; }
ErrorExit () { Error "$*" ; exit 1 ; }

destination=$default_destination
date_spec=$default_date_spec
keep_count=$default_keep_count
prune_days=$default_prune_days
dbuser=$default_dbuser
dry_run=false
quiet=false
while getopts 'd:k:p:s:qn' opt; do
  case "$opt" in
    d) destination=$OPTARG ;;
    k) let keep_count=$OPTARG ;;
    p) let prune_days=$OPTARG ;;
    s) date_spec=$OPTARG ;;
    u) dbuser=$OPTARG ;;
    q) quiet=true ;;
    n) dry_run=true ;;
    *) UsageExit ;;
  esac
done
shift $((OPTIND-1))

if [ $# -gt 0 ]
then
  UsageExit
fi

# Check destination
if ! [ -d "$destination" ]
then
  ErrorExit "destination directory should already exist: $destination"
fi

target_dir=$destination/$(date +"$date_spec")
target_log=$target_dir.log
target_prefix=${date_spec%%\%*}

# Prune old backups and log files
mapfile -t existing_target_dirs_by_mtime_asc < <(
    find "$destination" \
        -maxdepth 1 \
        -type d \
        -name "$target_prefix*" \
        -printf '%T@:%f\n' \
    | sed -r -e 's/^([0-9]+)\.[0-9]+:/\1:/' \
    | sort -n
)
if [ ${#existing_target_dirs_by_mtime_asc[*]} -gt $keep_count ]
then
  let mtime_threshold=$(date +%s -d "$prune_days days ago")
  let total=${#existing_target_dirs_by_mtime_asc[*]}
  let prune_count=$(( $total - $keep_count ))
  let prune_index=0 || :
  declare -p  mtime_threshold total prune_count
  while [ $prune_index -lt $prune_count ]
  do
    IFS=: read -r mtime name <<<"${existing_target_dirs_by_mtime_asc[$prune_index]}"
    if [ $mtime -lt $mtime_threshold ]
    then
      old_target_dir=$destination/$name
      old_target_log=$destination/$name.log
      if $dry_run
      then
        if ! $quiet
        then
          printf '** would be pruned: %q\n' "$old_target_dir" "$old_target_log"
        fi
      else
        (
          printf '**\n'
          printf '** pruning: %q\n' "$old_target_dir" "$old_target_log"
          printf '**\n'
          rm -rfv -- "$old_target_dir" "$old_target_log"
        ) >> "$target_log" 2>&1
      fi
    else
      break
    fi
    let ++$prune_index
  done
fi

# Check target directory
if [ -e "$target_dir" ]
then
  ErrorExit "New backup directory should not already exist: $target_dir"
fi

# Perform backup
backup_cmd=(
  mariabackup
  --backup
  --target-dir="$target_dir"
  --user="$dbuser"
)
prepare_cmd=(
  mariabackup
  --prepare
  --target-dir="$target_dir"
)
if $dry_run
then
  if ! $quiet
  then
    printf '**'
    printf ' %q' "${backup_cmd[@]}"
    printf ' >> %q 2>&1\n' "$target_log"
    printf '**'
    printf ' %q' "${prepare_cmd[@]}"
    printf ' >> %q 2>&1\n' "$target_log"
  fi
else
  if ! (
    printf '**\n**'
    printf ' %q' "${backup_cmd[@]}"
    printf '\n**\n'
    "${backup_cmd[@]}"
  ) >> "$target_log" 2>&1
  then
    ErrorExit "backup command failed: $target_log"
  fi
  if ! (
    printf '**\n**'
    printf ' %q' "${prepare_cmd[@]}"
    printf '\n**\n'
    "${prepare_cmd[@]}"
  ) >> "$target_log" 2>&1
  then
    ErrorExit "prepare command failed: $target_log"
  fi
fi
