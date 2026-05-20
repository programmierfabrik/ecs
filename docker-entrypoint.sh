#!/bin/bash
set -e

# If we run uvicorn (web), apply migrations, execute bootstrap and clear the cache (if the files updated, we need to use the new files)
if [[ $1 == "uvicorn" ]]; then
    poetry run ./manage.py migrate --noinput
    poetry run ./manage.py bootstrap
    poetry run ./manage.py clear_cache
fi;

echo "poetry run $*"
poetry run "$@"
