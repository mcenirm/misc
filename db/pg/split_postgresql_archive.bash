#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

Usage () { cat >&2 <<EOF
Usage: $0 archive destination [pg_restore_option ...]
Split a postgresql archive into one SQL file per object
Where:
  archive              an archive to split (use stdin if omitted)
  destination          a new directory to hold the SQL files
  pg_restore_option    options to give directly to pg_restore
EOF
}

Message () { printf "$1" ; shift ; printf ' %s' "$@" ; printf '\n' ; }
Error () { Message >&2 ERROR "$@" ; }
UsageExit () { Usage ; exit 1 ; }
ErrorExit () { Error "$@" ; exit 1 ; }
Status ( ) { $quiet && return ; Message 'Status -' "$@" ; }

force=no
restore_command=( pg_restore )
while [ $# -gt 0 ]
do
  case "$1" in
    --) shift ; break ;;
    --help|-h|-help|'-?') UsageExit ;;
    --force|-f) force=yes ; shift ;;
    -*) Error "Unrecognized flag:" "$1" ; UsageExit ;;
    *) break ;;
  esac
done
if [ $# -lt 2 ]
then
  UsageExit
fi
archive_path=$1 ; shift
dest_dir=$1 ; shift
if [ $# -gt 0 ]
then
  restore_command+=( "$@" )
fi

toc_file=$dest_dir/toc.txt
common_header_file=$dest_dir/common-header.sql


clean_entry_name () {
  perl -CS -pe '
      chomp;
      s/\s+("[^"]+"|\S+)$//     # remove owner (last identifier on line)
        unless m/ EXTENSION /;  #   except for EXTENSION lines(?)
      s/,\s+/,/g;               # remove space in parameter lists
      s/\s+/./g;                # replace runs of spaces with dot
    ' <<<"$1"
}


if [ ! -e "$archive_path" ]
then
  ErrorExit "Missing archive:" "$archive_path"
fi

if [ -e "$dest_dir" ]
then
  if [ no = "$force" ]
  then
    ErrorExit "Destination already exists:" "$dest_dir"
  else
    if [ ! -d "$dest_dir" ]
    then
      ErrorExit "Destination already exists, but is not a directory:" "$dest_dir"
    fi
  fi
else
  mkdir -- "$dest_dir"
fi

"${restore_command[@]}" --list --file="$toc_file" -- "$archive_path"

mapfile -t toc_entries <"$toc_file"

entry_sql_files=()
for toc_entry in "${toc_entries[@]}"
do
  if [ ';' = "${toc_entry:0:1}" ]
  then
    : skip comment
    continue
  fi
  IFS=\;$IFS read -r entry_index entry_name <<<"$toc_entry"
  entry_name=$( clean_entry_name "$entry_name" )
  entry_toc_file=$dest_dir/$entry_index.$entry_name.toc.txt
  entry_sql_file=$dest_dir/$entry_index.$entry_name.sql
  entry_sql_files+=( "$entry_sql_file" )
  printf '%s\n' "$toc_entry" > "$entry_toc_file"
  "${restore_command[@]}" --file="$entry_sql_file" --use-list="$entry_toc_file" "$archive_path"
  if [ ${#entry_sql_files[*]} -eq 1 ]
  then
    mapfile -t header_lines < "$entry_sql_file"
  else
    header_line_count=${#header_lines[*]}
    mapfile -t -n $header_line_count entry_header_lines < "$entry_sql_file"
    entry_header_line_count=${#entry_header_lines[*]}
    (( min_line_count = header_line_count < entry_header_line_count ? header_line_count : entry_header_line_count ))
    for (( i = 0 ; i < min_line_count ; i++ ))
    do
      [ "${header_lines[$i]}" = "${entry_header_lines[$i]}" ] || break
    done
    for (( j = ${#header_lines[*]}-1 ; j >= i ; j-- ))
    do
      unset "header_lines[$j]"
    done
  fi
done

if [ ${#header_lines[*]} -gt 0 ]
then
  printf '%s\n' "${header_lines[@]}" > "$common_header_file"
  sed --in-place -e "1,${#header_lines[*]} d" "${entry_sql_files[@]}"
fi
