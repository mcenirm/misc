#!/bin/bash
set -e
set -u

Usage () { cat >&2 <<EOF
Usage: $0 FOLDER [...]
Sync local archive to offsite backup at S3
Where:
  FOLDER  relative-to-mountpoint prefix to sync
          (Use "." for entire archive)
Note: S3 does not support symlinks at all.
EOF
}

# Name of S3 bucket for offsite backup
bucket='!! NAME OF SOME BUCKET IN S3 !!'

# Ordered list of archive mountpoints to try
archive_mountpoints=(
    /offsite-snowball
    /archive
)

# Folder in archive that is guaranteed to exist if archive is mounted
archive_mounted_test_folder='!! NAME OF SOME FOLDER THAT EXISTS ON THE archive VOLUME SO WE KNOW IF THE VOLUME IS MOUNTED !!'

# Command line options for aws s3 sync command
s3_sync_options=(
    # --dryrun
    # --only-show-errors
    --no-follow-symlinks
    # --delete
)

# Flag defaults
verbose=false

# Check for flags
while [ $# -gt 0 ] ; do
  case "$1" in
    --) shift ; break ;;
    -*) Usage ; exit 1 ;;
    *) break ;;
  esac
done

# Check for required arguments
if [ $# -lt 1 ] ; then
  Usage
  exit 1
fi

# Choose first archive mountpoint that has test folder
archive=''
for candidate_archive in "${archive_mountpoints[@]}" ; do
  if [ -d "$candidate_archive/$archive_mounted_test_folder" ] ; then
    archive=${candidate_archive}
    break
  fi
done

# Jump to archive to simplify later tests
cd "$archive"

# Check that folders exist and normalize them
folders=()
for folder in "$@" ; do
  # Make sure folder exists and is a folder
  if [ ! -d "$folder" ] ; then
    if [ ! -e "$folder" ] ; then
      echo >&2 ERROR: folder does not exist: "$folder"
    else
      echo >&2 ERROR: item exists but is not a folder: "$folder"
    fi
    Usage
    exit 2
  fi

  # Canonicalize path to folder
  real_folder=$( readlink -e "$folder" )

  # Special case for entire archive
  if [ "$real_folder" = "$archive" ] ; then
    folders=( . )
    break
  fi

  # Check if folder is in archive
  safe_folder=${real_folder#$archive/}
  if [ "${safe_folder:0:1}" = / ] ; then
    echo >&2 ERROR: folder is outside archive: "$folder"
    Usage
    exit 2
  fi
  folders+=( "$safe_folder" )
done

if [ "${folders[0]}" != . ] ; then
  # Ignore duplicates and already-covered descendants
  mapfile -t sorted_folders < <( printf '%s\n' "${folders[@]}" | sort -u )
  folders=()
  for folder in "${sorted_folders[@]}" ; do
    include_folder=true
    if [ "${#folders[@]}" -gt 0 ] ; then
      for previous_folder in "${folders[@]}" ; do
        if [ "${folder#$previous_folder/}" != "$folder" ] ; then
          include_folder=false
          break
        fi
      done
    fi
    if $include_folder ; then
      folders+=( "$folder" )
    fi
  done
fi

# Sync folders
for local_folder in "${folders[@]}" ; do
  s3_prefix=/$local_folder
  if [ "$local_folder" = . ] ; then
    s3_prefix=''
  fi
  (
    if $verbose ; then
      set -x
    fi
    aws s3 sync "${s3_sync_options[@]}" "$local_folder" s3://"$bucket$s3_prefix"
  )
done
