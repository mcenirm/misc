#!/usr/bin/env bash

dir="$PWD"
while [[ $dir != / ]]; do
  if [[ -e $dir/composer.json ]]
  then
    for cmd in drush.php drush
    do
      for pth in drush/drush bin
      do
        prg=$dir/vendor/$pth/$cmd
        if [[ -x $prg && $(head -c2 "$prg") == '#!' ]]
        then
          exec "$prg" "$@"
        elif [[ $prg == *.php ]]
        then
          exec php -f "$prg" -- "$@"
        fi
      done
    done
  fi
  dir=$(dirname "$dir")
done

echo "Error: No vendored Drush found in parent directories." >&2
exit 1
