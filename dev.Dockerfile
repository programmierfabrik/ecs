from ubuntu:xenial

RUN apt-get update -y

RUN apt-get install -y python3 \
    python3-venv \
    python3-pip \
    libxml2-dev \
    libxslt1-dev \
    libpq-dev \
    libmemcached-dev \
    gettext \
    libpango1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    ghostscript \
    pdftk

COPY ./requirements/django2.all /django2.all

RUN pip3 install cffi==1.13.2 && \
    (pip3 install -r /django2.all || pip3 install -r /django2.all)

RUN apt-get update && apt-get install -y locales && rm -rf /var/lib/apt/lists/* \
    && localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8

ENV LANG en_US.UTF-8

COPY ./docker-entrypoint.sh /docker-entrypoint.sh

WORKDIR /app

EXPOSE 8000

ENV DATABASE_URL=postgres://app:app@localhost:5432/app

RUN ln -s /usr/bin/python3 /usr/bin/python || true

ENV LANG='en_US.UTF-8'
ENV LC_ALL='en_US.UTF-8'

USER 1000

ENTRYPOINT [ "/docker-entrypoint.sh" ]
