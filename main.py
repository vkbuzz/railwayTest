import os
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv

# Load variables from the .env file into the environment
load_dotenv()


# 1. Database Configuration & Environment Validation
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("CRITICAL ERROR: DATABASE_URL environment variable is not set!")

# Railway fallback: Fixes legacy 'postgres://' URIs to match modern SQLAlchemy syntax
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Initialize SQLAlchemy core components
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 2. Database Model
class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)


# Automatically build database schemas/tables on application boot
Base.metadata.create_all(bind=engine)


# 3. Pydantic Schemas (Data Validation)
class UserBase(BaseModel):
    name: str
    email: str


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int

    # Enables Pydantic to read ORM models automatically
    model_config = ConfigDict(from_attributes=True)


# 4. FastAPI Setup & Dependency Injection
app = FastAPI(title="Railway FastAPI Postgres App")


# Database Session management context
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 5. API Endpoints
@app.get("/", status_code=status.HTTP_200_OK)
def read_root():
    """Health check route for Railway deployment monitoring."""
    return {"status": "healthy", "message": "FastAPI is running successfully!"}


@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user in the PostgreSQL database."""
    # Check if email duplicate exists
    db_user = db.query(UserDB).filter(UserDB.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Insert and commit transaction
    new_user = UserDB(name=user.name, email=user.email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.get("/users", response_model=List[UserResponse], status_code=status.HTTP_200_OK)
def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Fetch all users from the PostgreSQL database."""
    users = db.query(UserDB).offset(skip).limit(limit).all()
    return users
