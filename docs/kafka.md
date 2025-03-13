# Kafka Integration Documentation

This document provides an overview of the Kafka integration used in the FastAPI Template.

## Overview

The application uses Kafka as a message broker for asynchronous processing. Kafka is used for:

- Processing notifications
- Handling background tasks
- Implementing event-driven architecture

## Kafka Configuration

The Kafka configuration is defined in `consumers/kafka_config.py`:

```python
@dataclass
class KafkaConfig:
    """Kafka consumer configuration"""
    bootstrap_servers: str
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = True
    group_id: str = "fastapi_template_group"
    api_version: tuple = (2, 5, 0)


def get_default_config() -> KafkaConfig:
    """Get default Kafka configuration from environment settings"""
    try:
        settings = get_settings()
        
        # Get Kafka server from settings
        kafka_server = settings.kafka_server()
        if not kafka_server:
            logger.warning("Kafka server not configured, using localhost:9092")
            kafka_server = "localhost:9092"
            
        return KafkaConfig(
            bootstrap_servers=kafka_server,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            group_id="fastapi_template_group",
            api_version=(2, 5, 0),
        )
    except Exception as e:
        logger.error(f"Error getting Kafka config: {str(e)}")
        # Fallback to localhost
        return KafkaConfig(
            bootstrap_servers="localhost:9092",
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            group_id="fastapi_template_group",
            api_version=(2, 5, 0),
        )
```

## Kafka Consumer Framework

The Kafka consumer framework is implemented in `kafka_consumer.py`. It provides a robust way to consume messages from Kafka topics with error handling, retries, and batch processing.

### Creating a Kafka Consumer

```python
def create_kafka_consumer(
    topics: list[str], config: Optional[dict] = None, max_retries: int = 5
) -> Optional[KafkaConsumer]:
    """Create a Kafka consumer for the specified topics with retry mechanism"""
    kafka_config = config or get_default_config()
    retry_count = 0
    while retry_count < max_retries:
        try:
            logger.debug(
                f"Attempting to create Kafka consumer for topics: {topics} (attempt {retry_count + 1}/{max_retries})"
            )
            consumer = KafkaConsumer(
                *topics,
                bootstrap_servers=kafka_config.bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset=kafka_config.auto_offset_reset,
                enable_auto_commit=kafka_config.enable_auto_commit,
                group_id=kafka_config.group_id,
                api_version=kafka_config.api_version,
                # Add connection timeout to prevent hanging
                session_timeout_ms=6000,
                request_timeout_ms=10000,
            )
            # Test the connection
            consumer.topics()
            logger.info("Successfully created Kafka consumer")
            return consumer
        except Exception as e:
            retry_count += 1
            if retry_count == max_retries:
                logger.error(
                    f"Failed to create Kafka consumer after {max_retries} attempts: {str(e)}"
                )
                return None
            wait_time = min(
                2**retry_count, 30
            )  # Exponential backoff capped at 30 seconds
            logger.warning(
                f"Failed to create Kafka consumer (attempt {retry_count}/{max_retries}). Retrying in {wait_time} seconds..."
            )
            import time

            time.sleep(wait_time)
```

### Consuming Messages

```python
async def consume_messages(consumer: KafkaConsumer) -> None:
    """Consume and batch process messages from Kafka"""
    if not consumer:
        logger.error("No consumer provided")
        return

    # Wait for initial connection
    try:
        consumer.topics()
        logger.debug("Initial Kafka connection successful")
    except Exception as e:
        logger.error(f"Failed to establish initial Kafka connection: {str(e)}")
        return

    BATCH_SIZE = 25  # Process messages in smaller batches
    BATCH_TIMEOUT = 5  # Wait up to 5 seconds to collect messages

    logger.debug("Starting to consume messages")
    while True:
        try:
            # Poll for a batch of messages
            message_batch = []
            start_time = datetime.now()

            while (
                len(message_batch) < BATCH_SIZE
                and (datetime.now() - start_time).seconds < BATCH_TIMEOUT
            ):
                messages = consumer.poll(timeout_ms=1000)
                if not messages:
                    continue

                for topic_partition, records in messages.items():
                    for record in records:
                        message_batch.append(
                            Message(topic=record.topic, value=record.value)
                        )
                        if len(message_batch) >= BATCH_SIZE:
                            break
                    if len(message_batch) >= BATCH_SIZE:
                        break

            if not message_batch:
                await asyncio.sleep(1)  # Prevent tight polling loop
                continue

            # Process the batch of messages
            await process_message_batch(message_batch)
            logger.debug(f"Successfully processed batch of {len(message_batch)} messages")

        except Exception as e:
            logger.error(f"Consumer error: {str(e)}")
            await asyncio.sleep(1)  # Prevent tight error loop
            continue
```

