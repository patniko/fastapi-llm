# Database Documentation

This document provides an overview of the database schema and models used in the FastAPI Template.

## Database Configuration

The database configuration is defined in `db.py`. The application uses SQLAlchemy as the ORM with PostgreSQL as the database.

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from env import get_sqlConnectionString

Base = declarative_base()

# Database setup
engine = create_engine(
    get_sqlConnectionString(),
    pool_size=20,
    max_overflow=30,
    pool_timeout=60,
    pool_recycle=3600,
    pool_pre_ping=True,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## Database Models

The database models are defined in `models.py` using SQLAlchemy ORM. Here's an overview of the main models:

### User Model

The `User` model represents a user in the system:

```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String)
    email = Column(String, unique=True, index=True, nullable=True)
    email_verified = Column(Boolean, default=False)
    phone = Column(String, unique=True, index=True, nullable=True)
    phone_verified = Column(Boolean, default=False)
    picture = Column(String, unique=False, nullable=True)
    password_hash = Column(String, nullable=True)
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_logged_in = Column(DateTime(timezone=True), nullable=True)
    timezone = Column(String, nullable=False, default="UTC")
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, default=False)
```

### Authentication Models

#### RefreshToken Model

The `RefreshToken` model stores refresh tokens for JWT authentication:

```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token = Column(String, nullable=False, unique=True, index=True)
    device_info = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

#### DeviceToken Model

The `DeviceToken` model stores device tokens for push notifications:

```python
class DeviceToken(Base):
    __tablename__ = "device_tokens"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token = Column(String, nullable=False, unique=True, index=True)
    device_type = Column(String, nullable=False)  # "ios" or "android"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

### Notification Model

The `Notification` model stores notifications for users:

```python
class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    users = Column(ARRAY(Integer), nullable=False)
    event = Column(String, nullable=False)
    message = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_status = Column(Boolean, default=False)
```

### OAuth2 Models

The `OAuth2Credentials` model stores OAuth2 credentials for external services:

```python
class OAuth2Provider(str, enum.Enum):
    GOOGLE = "google"
    GITHUB = "github"
    FACEBOOK = "facebook"


class OAuth2Credentials(Base):
    __tablename__ = "oauth2_credentials"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider = Column(Enum(OAuth2Provider), nullable=False)
    email = Column(String, nullable=False, index=True)
    access_token = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

### Item Model (Example)

The `Item` model is a generic example model for demonstration purposes:

```python
class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    data = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

## Pydantic Models

The `models.py` file also defines Pydantic models for API request and response validation:

```python
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user_id: int
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    email_verified: bool
    phone: str
    phone_verified: bool
    picture: str

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    password: str


class UserUpdate(BaseModel):
    first_name: str = None
    last_name: str = None
    email: str = None
    phone: str = None
    picture: str = None


class ItemCreate(BaseModel):
    title: str
    description: str = None
    data: dict = None


class ItemResponse(BaseModel):
    id: int
    title: str
    description: str = None
    data: dict = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ItemUpdate(BaseModel):
    title: str = None
    description: str = None
    data: dict = None
    is_active: bool = None
```

## Database Migrations

Database migrations are managed using Alembic. The initial migration is defined in `alembic/versions/initial_generic_schema.py`.

To run migrations:

```bash
make migration-run
```

To create a new migration:

```bash
make migration-new m="migration_name"
