from prometheus_client import Counter, Gauge

sms_sent_total = Counter("sms_sent_total", "Total SMS successfully sent")
sms_failed_total = Counter("sms_failed_total", "Total SMS failed permanently")
sms_retry_scheduled_total = Counter("sms_retry_scheduled_total", "Total SMS scheduled for retry")
server_a_heartbeat_last_ts = Gauge("server_a_heartbeat_last_ts", "Last heartbeat timestamp from server A")
