import json, os
from confluent_kafka import Producer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")

producer = Producer({"bootstrap.servers": BOOTSTRAP})


def send(topic: str, value: dict):
    producer.produce(topic, json.dumps(value).encode())
    # fire-and-forget, но для юнит-тестов можно пробрасывать delivery_report
    producer.poll(0)