# Server B

Processing backend for SMS Gateway. Consumes messages from RabbitMQ, applies provider policies, sends SMS via provider adapters, exposes webhook and status endpoints, and tracks metrics.