### Processing Messages

```python
async def process_message_batch(messages: List[Message]) -> None:
    """Route messages to appropriate processors"""
    for message in messages:
        try:
            logger.debug(f"Processing message from batch: {message.topic} - {message.value}")

            # Example message routing based on topic
            if message.topic == "notifications":
                # Process notification messages
                user_id = message.value.get("user_id")
                event = message.value.get("event")
                content = message.value.get("content")
                
                if all([user_id, event, content]):
                    # Call your notification processor here
                    await process_notifications()
                else:
                    logger.error("Missing required fields in notification message")
                continue
                
            # Add more topic handlers here as needed
            if message.topic == "generic_topic":
                # Process generic topic messages
                # Implement your generic topic handler here
                logger.debug(f"Processing generic topic message: {message.value}")
                continue

            # Default case for unhandled topics
            logger.warning(f"Unhandled message topic: {message.topic}")

        except Exception as e:
            logger.error(f"Error processing message in batch: {str(e)}")
            continue
```

### Starting the Kafka Consumer

```python
def start_kafka_consumer() -> Optional[Thread]:
    """Start a Kafka consumer in a separate thread"""

    def run_consumer():
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            logger.debug("Starting Kafka consumer")
            consumer = create_kafka_consumer(
                [
                    "notifications",
                    "generic_topic",
                    # Add more topics as needed
                ]
            )
            if not consumer:
                logger.error("Failed to create consumer")
                return

            try:
                loop.run_until_complete(consume_messages(consumer))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in consumer thread: {str(e)}")

    try:
        consumer_thread = Thread(target=run_consumer, daemon=True)
        consumer_thread.start()
        logger.debug("Kafka consumer thread started")
        return consumer_thread
    except Exception as e:
        logger.error(f"Failed to start consumer thread: {str(e)}")
        return None
```

## Notification Consumer

The notification consumer is implemented in `consumers/notification_consumer.py`. It processes notification messages from Kafka and sends them to users.

```python
async def process_notifications():
    """
    Process pending notifications.
    This is a generic implementation that can be customized based on your needs.
    """
    try:
        db = SessionLocal()
        try:
            # Get unsent notifications
            notifications = (
                db.query(Notification)
                .filter(Notification.sent_status == False)  # noqa
                .order_by(Notification.created_at.asc())
                .limit(100)
                .all()
            )

            if not notifications:
                logger.debug("No pending notifications to process")
                return

            logger.info(f"Processing {len(notifications)} pending notifications")

            # Process each notification
            for notification in notifications:
                try:
                    # Here you would implement your notification delivery logic
                    # For example, sending push notifications, emails, etc.
                    
                    # This is a placeholder for actual notification delivery
                    logger.info(
                        f"Sending notification {notification.id} to users {notification.users}: "
                        f"{notification.event} - {notification.message}"
                    )
                    
                    # Simulate successful delivery
                    notification.sent_status = True
                    db.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing notification {notification.id}: {str(e)}")
                    db.rollback()
                    continue

            logger.info("Notification processing completed")

        except Exception as e:
            logger.error(f"Error in notification processing: {str(e)}")
            db.rollback()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Critical error in notification processing: {str(e)}")
```

## Integration with Scheduler

The Kafka consumer is started by the scheduler in `scheduler.py`:

