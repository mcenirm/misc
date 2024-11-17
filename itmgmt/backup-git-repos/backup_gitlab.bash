#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# Setup venv
VENV=$HOME/.venv.$(basename -- "${BASH_SOURCE[0]}" .bash)
if [[ -d $VENV ]]
then
  source -- "$VENV/bin/activate"
else
  python3 -m venv --upgrade-deps "$VENV"
  source -- "$VENV/bin/activate"
  python3 -m pip --require-virtualenv install python-gitlab
fi

# Save the list of gitlab repos to a temp file
list=$HOME/gitlab_repos.txt
tmplist=$list.tmp
baklist=$list.bak
python3 ./list_my_gitlab_repos.py | sort > "$tmplist"

# If there have been no changes to the list,
# then do not overwrite the list file
if ! diff -q "$list" "$tmplist" >/dev/null
then
  rm -f -- "$baklist"
  ln -fT -- "$list" "$baklist"
  ln -fT -- "$tmplist" "$list"
fi
rm -f -- "$tmplist"

# Sync each repository
while read -r remote
do
  out=$(mktemp)
  bash ./sync_git_repo_from_remote.bash "$remote" >"$out" 2>&1
  # Wrap any output to show the remote,
  # but not if there was no output
  if [ -s "$out" ]
  then
    echo ==== "$remote"
    echo
    cat "$out"
    echo ====
    echo
  fi
  rm -f "$out"
done < "$list"
