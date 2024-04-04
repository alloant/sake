# syntax=docker/dockerfile:1.4
FROM python:3.12.1-alpine3.19 AS builder

RUN pip install --upgrade pip
RUN apk add git

EXPOSE 8000

WORKDIR /app

COPY requirements.txt /app
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r requirements.txt

COPY . /app
CMD ["waitress-serve", "--url-scheme=https", "--threads=6", "--port=8000", "--call", "app:create_app"]

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
