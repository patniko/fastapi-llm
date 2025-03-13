# Scheduler Documentation

This document provides an overview of the scheduler system used in the FastAPI Template.

## Overview

The scheduler is responsible for running periodic tasks in the background. It uses the `schedule` library to schedule tasks at specific intervals and runs them in a separate thread.

## Scheduler Implementation

The scheduler is implemented in `scheduler.py`. It provides a `ServiceScheduler` class that manages the scheduling of various service processors.

```python
class ServiceScheduler:
    """Manages scheduling of various service processors"""

    def __init__(self):
        self.notification_enabled = True
        self.kafka_enabled = True
        self.kafka_thread = None  # Initialize as None since it will hold the actual thread
        self.task1_enabled = True  # Example generic task
        self.task2_enabled = True  # Example generic task
```

## Task Execution

The scheduler executes tasks at specified intervals. Each task is defined as a method in the `ServiceScheduler` class.

### Notification Processing

```python
def run_process_notifications(self):
    """Sync wrapper for async process_notifications"""
    if not self.notification_enabled:
        logger.debug("Notification processing is disabled")
        return

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_notifications())
    except Exception as e:
        logger.error(f"Error in notification processing: {str(e)}")
    finally:
        loop.close()
```

### Generic Tasks

```python
def run_task1(self):
    """Run generic task 1 if enabled"""
    if not self.task1_enabled:
        logger.debug("Task 1 processing is disabled")
        return

    try:
        # Placeholder for task 1 implementation
        logger.debug("Running task 1")
        # Implement your task 1 logic here
    except Exception as e:
        logger.error(f"Error in task 1 processing: {str(e)}")

def run_task2(self):
    """Run generic task 2 if enabled"""
    if not self.task2_enabled:
        logger.debug("Task 2 processing is disabled")
        return

    try:
        # Placeholder for task 2 implementation
        logger.debug("Running task 2")
        # Implement your task 2 logic here
    except Exception as e:
        logger.error(f"Error in task 2 processing: {str(e)}")
```

## Kafka Integration

The scheduler also manages the Kafka consumer thread:

```python
def toggle_kafka(self, enabled: bool, max_retries: int = 3) -> bool:
    """Enable/disable Kafka consumer with retry mechanism"""
    self.kafka_enabled = enabled
    if enabled and not self.kafka_thread:
        retry_count = 0
        while retry_count < max_retries:
            self.kafka_thread = start_kafka_consumer()
            if self.kafka_thread:
                logger.info("Kafka consumer started successfully")
                return True
            retry_count += 1
            if retry_count < max_retries:
                wait_time = min(2**retry_count, 30)  # Exponential backoff capped at 30 seconds
                logger.warning(
                    f"Failed to start Kafka consumer (attempt {retry_count}/{max_retries}). "
                    f"Retrying in {wait_time} seconds..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to start Kafka consumer after {max_retries} attempts")
        return False
    elif not enabled and self.kafka_thread:
        # Note: This will gracefully stop on next iteration
        self.kafka_thread = None
        logger.info("Kafka consumer will stop on next iteration")
        return True
    return True  # Already in desired state
```

## Starting the Scheduler

The scheduler is started in the `start` method:

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

## Integration with FastAPI

The scheduler is started when the FastAPI application starts up. This is done in the `lifespan` function in `server.py`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    run_scheduler_thread()
    yield
    # Shutdown (if needed)
    pass


def run_scheduler_thread():
    scheduler = ServiceScheduler()
    scheduler_thread = threading.Thread(target=scheduler.start, daemon=True)
    scheduler_thread.start()
```

## Adding a New Scheduled Task

To add a new scheduled task:

1. Add a new method to the `ServiceScheduler` class
2. Add a toggle method to enable/disable the task
3. Schedule the task in the `start` method

Example:

```python
def run_my_task(self):
    """Run my task if enabled"""
    if not self.my_task_enabled:
        logger.debug("My task processing is disabled")
        return

    try:
        # Implement your task logic here
        logger.debug("Running my task")
        # ...
    except Exception as e:
        logger.error(f"Error in my task processing: {str(e)}")

def toggle_my_task(self, enabled: bool):
    """Enable/disable my task processing"""
    self.my_task_enabled = enabled
    logger.info(f"My task processing {'enabled' if enabled else 'disabled'}")
```

Then add it to the `__init__` method:

```python
def __init__(self):
    self.notification_enabled = True
    self.kafka_enabled = True
    self.kafka_thread = None
    self.task1_enabled = True
    self.task2_enabled = True
    self.my_task_enabled = True  # Add your task toggle
```

And schedule it in the `start` method:

```python
# Schedule notification processing every 30 seconds
schedule.every(30).seconds.do(self.run_process_notifications)

# Schedule generic tasks
schedule.every(5).minutes.do(self.run_task1)
schedule.every(15).minutes.do(self.run_task2)

# Schedule your task
schedule.every(10).minutes.do(self.run_my_task)
```

## Best Practices

When implementing scheduled tasks, follow these best practices:

1. **Error Handling**: Use try-except blocks to catch and handle errors appropriately.
2. **Logging**: Use the logger to log important events and errors.
3. **Database Sessions**: Create a new database session for each task and close it when done.
4. **Async Support**: Use asyncio for async tasks.
5. **Task Isolation**: Each task should be isolated from others to prevent one task's failure from affecting others.
6. **Health Checks**: Implement health checks to ensure tasks are running correctly.
7. **Graceful Shutdown**: Implement graceful shutdown to ensure tasks are completed before the application shuts down.
