#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

# TODO cope with "$@" vs stdin

# TODO see if this would work instead:
#     grep -n -e '^COPY ' -e '^\\\.$'

grep -n -v -E \
    -e '^$' \
    -e '^--' \
    -e '^SELECT pg_catalog\.(set_config|setval)\(' \
    -e '^SET ' \
    -e '^(CREATE|ALTER) (FUNCTION|TABLE|SEQUENCE|INDEX) ' \
    -e '^    ' \
    -e '^\);$' \
    -e '^COMMENT ON ' \
    -e $'\t' \
    -e '^GRANT ' \
| while IFS=${IFS}: read -r n copy_or_end_of_data table_name rest
  do
    case "$copy_or_end_of_data" in
      COPY)
        n_for_copy=$n
        table_for_copy=$table_name
        ;;
      \\.)
        echo $(( $n - $n_for_copy - 1 )) ${table_for_copy#public.}
        ;;
      *)
        echo ERROR
        declare -p n copy_or_end_of_data table_name rest n_for_copy table_for_copy
        break
        ;;
    esac
  done \
| column -t
