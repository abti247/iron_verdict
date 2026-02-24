ARG PYTHON_VERSION=3.14.3
FROM python:${PYTHON_VERSION}-slim AS base

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-privileged user that the app will run under.
# See https://docs.docker.com/go/dockerfile-user-best-practices/
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

# Copy package metadata and source so pip can install the package and its
# dependencies. This layer is cached until pyproject.toml or src/ changes.
COPY pyproject.toml .
COPY src/ src/

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install .

# Create persistent data directory for session snapshots.
RUN mkdir -p /data && chown ${UID}:${UID} /data

# Copy the remaining files into the container.
COPY . .

# Switch to the non-privileged user to run the application.
USER appuser

# Expose the port that the application listens on.
EXPOSE 8000

# Run the application.
CMD ["python", "run.py"]
