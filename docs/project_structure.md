# Project Structure

This document provides an overview of the FastAPI Template project structure to help LLMs and developers quickly understand the codebase.

## Directory Structure

```
.
├── alembic/                  # Database migrations
│   ├── versions/             # Migration versions
│   │   └── initial_generic_schema.py  # Initial database schema
│   ├── env.py                # Alembic environment configuration
│   └── script.py.mako        # Migration script template
├── consumers/                # Kafka consumers
│   ├── kafka_config.py       # Kafka configuration
│   └── notification_consumer.py  # Notification consumer
├── docs/                     # Documentation
│   ├── project_structure.md  # This file
│   ├── database.md           # Database documentation
│   ├── authentication.md     # Authentication documentation
│   ├── kafka.md              # Kafka documentation
│   ├── services.md           # Services documentation
│   ├── scheduler.md          # Scheduler documentation
│   └── llm.md                # LLM integration documentation
├── services/                 # Service modules
│   ├── items.py              # Item service (CRUD operations)
│   ├── notifications.py      # Notification service
│   ├── users.py              # User service (authentication, profile)
│   └── webhooks.py           # Webhook service
├── static/                   # Static files
│   └── index.html            # Welcome page
├── auth.py                   # Authentication utilities
├── db.py                     # Database configuration
├── docker-compose.yml        # Docker Compose configuration
├── env.py                    # Environment configuration
├── kafka_consumer.py         # Kafka consumer framework
├── llm.py                    # LLM integration (Anthropic Claude)
├── Makefile                  # Makefile for common commands
├── memcache.py               # Redis cache utilities
├── models.py                 # Database models
├── pyproject.toml            # Poetry configuration
├── README.md                 # Project README
├── scheduler.py              # Background task scheduler
└── server.py                 # Main FastAPI application
```

## Key Components

### Core Files

- **server.py**: The main FastAPI application entry point. Defines the API routes, middleware, and startup/shutdown events.
- **models.py**: SQLAlchemy ORM models for the database schema.
- **auth.py**: Authentication utilities for JWT token generation, validation, and refresh token handling.
- **db.py**: Database connection and session management.
- **env.py**: Environment configuration using Pydantic settings.
- **memcache.py**: Redis cache utilities for caching data.
- **scheduler.py**: Background task scheduler for running periodic tasks.
- **kafka_consumer.py**: Kafka consumer framework for processing messages from Kafka topics.
- **llm.py**: LLM integration with Anthropic Claude for AI capabilities.

### Services

The `services/` directory contains modules that implement the business logic of the application:

- **users.py**: User management, authentication, and profile operations.
- **items.py**: Generic CRUD operations for items (example service).
- **notifications.py**: Notification management for sending messages to users.
- **webhooks.py**: Webhook integration for receiving and processing external events.

### Consumers

The `consumers/` directory contains Kafka consumers for processing messages from Kafka topics:

- **kafka_config.py**: Kafka configuration for consumers.
- **notification_consumer.py**: Consumer for processing notification messages.

### Database Migrations

The `alembic/` directory contains database migration scripts:

- **versions/initial_generic_schema.py**: Initial database schema migration.

## Docker Setup

The project includes a Docker Compose configuration for local development:

- PostgreSQL database
- Redis cache
- Kafka message broker

## Getting Started

See the [README.md](../README.md) for setup instructions and more information.
