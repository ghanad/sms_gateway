# Prometheus Metrics Architecture

Server-b exposes Prometheus metrics using the [`prometheus-client`](https://github.com/prometheus/client_python)
library in multi-process mode. Gunicorn web workers, Celery workers, and Celery Beat each
run in their own Docker containers. To aggregate their metrics correctly, the stack uses
a named Docker volume (`prometheus-multiproc`) that is mounted at `/var/run/prometheus`
inside every server-b container. Each process writes its metric samples into that shared
directory. The Django web service cleans this directory on startup to avoid stale gauge
files from previous runs and then serves the combined metrics at `/metrics` by using
`multiprocess.MultiProcessCollector`.

## Adding or Updating Metrics

Follow the steps below whenever you add a new metric or adjust an existing one.

1. **Choose the right module for the metric definition.**
   Define the metric in the module that will update it (or import a shared definition
   from `sms_gateway_project.metrics`). Metrics should be module-level singletons so that
   each process reuses the same object across function calls.

2. **Import the correct class from `prometheus_client`.**
   Use `Counter` for monotonically increasing values, `Gauge` for values that can go up
   and down, `Histogram` for latency/distribution tracking, and `Summary` when you need
   client-side quantiles.

3. **Instantiate the metric once.**
   Provide a descriptive metric name, help text, and optional labels. Example:

   ```python
   from prometheus_client import Counter

   SMS_FAILURES_TOTAL = Counter(
       "sms_failures_total",
       "Total number of SMS send attempts that resulted in a failure.",
       ["provider"],
   )
   ```

4. **Update the metric where the event occurs.**
   Call the appropriate method (`.inc()`, `.dec()`, `.observe(value)`, etc.) inside the
   business logic. For multi-process mode no special handling is required; the shared
   volume and the `PROMETHEUS_MULTIPROC_DIR` environment variable are already configured
   for you in Docker Compose.

5. **Expose new metrics automatically.**
   The `/metrics` endpoint aggregates every metric registered in the default Prometheus
   registry, so no extra wiring is required. Simply restart the affected containers and
   scrape `/metrics` to verify the output.

6. **Keep tests up to date.**
   When adding important metrics, consider writing or updating tests to ensure the metric
   is incremented or observed as expected.

7. **Document special behaviour.**
   If a metric has non-obvious semantics (custom labels, reset logic, etc.), add a comment
   near its definition or update this document to guide future contributors.

