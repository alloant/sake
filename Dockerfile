# syntax=docker/dockerfile:1.4
FROM python:3.13.2-alpine3.21 AS builder

RUN pip install --upgrade pip
RUN apk add git

WORKDIR /app

COPY requirements.txt /app
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r requirements.txt

COPY . /app
CMD ["/bin/bash","-c","python websocket_server.py; gunicorn -w 5 --threads 100 -b :8000 'app:create_app()'"]

FROM builder as dev-envs

RUN <<EOF
apk update
apk add git
EOF

RUN <<EOF
addgroup -S docker
adduser -S --shell /bin/bash --ingroup docker vscode
EOF
# install Docker tools (cli, buildx, compose)
COPY --from=gloursdocker/docker / /
