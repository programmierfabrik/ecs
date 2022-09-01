#!/bin/bash
set -e

# If we run daphne (web), apply migrations and execute bootstrap
if [[ $1 == "daphne" ]]; then
    pipenv run ./manage.py migrate --noinput
    pipenv run ./manage.py bootstrap
fi;

echo "pipenv run $*"
pipenv run "$@"
