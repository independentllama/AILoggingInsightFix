import logging
from confluent_kafka import Consumer, KafkaError
from config import Config
from error_processor import process_error_log

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def kafka_consumer_thread():
    consumer = Consumer({
        'bootstrap.servers': Config.KAFKA_BOOTSTRAP_SERVERS,
        'group.id': Config.KAFKA_GROUP_ID,
        'auto.offset.reset': 'earliest',
        'security.protocol': 'SASL_PLAINTEXT',
        'sasl.mechanism': 'PLAIN',
        'sasl.username': Config.KAFKA_USERNAME,
        'sasl.password': Config.KAFKA_PASSWORD
    })

    consumer.subscribe([Config.KAFKA_TOPIC_NAME])

    logger.info("Kafka Consumer started successfully.")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.info("End of partition reached.")
                    continue
                else:
                    logger.error(f"Error consuming message: {msg.error()}")
                    break
            error_log = msg.value().decode('utf-8')
            logger.info(f"Received message: {error_log}")
            process_error_log(error_log)
    finally:
        consumer.close()
        logger.info("Kafka Consumer closed.")
