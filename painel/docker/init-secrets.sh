#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
umask 077
mkdir -p secrets
chmod 700 secrets

for name in db_password calendar_secret_key; do
    if [ ! -e "secrets/$name" ]; then
        openssl rand -hex 32 > "secrets/$name"
        chmod 600 "secrets/$name"
        printf 'Criado: secrets/%s\n' "$name"
    else
        printf 'Preservado: secrets/%s\n' "$name"
    fi
done
