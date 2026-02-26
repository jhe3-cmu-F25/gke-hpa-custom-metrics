"""
Kafka client wrapper for the Flask web application.
Handles producing messages to request topics and consuming responses
from response topics. Uses correlation IDs to match responses to requests.
"""

import json
import os
import time
import logging
from dotenv import load_dotenv
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

load_dotenv()

logger = logging.getLogger(__name__)


class KafkaClient:
    """
    Thin wrapper around kafka-python's KafkaProducer and KafkaConsumer.
    All config values are read from environment variables (loaded via .env).
    """

    def __init__(self):
        self.broker = os.getenv("KAFKA_BROKER", "localhost:9092")
        self._producer = None  # Lazy-initialised on first use

    # ------------------------------------------------------------------
    # Producer
    # ------------------------------------------------------------------

    def _get_producer(self) -> KafkaProducer:
        """Return a cached KafkaProducer, creating it on first call."""
        if self._producer is None:
            self._producer = KafkaProducer(
                bootstrap_servers=self.broker,
                # Serialise Python dicts to JSON bytes automatically
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                # Retry up to 3 times on transient send errors
                retries=3,
            )
        return self._producer

    def produce(self, topic: str, message: dict) -> None:
        """
        Send *message* (a Python dict) to *topic*.
        Blocks until the broker acknowledges or raises on failure.
        """
        producer = self._get_producer()
        try:
            future = producer.send(topic, value=message)
            # Block until the send completes (or raises)
            record_metadata = future.get(timeout=10)
            logger.info(
                "Produced to %s [partition %d offset %d]",
                record_metadata.topic,
                record_metadata.partition,
                record_metadata.offset,
            )
        except KafkaError as exc:
            logger.error("Failed to produce message to %s: %s", topic, exc)
            raise

    # ------------------------------------------------------------------
    # Consumer
    # ------------------------------------------------------------------

    def consume_one(
        self,
        topic: str,
        correlation_id: str,
        timeout: int = 120,
        group_id: str = "flask-client",
    ) -> dict | None:
        """
        Poll *topic* until a message whose ``correlation_id`` field matches
        the supplied *correlation_id* is found, or *timeout* seconds elapse.

        Returns the parsed response dict on success, or ``None`` on timeout.

        Note: Creates a *new* consumer each time so that we always start
        reading from the latest offset (we only care about the reply to
        *this* request).
        """
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=self.broker,
            # Each request gets its own unique group so it reads from the
            # beginning of its own "window" — we use auto_offset_reset=latest
            # and a fresh group_id so we don't replay old messages.
            group_id=f"{group_id}-{correlation_id}",
            auto_offset_reset="latest",
            enable_auto_commit=True,
            value_deserializer=lambda b: json.loads(b.decode("utf-8")),
            consumer_timeout_ms=1000,  # Poll interval; we loop manually
        )

        deadline = time.time() + timeout
        try:
            while time.time() < deadline:
                # poll() returns a dict of {TopicPartition: [ConsumerRecord]}
                records = consumer.poll(timeout_ms=1000)
                for partition_records in records.values():
                    for record in partition_records:
                        msg = record.value
                        if isinstance(msg, dict) and msg.get("correlation_id") == correlation_id:
                            logger.info(
                                "Received matching response for correlation_id=%s",
                                correlation_id,
                            )
                            return msg
        finally:
            consumer.close()

        logger.warning(
            "Timed out after %ds waiting for correlation_id=%s on topic %s",
            timeout,
            correlation_id,
            topic,
        )
        return None
