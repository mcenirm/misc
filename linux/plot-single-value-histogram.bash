#!/usr/bin/env bash
LINES=24
COLUMNS=80
spec=%d
field=1
if size=( $( (stty size </dev/tty) 2>/dev/null ) )
then
  LINES=${size[0]}
  COLUMNS=${size[1]}
fi
if [ $# -gt 0 ]
then
  spec=$1
  shift
fi
if [ $# -gt 0 ]
then
  field=$1
  shift
fi
awk "0+\$${field} == \$${field} {printf \"${spec}\n\",\$${field};}" \
| sort -g \
| uniq -c \
| gnuplot -e "set terminal dumb size $COLUMNS, $LINES; set autoscale; plot '-' using 2:1 with lines notitle"
