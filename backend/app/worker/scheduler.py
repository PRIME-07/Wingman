from typing import Optional
from arq import create_pool
from arq.connections import RedisSettings
from backend.app.core.config import settings
from backend.app.core.logging import logger

async def enqueue_background_task(task_name: str, *args, **kwargs) -> bool:
    """
    Connects temporarily to Redis to inject an asynchronous task into the 
    active global work queue handled by distributed workers.
    """
    try:
        redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
        pool = await create_pool(redis_settings)
        
        logger.info(f"[Worker-Scheduler] Enqueuing async task '{task_name}' into Redis.")
        
        # Enqueue the target task
        job = await pool.enqueue_job(task_name, *args, **kwargs)
        
        await pool.close()
        
        if job:
            logger.info(f"[Worker-Scheduler] Successfully registered Job ID='{job.job_id}'.")
            return True
        
        return False
    except Exception as e:
        logger.error(f"[Worker-Scheduler] Failed to communicate with Redis queue: {e}", exc_info=True)
        # Return false indicator to allow handlers to decide if they should fallback to synchronous loops
        return False
