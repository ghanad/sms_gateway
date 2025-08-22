#!/bin/sh

# Replace placeholder with actual API URL
envsubst '$$VITE_API_BASE_URL' < /etc/nginx/conf.d/default.conf > /tmp/default.conf && mv /tmp/default.conf /etc/nginx/conf.d/default.conf

exec "$@"