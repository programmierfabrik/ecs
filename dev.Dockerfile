from ubuntu:xenial

RUN apt-get update -y

RUN apt-get install -y python3 \
    python3-venv \
    python3-pip \
    libxml2-dev \
    libxslt1-dev \
    libpq-dev \
    libmemcached-dev \
    gettext

COPY ./requirements/django2.all /django2.all

RUN pip3 install cffi==1.13.2 && \
    (pip3 install -r /django2.all || pip3 install -r /django2.all)

COPY ./docker-entrypoint.sh /docker-entrypoint.sh

WORKDIR /app

EXPOSE 8000

ENV DATABASE_URL=postgres://app:app@localhost:5432/app

ENTRYPOINT [ "/docker-entrypoint.sh" ]
