# ECS

The ethic commission system (ECS) is an open-source webservice supporting clinical trials approval, monitoring and the
electronic management of the related data. See the [ECS Homepage](https://ecs-org.github.io/ecs-docs/) for more
information about ECS.

## Development

### Required packages

You need `docker` and `docker-compose` for the development database. You need `python3.10` with `pip3` for the ecs and a
few additional packages:

Ubuntu 22.04:

```
gettext
libpq-dev
```

Start the development database:

```shell
docker-compose up -d
```

To apply the migrations and execute the bootstrap you can either do it via console:

```shell
pipenv run ./manage.py migrate
pipenv run ./manage.py bootstrap
```

Or you can use your Jetbrains based IDE to run any tasks (migrate, bootstrap, ...) with `Ctrl+Alt+R` or `⌥ R`.
Here you can type `migrate` and `bootstrap`.

Finally, start the server with

```shell
pipenv run ./manage.py runserver
```

or in your Jetbrains based IDE with the `run` or (preferably) `debug` button.

### Download database from production

Be sure that the database is empty (no migrations or data). If it is not empty just `docker-compose down && docker-compose up -d`.

```shell
ssh root@example.com cat /data/ecs-pgdump/ecs.pgdump.gz | \
  gzip -d | \
  docker exec -i test-ecs pg_restore -U test-ecs -1 --format=custom --schema=public --no-owner --dbname=test-ecs
```

```shell
ssh ecs@example.com cat ./deployment/data/ecs/dump/ecs.pgdump.gz | \
  gzip -d | \
  docker exec -i test-ecs pg_restore -U test-ecs -1 --format=custom --schema=public --no-owner --dbname=test-ecs
```
