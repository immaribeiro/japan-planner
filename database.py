from sqlmodel import create_engine, Session, SQLModel
from config import settings

# Create the database engine
engine = create_engine(settings.DATABASE_URL, echo=False)

def create_db_and_tables():
    """
    Creates all database tables defined in SQLModel metadata.
    This should be called at application startup.
    """
    SQLModel.metadata.create_all(engine)

def get_session():
    """
    Dependency to get a database session.
    Yields a session and ensures it's closed afterwards.
    """
    with Session(engine) as session:
        yield session

