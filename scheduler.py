import time
import schedule
import asyncio
from loguru import logger
from consumers.notification_consumer import process_notifications
from kafka_consumer import start_kafka_consumer


class ServiceScheduler:
    """Manages scheduling of various service processors"""

    def __init__(self):
        self.notification_enabled = True
        self.kafka_enabled = True
        self.kafka_thread = None  # Initialize as None since it will hold the actual thread
        self.task1_enabled = True  # Example generic task
        self.task2_enabled = True  # Example generic task

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

    def toggle_notifications(self, enabled: bool):
        """Enable/disable notification processing"""
        self.notification_enabled = enabled
        logger.info(f"Notification processing {'enabled' if enabled else 'disabled'}")

    def toggle_task1(self, enabled: bool):
        """Enable/disable task 1 processing"""
        self.task1_enabled = enabled
        logger.info(f"Task 1 processing {'enabled' if enabled else 'disabled'}")

    def toggle_task2(self, enabled: bool):
        """Enable/disable task 2 processing"""
        self.task2_enabled = enabled
        logger.info(f"Task 2 processing {'enabled' if enabled else 'disabled'}")

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


if __name__ == "__main__":
    scheduler = ServiceScheduler()
    scheduler.start()
