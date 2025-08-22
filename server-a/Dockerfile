# Use a slim Python image as base
FROM python:3.12-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Create a non-root user and switch to it
RUN adduser --system --group appuser
USER appuser

# Set the working directory
WORKDIR /app

# Install build dependencies (if any, for example, for some python packages)
# Then remove them to keep the image small
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and install dependencies
# This step is separated to leverage Docker cache if dependencies don't change
COPY --chown=appuser:appuser server-a/pyproject.toml .
RUN pip install --no-cache-dir poetry && \
    poetry install --no-root --no-dev && \
    rm -rf ~/.cache/pypoetry

# Copy the application code
COPY --chown=appuser:appuser server-a/app ./app

# Expose the port FastAPI will run on
ARG SERVER_A_PORT=8000
EXPOSE ${SERVER_A_PORT}

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "${SERVER_A_PORT}"]