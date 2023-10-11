#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x


umask 027
export PGUSER=postgres
BACKUPS_DIR=/path/to/backups_dir
KEEP=15
declare -a DBNAMES=( _GLOBALS_ )
DATE_FORMAT='%Y-%m-%d'
DATE_FIND_GLOB='????-??-??'
DATE_MATCH_PAT='[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]'
DATE=$(date +"$DATE_FORMAT")
T=$(mktemp)
trap "rm -f -- '$T'" EXIT


main () {
  lookup_dbnames

  local should_exit=false
  for dbname in "${DBNAMES[@]}"
  do
    check_existing "$dbname" || should_exit=true
  done
  if $should_exit
  then
    exit 1
  fi

  for dbname in "${DBNAMES[@]}"
  do
    rotate "$dbname"
    backup "$dbname"
  done
}


ErrorExit () { set +x ; Error "$@" ; exit 1 ; }
Error () { set +x ; ( printf 'Error:' ; printf ' %s' "$@" ; printf '\n' ) >&2 ; }
TODOExit () { set +x ; TODO "$@" ; exit 1 ; }
TODO () { set +x ; ( printf 'TODO:' ; printf ' %s' "$@" ; printf '\n' ) >&2 ; }


lookup_dbnames () {
  local dbname

  while read -r dbname
  do
    if [ -n "$dbname" -a "$dbname" != template0 ]
    then
      DBNAMES+=( "$dbname" )
    fi
  done < <(
    /usr/bin/psql \
        --no-password \
        --no-align --tuples-only \
        --command='select datname from pg_database;' \
        postgres
  )
}


check_existing () {
  local dbname=$1
  local backup_name=$(backup_name_for_dbname "$dbname")
  local backup=$(backup_for_backup_name "$backup_name")
  local label='Database'

  if is_globals "$dbname"
  then
    label='Globals'
  fi

  if [ -e "$backup" ]
  then
    Error "$label backup already exists:" "$backup"
    return 1
  fi
}


rotate () {
  local dbname=$1
  local backup_name=$(backup_name_for_dbname "$dbname")
  local today_glob=${backup_name/$DATE/$DATE_FIND_GLOB}
  local -a find_names=( -name "$today_glob" )
  local base=db.${dbname}

  if is_globals "$dbname"
  then
    base=globals
  fi

  # legacy logrotate backups
  find_names+=(
      -o -name "$base".pg
      -o -name "$base".pg-'????????'
  )

  mapfile -t old_names < <(
    find \
        "$BACKUPS_DIR" \
        -mindepth 1 -maxdepth 1 \
        '(' "${find_names[@]}" ')' \
        -printf '%P\n'
  )

  for old_name in "${old_names[@]}"
  do
    old_date=UNSET
    old_category=UNSET
    case "$old_name" in
      *.pg)
        old_date=$(date -r "$BACKUPS_DIR/$old_name" +"$DATE_FORMAT")
        old_category=1-logrotate-mostrecent
        ;;
      *.pg-????????)
        old_date=$(date -d "${old_name##*.pg-} -1 day" +"$DATE_FORMAT")
        old_category=1-logrotate-rotated
        ;;
      *.${DATE_FIND_GLOB}|*.${DATE_FIND_GLOB}.*)
        [[ "$old_name" =~ $DATE_MATCH_PAT ]]
        old_date=$(date -d "$BASH_REMATCH" +"$DATE_FORMAT")
        old_category=2-backup-with-date
        ;;
      *)
        ErrorExit 'Mismatch find and categorizer:' "$old_name" "$(printf '+ %q\n' "${find_names[@]}")"
        ;;
    esac
    printf '%s\t%s\t%s\t%s\n' "$old_date" "$old_category" "$old_name"
  done \
  | sort > "$T"

  mapfile -t sorted_old_names < <(
    cut -f 3 -- "$T"
  )
  count=${#sorted_old_names[*]}
  for old_name in "${sorted_old_names[@]}"
  do
    [ $count -ge $KEEP ] || break
    remove "$old_name"
    let count--
  done
}


backup () {
  local dbname=$1
  local backup_name=$(backup_name_for_dbname "$dbname")
  local backup=$(backup_for_backup_name "$backup_name")

  if is_globals "$dbname"
  then
    /usr/bin/pg_dumpall \
        --no-password \
        --globals-only \
        --file="$backup"
  else
    /usr/bin/pg_dump \
        --no-password \
        --format=directory \
        --file="$backup" \
        "$dbname"
    if [ -d "$backup" ]
    then
      # workaround pg_dump ignoring umask for directory (cf postgresql BUG #15502)
      chmod "$(umask -S)" -- "$backup"
    fi
  fi
}


backup_name_for_dbname () {
  local dbname=$1
  local shortname=db.$dbname
  local suffix='' # blank for directory, .tgz for tar format

  if is_globals "$dbname"
  then
    shortname='globals'
    suffix='.sql'
  fi

  printf 'pg.%s.%s%s\n' "$shortname" "$DATE" "$suffix"
}


backup_for_backup_name () {
  local backup_name=$1

  printf '%s/%s\n' "$BACKUPS_DIR" "$backup_name"
}


is_globals () {
  local dbname=$1

  [ "$dbname" = _GLOBALS_ ]
}


remove () {
  local old_name=$1

  rm -rf -- "$old_name"
}
  

main
