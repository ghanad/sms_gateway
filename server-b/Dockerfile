# =================
#  Stage 1: Builder
# =================
# This stage installs build dependencies and Python packages into a virtual environment.
FROM python:3.12-slim-bookworm AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Define a build-time argument for the apt mirror
ARG APT_MIRROR=""

# Install build-time dependencies needed for compiling packages
RUN \
    if [ -n "$APT_MIRROR" ]; then \
        echo "deb $APT_MIRROR bookworm main" > /etc/apt/sources.list && \
        echo "deb $APT_MIRROR bookworm-updates main" >> /etc/apt/sources.list; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Create the virtual environment
RUN python -m venv $VIRTUAL_ENV

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# =================
#  Stage 2: Final Image
# =================
# This stage creates the lean final image for running the Django application.
FROM python:3.12-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Create a non-root user for security
RUN adduser --system --group appuser

# Set the working directory
WORKDIR /app

# --- START: Permission Fix ---
# Change the ownership of the work directory to the non-root user.
# This must be done BEFORE switching the user.
RUN chown appuser:appuser /app
# --- END: Permission Fix ---

# Switch to the non-root user
USER appuser

# Copy the virtual environment from the builder stage
COPY --from=builder $VIRTUAL_ENV $VIRTUAL_ENV

# Copy the application code. Since we are already 'appuser',
# the files will be owned by 'appuser' automatically.
COPY . .

# Run collectstatic as the non-root user
RUN python manage.py collectstatic --noinput

# Expose the port Django will run on
EXPOSE 9000

# The CMD is defined in the docker-compose.yml, but this is a good default
CMD ["gunicorn", "--bind", "0.0.0.0:9000", "sms_gateway_project.wsgi:application"]