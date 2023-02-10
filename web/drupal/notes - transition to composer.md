## Overview

TODO, but this assumes a Drupal 8 instance that started from a distribution archive, not from Composer.


## Preparation

1. Identify the Drupal root folder (contains `core/` and `composer.json`)

    ```shell
    DRUPALROOT=...
    ```

2. Create a scratch directory (outside the web document root) to hold the output files

    ```shell
    SCRATCH=...
    mkdir -v "$SCRATCH"
    ```


## Collect extension details

1. Use Drush to collect all extensions

    ```shell
    cd "$SCRATCH"
    drush --root="$DRUPALROOT" pml --format=json 2>/dev/null | jq -S . > extensions.json
    ```

2. Filter out what looks like extensions from Drupal core

    ```shell
    jq -S 'with_entries(select(.value.path|test("^core/")|not))' < extensions.json > non-core-extensions.json
    ```

3. Just the enabled ones

    ```shell
    jq -S 'with_entries(select(.value.status == "Enabled"))' < non-core-extensions.json > enabled-nce.json
    ```

4. Determine the projects with at least one enabled extension

    ```shell
    jq -S 'with_entries(select(.value.project|test("."))|(.key=.value.project)|(.value=(.value.version|tostring)))' < enabled-nce.json > projects-in-use.json
    ```


## Troubleshoot installability and dependencies

1. Create fake composer.json based on the projects in use

    Note: "8.9.20" is the final release of Drupal 8.x

    ```shell
    cd "$SCRATCH"
    mkdir -v fake
    jq -S '{"repositories":[{"type":"composer","url":"https://packages.drupal.org/8"}],"require":(with_entries((.key|="drupal/"+.)|(.value|=sub("^8\\.x-";"")))+({"drupal/core":"8.9.20"}))}' < projects-in-use.json > fake/composer.json
    ```

2. Try to resolve requirements and download packages

    ```shell
    cd "$SCRATCH"/fake
    composer install
    ```

    If the output includes

    > Your requirements could not be resolved to an installable set of packages.

    ... then review the problems and potential causes.

    *  "... could not be found in any version, there may be a typo in the package name."
    *  "drupal/foo dev-1.x requires drupal/core ^9.3 || ^10 -> ... but it conflicts with your root composer.json require (8.9.20)."

3. If a problematic package is using a branch alias (eg, "dev-1.x"), then check the available versions and try to require a specific version

       ```shell
       composer show -a drupal/foo
       composer require drupal/foo:1.2.3
       ```

4. Remove any remaining problematic packages

       ```shell
       composer remove drupal/foo drupal/bar
       ```

Note: Because the fake `composer.json` file does include `composer/installers` and `installer-paths`,
all of the packages will be downloaded to the default `vendor/` folder (eg, `vendor/drupal/core`).


## Compare downloaded packages against existing files

1. Determine which packages have not been modified from the downloaded versions

    ```shell
    cd "$SCRATCH"
    rm -fv to-be-{cleaned,required,resolved}.lst
    for project in $(jq -r 'keys[]' < projects-in-use.json )
    do
      fresh=fake/vendor/drupal/$project
      existing=$( jq -r .$project.path < enabled-nce.json )
      if [ -d "$fresh" ]
      then
        echo -e "# $PWD/$fresh\n# $DRUPALROOT/$existing" > differences."$project".out
        if diff -ru "$fresh" "$DRUPALROOT"/"$existing" >> differences."$project".out
        then
          rm -f differences."$project".out
          echo "i  $existing"
          echo "$existing" >> to-be-cleaned.lst
          jq --arg p drupal/"$project" -r '$p+":"+.require[$p]' < fake/composer.json >> to-be-required.lst
        else
          echo "X  $existing"
        fi
      else
        echo "M  $existing"
        echo "$existing" >> to-be-resolved.lst
      fi
    done | sort
    ```

    Legend:

    * `i` The existing files are identical to the downloaded packages.
    * `M` The project is missing from the downloaded packages.
    * `X` The existing files are different from the downloaded.

    Files produced:

    * `differences.$project.out` - The output from the `diff` command
    * `to-be-cleaned.lst` - A list of paths (relative to `$DRUPALROOT`) that can be removed
    * `to-be-required.lst` - A list of packages (with versions) to be `composer require`d
    * `to-be-resolved.lst` - A list of packages that require further version resolution


## Replace unchanged existing files with "required" packages

1. Require and download unchanged packages

    ```shell
    cd "$DRUPALROOT"
    composer require $(cat "$SCRATCH"/to-be-required.lst)
    ```

2. Archive existing unchanged files

    ```shell
    mkdir -v "$SCRATCH"/archived
    cd "$DRUPALROOT"
    for existing in $(cat "$SCRATCH"/to-be-cleaned.lst)
    do
      dest=$SCRATCH/archived/$(dirname "$existing")
      mkdir -pv "$dest"
      mv -iv "$existing" "$dest"
    done
    ```

3. Rebuild Drupal cache

    ```shell
    drush --root="$DRUPALROOT" cr
    ```

4. Backup previous extension details

    ```shell
    cd "$SCRATCH"
    ts=$(date -d @$(stat -c %Y extensions.json) +%Y%m%d-%H%M%S)
    for f in extensions.json non-core-extensions.json enabled-nce.json projects-in-use.json
    do
      mv -iv $f details.$ts.$f
    done
    ```
