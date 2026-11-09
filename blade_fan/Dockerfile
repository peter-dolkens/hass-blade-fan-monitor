# Alpine ships libgpiod v2 and paho-mqtt Python packages, so the image needs no
# pip and no compiler.
ARG BUILD_FROM=alpine:3.24
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-libgpiod py3-paho-mqtt

ARG BUILD_VERSION
ENV BUILD_VERSION=${BUILD_VERSION}

COPY app/ /app/

# Supervisor may build FROM its s6-overlay base, whose /init entrypoint starts
# CMD with a scrubbed environment (no SUPERVISOR_TOKEN -> 401 from core). A
# single-process add-on needs no supervision tree, so run python as PID 1.
ENTRYPOINT []
CMD [ "python3", "-u", "/app/main.py" ]
