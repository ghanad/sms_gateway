# Server B

Processing backend for SMS Gateway. Consumes messages from RabbitMQ, applies provider policies, sends SMS via provider adapters, exposes webhook and status endpoints, and tracks metrics.

## Configuration

Set the `ALLOWED_ORIGINS` environment variable in a `.env` file to specify which web origins are permitted to access the API.
The value should be a comma-separated list of origins, for example:

```
ALLOWED_ORIGINS=http://localhost:5173
```
