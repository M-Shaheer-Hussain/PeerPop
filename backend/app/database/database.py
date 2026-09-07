from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine("sqlite:///./user.db", connect_args={"check_same_thread": False})
localsession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
base = declarative_base()

def get_db():
    db = localsession()
    try:
        yield db
    finally:
        db.close()