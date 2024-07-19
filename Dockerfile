# To build the image, run `docker build` command from the root of the
# repository:
#
#    docker build .
#
# An optional LIBOLM_VERSION build argument which sets the
# version of libolm to build against. For example:
#
#    docker build --build-arg LIBOLM_VERSION=3.1.4 .
#

##
## Creating a builder container
##

# We use an initial docker container to build all of the runtime dependencies,
# then transfer those dependencies to the container we're going to ship,
# before throwing this one away
FROM docker.io/python:3.10.14-alpine3.20 as builder

##
## Build libolm for matrix-nio e2e support
##

# Install libolm build dependencies
ARG LIBOLM_VERSION=3.2.10
RUN apk add --no-cache \
    make \
    cmake \
    gcc \
    g++ \
    git \
    libffi-dev \
    yaml-dev \
    python3-dev \
    postgresql-dev \
    musl-dev

# Build libolm
#
# Also build the libolm python bindings and place them at /python-libs
# We will later copy contents from both of these folders to the runtime
# container
COPY docker/build_and_install_libolm.sh /scripts/
RUN /scripts/build_and_install_libolm.sh ${LIBOLM_VERSION} /python-libs

RUN mkdir -p /app

COPY requirements.txt /app

WORKDIR /app

RUN pip install --prefix="/python-libs" --no-warn-script-location -r requirements.txt

##
## Creating the runtime container
##

# Create the container we'll actually ship. We need to copy libolm and any
# python dependencies that we built above to this container
FROM docker.io/python:3.10.14-alpine3.20

# Copy python dependencies from the "builder" container
COPY --from=builder /python-libs /usr/local

# Copy libolm from the "builder" container
COPY --from=builder /usr/local/lib/libolm* /usr/local/lib/

# Install any native runtime dependencies
RUN apk add --no-cache \
    libstdc++ \
    libpq \
    postgresql-dev

WORKDIR /app

# Copy app files
COPY *.py *.md /app/
COPY middleman/ /app/middleman/

CMD python main.py /config/config.yaml
