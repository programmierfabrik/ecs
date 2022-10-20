#!/bin/bash
set -e

# If we run daphne (web), apply migrations, execute bootstrap and clear the cache (if the files updated, we need to use the new files)
if [[ $1 == "daphne" ]]; then
    pipenv run ./manage.py migrate --noinput
    pipenv run ./manage.py bootstrap
    pipenv run ./manage.py clear_cache
fi;

echo "pipenv run $*"
pipenv run "$@"
