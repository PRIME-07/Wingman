import logging
import sys
from backend.app.core.config import settings

def setup_logging():
    """Configure logging for the application."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Avoid adding multiple handlers
    if logging.getLogger().hasHandlers():
        logging.getLogger().handlers.clear()
        
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )
    
    # Suppress verbose third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    
    logger = logging.getLogger("wingman")
    logger.info(f"Logging setup complete with level: {settings.LOG_LEVEL}")
    return logger

# Instantiate logger
logger = setup_logging()
