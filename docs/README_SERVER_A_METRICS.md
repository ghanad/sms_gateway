# Server A Prometheus Metrics

This document describes the Prometheus metrics exported by **server-a** via the `/metrics`
endpoint. The endpoint requires HTTP Basic authentication and should be scraped using the
credentials configured through the `METRICS_USERNAME` and `METRICS_PASSWORD` environment
variables.

## Registry

All metrics are registered against a dedicated registry inside `server-a`. This avoids
conflicts with third-party instrumentation and ensures only the metrics defined below are
exposed. The payload is rendered in OpenMetrics text format.

## Metrics Reference

| Metric name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `sms_providers_config_total` | Gauge | _none_ | Number of SMS providers loaded into the in-memory configuration cache. |
| `sms_provider_active` | Gauge | `provider` | Indicates whether a provider is marked as active (`1`) or disabled (`0`). |
| `sms_provider_operational` | Gauge | `provider` | Indicates whether a provider is currently operational (`1`) or unavailable (`0`). |
| `sms_request_rejected_unknown_provider_total` | Counter | `client` | Counts SMS send attempts rejected because the request referenced an unknown provider. |
| `sms_request_rejected_provider_disabled_total` | Counter | `client`, `provider` | Counts SMS send attempts rejected because the selected provider is disabled. |
| `sms_request_rejected_no_provider_available_total` | Counter | `client` | Counts SMS send attempts rejected when no provider is available to accept the request. |
| `sms_config_fingerprint_mismatch_total` | Counter | `kind` | Counts configuration synchronization attempts where the received fingerprint did not match the expected value. |
| `sms_send_requests_total` | Counter | _none_ | Total number of SMS send API requests received. |
| `sms_send_request_latency_seconds` | Histogram | _none_ | Observes the latency of the SMS send API handler in seconds. |
| `sms_send_request_success_total` | Counter | _none_ | Counts SMS send API requests that completed successfully. |
| `sms_send_request_error_total` | Counter | _none_ | Counts SMS send API requests that resulted in an error. |

## Usage Notes

- Provider gauges (`sms_provider_active`, `sms_provider_operational`) are populated during
  application startup based on the cached provider configuration. When the cache changes
  at runtime the same helper can be reused to refresh the metrics.
- Error counters increment at the point where validation rejects an incoming request,
  enabling dashboards to highlight client-side misconfigurations.
- The latency histogram can be used to define SLA objectives for the SMS send endpoint
  by configuring Prometheus histograms or alerting rules in Grafana.

