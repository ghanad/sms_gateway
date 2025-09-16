# =================
#  Stage 1: Builder
# =================
# This stage installs build dependencies and Python packages into a virtual environment.
FROM python:3.12-slim-bookworm AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# Create a virtual environment to keep dependencies isolated
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install build-time dependencies needed to compile some Python packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Create the virtual environment
RUN python -m venv $VIRTUAL_ENV

# Copy only the requirements file first to leverage Docker cache
COPY requirements.txt .
# Install Python dependencies into the virtual environment
RUN pip install --no-cache-dir -r requirements.txt


# =================
#  Stage 2: Final Image
# =================
# This stage creates the lean final image for running the application.
FROM python:3.12-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Create a non-root user for security
RUN adduser --system --group appuser
WORKDIR /app

# Copy the virtual environment with all installed packages from the builder stage
COPY --from=builder $VIRTUAL_ENV $VIRTUAL_ENV

# Copy the application code
COPY --chown=appuser:appuser app ./app

# Switch to the non-root user
USER appuser

# Expose the port FastAPI will run on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]