```python
def start(self):
    """Start the scheduler with all processors"""
    try:
        logger.info("Starting service scheduler")

        # Start Kafka consumer if enabled with retry mechanism
        if self.kafka_enabled:
            logger.debug("Attempting to start Kafka consumer...")
            if not self.toggle_kafka(True):  # This includes the retry mechanism
                raise Exception("Failed to start Kafka consumer after maximum retries")

        # Schedule notification processing every 30 seconds
        schedule.every(30).seconds.do(self.run_process_notifications)

        # Schedule generic tasks
        schedule.every(5).minutes.do(self.run_task1)
        schedule.every(15).minutes.do(self.run_task2)

        logger.info("All tasks scheduled successfully")

        # Initial health check
        if self.kafka_enabled and (not self.kafka_thread or not self.kafka_thread.is_alive()):
            raise Exception("Kafka consumer thread died during startup")

        while True:
            try:
                # Periodic health check
                if self.kafka_enabled and (not self.kafka_thread or not self.kafka_thread.is_alive()):
                    raise Exception("Kafka consumer thread died")

                schedule.run_pending()
                time.sleep(5)  # Reduced polling frequency
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                # Only sleep on transient errors, re-raise critical ones
                if "Kafka consumer thread died" in str(e):
                    raise
                time.sleep(5)  # Prevent tight error loop
    except Exception as e:
        logger.error(f"Critical error in scheduler: {str(e)}")
        raise  # Re-raise the exception to notify the parent thread
```

## Docker Setup

The Kafka service is defined in `docker-compose.yml`:

```yaml
kafka:
    image: confluentinc/cp-kafka:7.5.0
    hostname: kafka
    container_name: kafka
    ports:
        - 9092:9092
    environment:
        KAFKA_BROKER_ID: 1
        KAFKA_NODE_ID: 1
        KAFKA_PROCESS_ROLES: 'broker,controller'
        KAFKA_CONTROLLER_QUORUM_VOTERS: '1@kafka:29093'
        KAFKA_LISTENERS: 'PLAINTEXT://0.0.0.0:9092,CONTROLLER://kafka:29093'
        KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://localhost:9092'
        KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT'
        KAFKA_INTER_BROKER_LISTENER_NAME: 'PLAINTEXT'
        KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
        KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
        KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
        KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
        KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
        KAFKA_AUTO_CREATE_TOPICS_ENABLE: 'true'
        KAFKA_LOG_DIRS: '/var/lib/kafka/data'
        KAFKA_LOG_RETENTION_HOURS: 168
        KAFKA_NUM_PARTITIONS: 1
    volumes:
        - kafka-data:/var/lib/kafka/data
    networks:
        - fastapi-net
    command: |
        bash -c '
        echo "Generating cluster ID..."
        CLUSTER_ID=$$(/bin/kafka-storage random-uuid)
        echo "Generated Cluster ID: $$CLUSTER_ID"
        echo "Formatting storage..."
        /bin/kafka-storage format -t $$CLUSTER_ID -c /etc/kafka/kraft/server.properties
        echo "Starting Kafka..."
        exec /etc/confluent/docker/run
        '
```

## Adding a New Kafka Consumer

To add a new Kafka consumer:

1. Create a new file in the `consumers/` directory
2. Implement your consumer logic
3. Add the topic to the list of topics in `kafka_consumer.py`
4. Add the message processing logic to `process_message_batch` in `kafka_consumer.py`

Example:

```python
# consumers/my_consumer.py
async def process_my_messages(data):
    """Process my messages"""
    try:
        # Implement your message processing logic here
        logger.info(f"Processing my message: {data}")
        # ...
    except Exception as e:
        logger.error(f"Error processing my message: {str(e)}")
```

Then in `kafka_consumer.py`:

```python
from consumers.my_consumer import process_my_messages

# ...

async def process_message_batch(messages: List[Message]) -> None:
    """Route messages to appropriate processors"""
    for message in messages:
        try:
            # ...
            
            # Add your new topic handler
            if message.topic == "my_topic":
                # Process my topic messages
                data = message.value.get("data")
                if data:
                    await process_my_messages(data)
                else:
                    logger.error("Missing data in my topic message")
                continue
                
            # ...
        except Exception as e:
            logger.error(f"Error processing message in batch: {str(e)}")
            continue
```

And update the list of topics in `start_kafka_consumer`:

```python
consumer = create_kafka_consumer(
    [
        "notifications",
        "generic_topic",
        "my_topic",  # Add your new topic
    ]
)
