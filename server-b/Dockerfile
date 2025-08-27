# Use a slim Python image as base
FROM python:3.12-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN adduser --system --group appuser

# Set the working directory
WORKDIR /app

# Copy requirements.txt and install dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY --chown=appuser:appuser . .

RUN python manage.py collectstatic --noinput

# Switch to the non-root user
USER appuser

# Expose the port Django will run on
EXPOSE 9000

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:9000", "sms_gateway_project.wsgi:application"]
