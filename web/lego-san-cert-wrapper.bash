#!/usr/bin/env bash
# vim: shiftwidth=2 tabstop=2 expandtab
set -euo pipefail
[[ "${TRACE-0}" == "1" ]] && set -x

# Clunky wrapper around https://go-acme.github.io/lego/
#
# Use case
# * Multiple websites per cert
# * One cert per deployment environment
# * File-based validation for use with `--http.webroot` option
#
# Lego limitation(?)
# * All domains for a single cert must share a webroot
#
# TODO
# [ ] load most settings from files

#s='https://acme-staging-v02.api.letsencrypt.org/directory'
s='https://acme-v02.api.letsencrypt.org/directory'
m='XXXXXX@YYYYYY.ZZZZZZ'  # admin email for registration

base=example.com
sites=(
    www
    static
)
envs=(
    prod
    staging
    dev
)

lego_opts=(
    --accept-tos
    --email $m
    --server $s
    --http
)

argaction=${1:-_auto}

for env in "${envs[@]}"
do
  opts=( "${lego_opts[@]}" )
  suffix=${env#prod}.$base
  domains=()
  for site in "${sites[@]}"
  do
    domain=$site$suffix
    domains+=( $domain )
    if [ $domain = www.$base ]
    then
      domains+=( $base )
    fi
  done
  crt=${LEGO_PATH:-${HOME}/.lego}/certificates/$domains.crt
  webroot=/var/www/$domains/html
  opts+=( --http.webroot $webroot )
  for domain in "${domains[@]}"
  do
    opts+=( --domains $domain )
  done
  if [ "$argaction" = _auto ]
  then
    if [ -f "$crt" ]
    then
      action=renew
    else
      action=run
    fi
  else
    action=$argaction
  fi

  ( set -x ; lego "${opts[@]}" "$action" )
done
