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
COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --ignore-pipfile

# Copy rest of code
COPY . .

#./manage.py compilemessages && \
#./manage.py collectstatic --noinput

EXPOSE 8000

ENTRYPOINT ["/opt/ecs/docker-entrypoint.sh"]
