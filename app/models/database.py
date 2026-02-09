"""
Database configuration and session management
"""
import ssl
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Prepare database URL and connection args
database_url = settings.DATABASE_URL
connect_args = {}

# Convert postgresql:// to postgresql+asyncpg:// for async support
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)

# Handle SSL for cloud databases (Neon, Vercel, etc.)
if "neon.tech" in database_url or "vercel" in database_url.lower():
    # Remove sslmode from URL if present (asyncpg doesn't support it)
    if "sslmode=" in database_url:
        import re
        database_url = re.sub(r'[?&]sslmode=[^&]*', '', database_url)
        database_url = database_url.replace('?&', '?').rstrip('?')
    
    # Create SSL context for asyncpg
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_context

# Create async engine
engine = create_async_engine(
    database_url,
    echo=settings.DATABASE_ECHO,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args=connect_args
)

# Async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting async database session"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
