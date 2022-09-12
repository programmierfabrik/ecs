# ECS

The ethic commission system (ECS) is an open-source webservice supporting clinical trials approval, monitoring and the
electronic management of the related data. See the [ECS Homepage](https://ecs-org.github.io/ecs-docs/) for more
information about ECS.

## Development

### Required packages

Ubuntu 22.04:

```
gettext
libmemcached-dev
```

MacOS (incomplete):

```
gettext
libmemcached
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


## TODO:

* Sanitize read / write only pdfs in python only
* Barcode on every pdf page when generating a pdf
