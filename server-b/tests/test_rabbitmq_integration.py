"""Integration tests against a real RabbitMQ broker."""

import os
import shutil
import socket
import subprocess
import time
import uuid

import pika
from django.test import SimpleTestCase


INTEGRATION_ENV = "ENABLE_RABBITMQ_INTEGRATION_TESTS"


def _docker_integration_enabled() -> bool:
    return shutil.which("docker") is not None and os.environ.get(INTEGRATION_ENV) == "1"


if _docker_integration_enabled():  # pragma: no cover - optional integration path

    class RabbitMQIntegrationTests(SimpleTestCase):
        """Exercise queue behaviour using a Docker-backed RabbitMQ instance."""

        host = "localhost"
        port = int(os.environ.get("RABBITMQ_TEST_PORT", "5672"))
        container_name = f"smsgw-rabbit-test-{uuid.uuid4().hex[:8]}"

        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--rm",
                    "--name",
                    cls.container_name,
                    "-p",
                    f"{cls.port}:5672",
                    "rabbitmq:3-alpine",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            cls._wait_for_port()

        @classmethod
        def tearDownClass(cls):
            try:
                subprocess.run(
                    ["docker", "rm", "-f", cls.container_name],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            finally:
                super().tearDownClass()

        @classmethod
        def _wait_for_port(cls, timeout: float = 30.0) -> None:
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    with socket.create_connection((cls.host, cls.port), timeout=1):
                        return
                except OSError:
                    time.sleep(0.5)
            raise RuntimeError("RabbitMQ did not become ready in time")

        def _open_channel(self):
            credentials = pika.PlainCredentials("guest", "guest")
            params = pika.ConnectionParameters(host=self.host, port=self.port, credentials=credentials)
            connection = pika.BlockingConnection(params)
            return connection, connection.channel()

        def test_dlx_routing_to_permanent_dlq(self):
            connection, channel = self._open_channel()
            try:
                channel.queue_declare(queue="sms_permanent_dlq", durable=True)
                channel.queue_purge("sms_permanent_dlq")
                channel.queue_declare(
                    queue="sms_outbound_queue",
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": "",
                        "x-dead-letter-routing-key": "sms_permanent_dlq",
                    },
                )
                channel.queue_purge("sms_outbound_queue")

                body = b"integration-dlx"
                channel.basic_publish(
                    exchange="",
                    routing_key="sms_outbound_queue",
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                method, properties, _ = channel.basic_get("sms_outbound_queue", auto_ack=False)
                self.assertIsNotNone(method)
                channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)

                deadline = time.time() + 5
                dlq_body = None
                while time.time() < deadline:
                    dlq_method, _, dlq_payload = channel.basic_get("sms_permanent_dlq", auto_ack=True)
                    if dlq_method:
                        dlq_body = dlq_payload
                        break
                    time.sleep(0.5)

                self.assertEqual(dlq_body, body)
            finally:
                connection.close()

        def test_wait_queue_ttl_requeues(self):
            connection, channel = self._open_channel()
            try:
                channel.queue_declare(queue="sms_outbound_queue", durable=True)
                channel.queue_purge("sms_outbound_queue")
                channel.queue_declare(
                    queue="sms_retry_wait_queue",
                    durable=True,
                    arguments={
                        "x-message-ttl": 1000,
                        "x-dead-letter-exchange": "",
                        "x-dead-letter-routing-key": "sms_outbound_queue",
                    },
                )
                channel.queue_purge("sms_retry_wait_queue")

                channel.basic_publish(
                    exchange="",
                    routing_key="sms_retry_wait_queue",
                    body=b"wait-queue-test",
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        headers={"x-retry-count": 2, "retry_count": 2},
                    ),
                )

                time.sleep(1.5)
                method, header, body = channel.basic_get("sms_outbound_queue", auto_ack=True)
                self.assertIsNotNone(method)
                self.assertEqual(body, b"wait-queue-test")
                self.assertEqual(header.headers.get("x-retry-count"), 2)
            finally:
                connection.close()

        def test_persistent_message_survives_restart(self):
            connection, channel = self._open_channel()
            try:
                channel.queue_declare(queue="sms_persistence_test", durable=True)
                channel.queue_purge("sms_persistence_test")
                channel.basic_publish(
                    exchange="",
                    routing_key="sms_persistence_test",
                    body=b"persist-me",
                    properties=pika.BasicProperties(delivery_mode=2),
                )
            finally:
                connection.close()

            subprocess.run(
                ["docker", "restart", self.container_name],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._wait_for_port()

            connection, channel = self._open_channel()
            try:
                method, _, body = channel.basic_get("sms_persistence_test", auto_ack=True)
                self.assertIsNotNone(method)
                self.assertEqual(body, b"persist-me")
            finally:
                connection.close()

else:

    class RabbitMQIntegrationTests(SimpleTestCase):  # pragma: no cover - skipped by default
        def test_integration_skipped(self):
            self.skipTest(
                "Set ENABLE_RABBITMQ_INTEGRATION_TESTS=1 and install Docker to run RabbitMQ integration tests."
            )

