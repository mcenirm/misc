#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

Usage () { cat >&2 <<EOF
Usage: $0 REMOTE
EOF
}

if [[ $# -ne 1 ]]
then
  Usage
  exit 1
fi

rurl=$1

case "$rurl" in
  https://*|http://*)
    echo >&2 TODO: handle HTTP remotes
    exit 2
    ;;
  *:*)
    # assume SSH
    rpath=${rurl##*:}
    user_and_site=${rurl%:$rpath}
    site=${user_and_site#*@}
    lpath=$site/$rpath
    ;;
  *)
    echo >&2 TODO: handle file remotes
    exit 2
    ;;
esac


main () {
  if already_cloned
  then
    update
  else
    clone
  fi
}


already_cloned () {
  [[ -d $lpath ]] && _run_git_in_local_repo rev-parse
}


update () {
  _run_git_in_local_repo remote update --prune
}


clone () {
  _run_git clone --quiet --mirror "$rurl" "$lpath"
}


_run_git_in_local_repo () {
  _run_git --git-dir="$lpath" "$@"
}


_run_git () {
  git "$@" >/dev/null
}


main
