#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

ccfid=999100
t=$(date -u -d '2024-09-17 12:00:00' +%s)
delays=(
     68
     37
    284
     82
    262
     21
    305
     54
    232
    314
)

for d in "${delays[@]}"
do
  let ccfid++
  let t+=$d
  n=CCFID_${ccfid}_$(date -u -d @$t +%Y%j%H%M%S)_IMAGE
  svg=$n.svg
  tif=$n.tif
  #printf '%d  %'"'"'12d  %s  %s\n' $ccfid "$t" "$(date -u -d @$t '+%F %T')" "$svg"
  cat > "$svg" <<EOF
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="6in" height="4in" viewBox="0 0 6 4" version="1.1" xmlns="http://www.w3.org/2000/svg">
  <g>
    <text x="50%" y="50%" height="4" width="6" style="font-size:0.5px;font-family:sans-serif;font-weight:bold;" dominant-baseline="middle" text-anchor="middle">
      <tspan x="50%" dy="-1.8em">CCFID ${ccfid}</tspan>
      <tspan x="50%" dy="1.8em">$(date -u -d "@$t" '+%Y/%j (%b %d)')</tspan>
      <tspan x="50%" dy="1.8em">$(date -u -d "@$t" +%T) UTC</tspan>
    </text>
    <rect style="fill-opacity:0;stroke:black;stroke-width:0.1;" width="5.9" height="3.9" x="0.05" y="0.05" />
  </g>
</svg>
EOF
  convert "$svg" "$tif"
  touch -t "$(date -d @$t +%Y%m%d%H%M.%S)" "$svg" "$tif"
done
