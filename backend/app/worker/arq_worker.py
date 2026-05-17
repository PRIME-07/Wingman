import asyncio
from datetime import datetime
from arq import cron
from arq.connections import RedisSettings
from backend.app.core.config import settings
from backend.app.core.logging import logger

# Clients to initialize in the isolated background context
from backend.app.memory.mongodb_client import mongo_client
from backend.app.memory.neo4j_client import neo4j_client
from backend.app.scheduler.consolidation import run_micro_consolidation

async def startup(ctx):
    """
    Executes upon Redis Worker startup. 
    Ensures persistent databases and connections are active.
    """
    logger.info("[Arq-Worker] Bootstrapping background task context...")
    # Explicitly trigger client initializations for this detached runtime
    mongo_client.connect()
    logger.info("[Arq-Worker] Core state initializations completed successfully.")

async def shutdown(ctx):
    """Graceful termination handlers for the isolated pool."""
    logger.info("[Arq-Worker] Shutting down background tasks context...")
    mongo_client.disconnect()
    logger.info("[Arq-Worker] Detached worker clean shutdown complete.")

async def task_run_consolidation(ctx):
    """
    Invokes the central 4-hour micro-consolidation pipeline. 
    Serializes raw MongoDB conversations, updates permanent Neo4j knowledge,
    and safe-drops the transient window's collection.
    """
    logger.info(f"[Arq-Worker] Micro-Consolidation task triggered")
    success = await run_micro_consolidation()
    
    if success:
        logger.info("[Arq-Worker] Consolidation task executed SUCCESSFULLY.")
    else:
        logger.error("[Arq-Worker] Consolidation task completed with failure indicators.")
    return success

async def task_vector_pruning(ctx):
    """
    Runs hourly cleanup of temporary index layers or expired cached vectors.
    Ensures high performance of RAG paths.
    """
    logger.info("[Arq-Worker] Commencing scheduled Vector & Metadata pruning routine...")
    # Currently placeholders for future Pinecone/Neo4j maintenance sweeps
    logger.info("[Arq-Worker] Task completed.")
    return True

# WORKER CONFIGURATION SCHEMA
# Used by standard 'arq backend.app.worker.arq_worker.WorkerSettings' command lines

class WorkerSettings:
    """
    Centralized configuration for the distributed Arq worker instances.
    Defines functions, cron cycles, and connection pools.
    """
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    
    # Isolated Lifecycle Hooks
    on_startup = startup
    on_shutdown = shutdown
    
    # List of standalone callable task signatures
    functions = [
        task_run_consolidation,
        task_vector_pruning
    ]
    
    # Persistent Cron-Style Schedules
    cron_jobs = [
        # Run memory consolidation every 4 hours
        cron(
            task_run_consolidation,
            hour={0, 4, 8, 12, 16, 20},
            minute=0,
            run_at_startup=False,
            unique=True
        ),
        # Run vectors & logs cleanup once every hour
        cron(
            task_vector_pruning,
            minute=15,
            unique=True
        )
    ]
