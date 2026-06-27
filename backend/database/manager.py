import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("travelops.database.manager")

class DatabaseManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///travelops.db")
        logger.info(f"DatabaseManager initializing engine for URL schema: {self.database_url.split('://')[0]}://...")
        
        # Configure connection arguments based on database engine type
        if self.database_url.startswith("sqlite"):
            # SQLite specific thread pooling flags
            from sqlalchemy.pool import NullPool
            from sqlalchemy import event
            self.engine = create_engine(
                self.database_url,
                connect_args={"check_same_thread": False, "timeout": 30},
                poolclass=NullPool
            )
            
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()
        else:
            # PostgreSQL connection pool settings for enterprise concurrent queries
            self.engine = create_engine(
                self.database_url,
                pool_size=15,
                max_overflow=25,
                pool_timeout=30,
                pool_pre_ping=True
            )
            
        self.session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        self._initialized = True

    def get_engine(self):
        """Returns the active SQLAlchemy Engine."""
        return self.engine

    def get_session(self) -> Session:
        """Returns a new Session instance."""
        return self.session_factory()

    @contextmanager
    def session_scope(self):
        """Transactional scope context manager for safe SQLAlchemy operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Transaction failed, session rolled back: {e}")
            raise
        finally:
            session.close()
            
    def init_db(self, base):
        """Creates database schemas if SQLite. For production Postgres, migrations should manage schemas."""
        logger.info("Initializing database schemas...")
        try:
            base.metadata.create_all(bind=self.engine)
            logger.info("Database schemas verified/created successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize database tables: {e}")
            raise
