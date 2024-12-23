#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

# report only transitions between responding and not responding

ping "$1" \
| awk '
    /bytes from/ {
      if (status == 0) {
        print strftime("%Y-%m-%d %H:%M:%S") ": Responding";
        status = 1;
      }
    }

    /Destination Host Unreachable/ {
      if (status == 1) {
        print strftime("%Y-%m-%d %H:%M:%S") ": Not Responding";
        status = 0;
      }
    }
  '
