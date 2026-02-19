from datetime import date, datetime
from typing import List, Optional
from sqlmodel import Field, Relationship, SQLModel

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    is_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    itinerary_days: List["ItineraryDay"] = Relationship(back_populates="user")
    flights: List["Flight"] = Relationship(back_populates="user")
    expenses: List["Expense"] = Relationship(back_populates="user")
    sessions: List["SessionData"] = Relationship(back_populates="user")

class City(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    country: str
    lat: float
    lon: float
    description: Optional[str] = None
    order: int = 0

    # Relationships
    itinerary_days: List["ItineraryDay"] = Relationship(back_populates="city")
    accommodations: List["Accommodation"] = Relationship(back_populates="city")

class ItineraryDay(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: date
    user_id: int = Field(foreign_key="user.id")
    city_id: int = Field(foreign_key="city.id")
    title: str
    notes: Optional[str] = None

    # Relationships
    user: User = Relationship(back_populates="itinerary_days")
    city: City = Relationship(back_populates="itinerary_days")
    activities: List["Activity"] = Relationship(back_populates="itinerary_day")

class Activity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    itinerary_day_id: int = Field(foreign_key="itineraryday.id")
    time: datetime # Specific time of the activity
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    cost: Optional[float] = None
    order: int = 0

    # Relationships
    itinerary_day: ItineraryDay = Relationship(back_populates="activities")

class Accommodation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    city_id: int = Field(foreign_key="city.id")
    name: str
    address: str
    check_in: date
    check_out: date
    cost: Optional[float] = None
    booking_url: Optional[str] = None
    notes: Optional[str] = None

    # Relationships
    city: City = Relationship(back_populates="accommodations")

class Flight(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    departure_city: str
    arrival_city: str
    datetime: datetime
    flight_number: Optional[str] = None
    cost: Optional[float] = None
    booking_ref: Optional[str] = None

    # Relationships
    user: User = Relationship(back_populates="flights")

class Expense(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    date: date
    description: str
    amount: float
    category: Optional[str] = None # e.g., "Food", "Transport", "Shopping"
    split_with: Optional[str] = None # e.g., "pedro.rodrigues" for shared expenses

    # Relationships
    user: User = Relationship(back_populates="expenses")

    # Pydantic models for API request/response
# These will be created as needed for CRUD operations later.
# For example:
# class UserCreate(SQLModel):
#     username: str
#     password: str
#     is_admin: bool = False

class SessionData(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(unique=True, index=True)
    user_id: int = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime

    user: User = Relationship(back_populates="sessions")
