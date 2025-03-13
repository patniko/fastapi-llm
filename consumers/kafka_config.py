from dataclasses import dataclass
from loguru import logger
from env import get_settings


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
