# FastAPI Template

## Architecture

This FastAPI Template is built with a modern, scalable architecture consisting of several key components:

- **FastAPI Application**: Core REST API server with CORS middleware
- **Service Layer**: Modular services for different domain functionalities (users, items, notifications, etc.)
- **Background Processing**: Service scheduler managing periodic tasks and Kafka consumers
- **Event Processing**: Kafka-based message broker for asynchronous operations
- **Database**: PostgreSQL for persistent storage, Redis for caching and session management
- **External Integrations**: Webhook support for third-party services
- **Authentication**: JWT-based authentication with refresh tokens

## Features

- **User Authentication**: Complete authentication system with JWT tokens and refresh tokens
- **Database Integration**: SQLAlchemy ORM with PostgreSQL
- **Caching**: Redis integration for caching
- **Background Tasks**: Scheduler for running periodic tasks
- **Asynchronous Processing**: Kafka integration for message processing
- **Notifications**: Notification system for sending messages to users
- **Webhooks**: Webhook system for integrating with external services
- **LLM Integration**: Anthropic Claude integration for AI capabilities
- **Docker Support**: Docker Compose setup for local development

## Developer Setup

### Development dependencies
- Python v3.11+
- Docker
- Docker Compose
- VS Code (recommended)
- Poetry v1.8.4

## Deployment
### Prod
The application can be deployed using Platform.sh or any other cloud provider that supports Python applications.

## Setup
Before you run the service, you will need to set up environment variables.

```bash
# Set environment variable to run in dev
echo "FASTAPI_ENV=dev" >> ~/.zshrc

# Setup python 3.11 environment
brew install poetry

# Install dependencies
poetry install

# Run the application
make app-run
```

## Run Application
This will run the application and spin up the needed docker containers
```shell
make app-run
```

## Run Docker Containers
```shell
make docker-up # spin up all docker containers and run the migration scripts

make docker-down # spin docker containers down
```

### Testing
You can run tests using the following command:
```shell
make app-test
```

## Migration Commands
```shell
make migration-run # Runs the migrations against the db
make migration-new m="foo" # Creates a new migration script
```

## Project Structure

```
.
├── alembic/                  # Database migrations
├── consumers/                # Kafka consumers
│   ├── __init__.py
│   ├── kafka_config.py       # Kafka configuration
│   └── notification_consumer.py  # Notification consumer
├── services/                 # Service modules
│   ├── items.py              # Item service
│   ├── notifications.py      # Notification service
│   ├── users.py              # User service
│   └── webhooks.py           # Webhook service
├── static/                   # Static files
├── alembic.ini               # Alembic configuration
├── auth.py                   # Authentication utilities
├── db.py                     # Database configuration
├── docker-compose.yml        # Docker Compose configuration
├── env.py                    # Environment configuration
├── kafka_consumer.py         # Kafka consumer framework
├── kafka_utils.py            # Kafka utilities
├── llm.py                    # LLM integration
├── Makefile                  # Makefile for common commands
├── memcache.py               # Redis cache utilities
├── models.py                 # Database models
├── pyproject.toml            # Poetry configuration
├── README.md                 # This file
├── scheduler.py              # Background task scheduler
└── server.py                 # Main FastAPI application
```

## Extending the Template

### Adding a New Service

1. Create a new file in the `services/` directory
2. Define a FastAPI router and endpoints
3. Add the router to `server.py`

Example:

```python
# services/my_service.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import validate_jwt
from db import get_db

router = APIRouter()

@router.get("/")
async def get_my_data(db: Session = Depends(get_db), user: dict = Depends(validate_jwt)):
    # Implement your service logic here
    return {"message": "Hello from my service!"}
```

Then add to `server.py`:

```python
from services.my_service import router as my_service_router

# ...

app.include_router(my_service_router, prefix="/my-service", tags=["my-service"])
```

### Adding a New Kafka Consumer

1. Create a new file in the `consumers/` directory
2. Implement your consumer logic
3. Add the topic to `kafka_consumer.py`

### Adding a New Scheduled Task

1. Add a new method to the `ServiceScheduler` class in `scheduler.py`
2. Schedule the task in the `start` method

## Environment Variables

The application uses environment variables for configuration. You can set these in a `.env.dev` file for development.

Required variables:

- `FASTAPI_ENV`: Environment (dev, prod)
- `SQL_HOST`: PostgreSQL host
- `SQL_PORT`: PostgreSQL port
- `SQL_USER`: PostgreSQL user
- `SQL_PASSWORD`: PostgreSQL password
- `SQL_DATABASE`: PostgreSQL database
- `REDIS_HOST`: Redis host
- `REDIS_PORT`: Redis port
- `KAFKA_HOST`: Kafka host
- `KAFKA_PORT`: Kafka port
- `AUTH_SECRET_KEY`: Secret key for JWT tokens
- `AUTH_ALGORITHM`: Algorithm for JWT tokens (e.g., HS256)
- `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`: JWT token expiration in minutes

Optional variables:

- `ANTHROPIC_API_KEY`: Anthropic API key for LLM integration
