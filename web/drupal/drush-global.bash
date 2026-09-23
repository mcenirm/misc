#!/usr/bin/env bash

dir="$PWD"
while [[ $dir != / ]]; do
  for cmd in drush.php drush
  do
    for pth in drush/drush bin
    do
      prg=$dir/vendor/$pth/$cmd
      if [[ -x $prg && -e $dir/composer.json ]]
      then
        exec "$prg" "$@"
      fi
    done
  done
  dir=$(dirname "$dir")
done

echo "Error: No vendored Drush found in parent directories." >&2
exit 1
