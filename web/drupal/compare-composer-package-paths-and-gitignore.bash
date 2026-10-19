#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

if (( $# > 0 ))
then
  cat >&2 <<EOF
Usage: $(basename -- ${BASH_SOURCE[0]})

Show which composer packages are not being gitignored.

Must be inside a git working tree (or use GIT_WORK_TREE),
with a composer.json file in the current directory.

EOF
  exit 64 # EX_USAGE
fi

if [[ ! -e composer.json ]]
then
  echo >&2 Error: Change to a directory with composer.json and try again.
  exit 64 # EX_USAGE
fi

if [[ $(git rev-parse --is-inside-work-tree 2>/dev/null) != true ]]
then
  echo >&2 Error: Change to a git working tree and try again.
  exit 64 # EX_USAGE
fi

mapfile -t package_paths < <(
  composer show --path --format=json \
  | jq -r '
      .installed
      | map(
          .path                      # get absolute path
          | select(. != null)        # skip metapackages
          | ltrimstr(env.PWD + "/")  # convert to relative path
        )
      | sort
      | .[]
    '
)

let count=0 || :
for pp in "${package_paths[@]}"
do
  if git ls-files --error-unmatch -- "$pp" >& /dev/null
  then
    # path contains at least one tracked file
    # not sure what to do about that
    : TODO
  else
    if git check-ignore -q -- "$pp"
    then
      # path is being ignored
      : PASS
    else
      # and convert back to repo-absolute path
      # for use in .gitignore
      printf '/%s\n' "$pp"
      let ++count
    fi
  fi
done

if (( $count < 1 ))
then
  echo >&2 '(No package paths are NOT being gitignored.)'
  exit 1
fi
