FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG BUILD_TIME='unknown'

# Global environment variables
ENV BUILD_TIME=${BUILD_TIME}

# Install dependencies
RUN apt-get update -y && \
    apt-get install -y \
    # python dependencies
    python3 python3-pip \
    # ecs dependencies
    gettext libmemcached-dev \
    && rm -rf /var/lib/apt/lists/*

# Install pipenv
RUN pip install --no-cache-dir pipenv

# Create ecs user with uid 1000
RUN useradd ecs -m -u 1000
RUN mkdir /opt/ecs && chown ecs:ecs /opt/ecs

# Change to user ecs
USER ecs
WORKDIR /opt/ecs

# Copy pip files and install
COPY --chown=ecs Pipfile Pipfile.lock ./
RUN pipenv install --deploy --ignore-pipfile

# Copy rest of code
COPY --chown=ecs . .

# Compile the messages
RUN pipenv run ./manage.py compilemessages

# Create folders that will be mounted via volumes. We have problems with permission, as docker uses the root account for volumes and we use ecs (1000)
RUN mkdir /opt/ecs/data /opt/ecs/volatile

EXPOSE 8000

ENTRYPOINT ["/opt/ecs/docker-entrypoint.sh"]
