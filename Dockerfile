FROM node:24-slim@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9 AS node-runtime

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

LABEL org.opencontainers.image.source="https://github.com/perdiesman/mitchells-ineffable-rules"

# Project-local Prettier and ESLint installations need only the Node runtime.
# Copying that binary avoids a package manager and keeps Git out of the image.
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node

WORKDIR /app
COPY requirements-docker.txt /app/
RUN pip install --no-cache-dir --require-hashes -r requirements-docker.txt

COPY pyproject.toml README.md /app/
COPY mir /app/mir
RUN pip install --no-cache-dir --no-deps .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

ENTRYPOINT ["mir"]
