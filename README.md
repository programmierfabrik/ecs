# ECS

The ethic commission system (ECS) is an open-source webservice supporting clinical trials approval, monitoring and the electronic management of the related data. See the [ECS Homepage](https://ecs-org.github.io/ecs-docs/) for more information about ECS.


**See the [Administrator Manual](https://ecs-org.github.io/ecs-docs/admin-manual/index.html) for installing and configuring an ECS-Appliance.**


## Development

The devserver requires at least 10GB Harddisk Space and 1,5GB RAM.

Needed packages

```
apt-get install python3 \
    python3-venv \
    python3-pip \
    libxml2-dev \
    libxslt1-dev \
    libpq-dev \
    libmemcached-dev
```

```bash
docker run --rm -p 5432:5432 -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app -e POSTGRES_DB=app postgres:12-alpine
docker run --rm --network host -v $PWD/:/app/ test-ecs

```

```bash
python3 -m venv ./venv
. ./venv/bin/activate
pip install cffi==1.13.2
pip install -r requirements/django2.all
```

## Using the devserver

+ login into devserver and forward port 8000 (django http) to your local machine:
    + `ssh -L 8000:localhost:8000 app@virtual.machine`
    
+ start devserver `sudo systemctl start devserver`
  + once started, the devserver will be available under http://localhost:8000

+ stop devserver: `sudo systemctl stop devserver`
  
+ look into logfile of devserver:
    + show devserver logfile with paging: `sudo journalctl -u devserver`
    + follow the log to see errors or emails: `sudo journalctl -u devserver -f`
    + search for user emails retrospective:
        + `sudo journalctl -u devserver | grep href`
        + `sudo journalctl -u devserver | grep ': Subject' -A 25`
    + grep something in the log: `sudo journalctl -u devserver | grep -i migration`

+ django management:
```
. ~/env/bin/activate
cd ~/ecs
./manage.py
```

### using devupdate.sh 

Features:

+ updates/restarts everything needed for the requested change without intervention
+ allows only one running devupdate at a time, second will abort
+ automatically restores from dump if needed


Usage:

+ **get help**: execute `devupdate.sh`

+ install all app and server dependencies, do not touch sourcecode
    + `devupdate.sh init`

+ fetch changes, checkout last used branch, update server
    + `devupdate.sh pull`

+ fetch changes, force checkout last used branch, restore from dump, update server
    + `devupdate.sh --restore-dump pull --force`

+ fetch changes, checkout to another branch, update server
    + `devupdate.sh pull foobranch`

+ use a empty database with testusers for screencasts
    + change to a different branch if needed: `devupdate.sh pull branchname`
    + clear database, add testuser: `ECS_USERSWITCHER_PARAMETER=-it devupdate.sh freshdb`

+ dump current database, will be saved to /app/ecs.pgdump and will be preferred on restore over default iso dump
    + `devupdate.sh dumpdb`
+ dump current database to a custom filename:
    + `devupdate.sh dumpdb mydump.pgdump`
+ restore from custom dump (use absolute filenames for dumpfilename):
    + `ECS_DUMP_FILENAME=~/mydump.pgdump devupdate.sh --restore-dump init`
+ clone an existing database dump available via ssh into the devserver database
    + `devupdate.sh transferdb root@domain.name cat /data/ecs-pgdump/ecs.pgdump.gz`
+ make a new database dump on a remote machine and transfer this dump via ssh into the devserver database
    + `devupdate.sh transferdb root@domain.name "gosu app /bin/bash -c 'set -o pipefail && pg_dump --encoding=utf-8 --format=custom -Z0 -d ecs | /bin/gzip --rsyncable'"`
+ disable updates, branch switches & database restores
    + `touch /app/devupdate.disabled`
    + to remove this lock: `rm /app/devupdate.disabled`
