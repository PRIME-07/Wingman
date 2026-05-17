from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.chat import router as chat_router
from backend.app.api.v1.telemetry import router as telemetry_router

def create_app() -> FastAPI:
    """Initializes the FastAPI application instance."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="The backend orchestrator for the Wingman personalized AI OS.",
        version=settings.VERSION,
        debug=settings.DEBUG
    )
    
    # Setup CORS middleware for frontend connectivity
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Setup Application Lifecycle Events
    @app.on_event("startup")
    async def startup_event():
        logger.info(f"Starting up {settings.APP_NAME} v{settings.VERSION}")
        try:
            # Connect databases during server bootstrap
            from backend.app.memory.mongodb_client import mongo_client
            from backend.app.memory.neo4j_client import neo4j_client
            
            logger.info("Initializing persistent data clients...")
            mongo_client.connect()
            # Provision indexes on startup
            await mongo_client.ensure_indexes()
            # Neo4j connectivity checked via drivers
            await neo4j_client.connect()
            
            # Initialize and bootstrap Global Event Bus
            from backend.app.event_bus.bus import event_bus
            from backend.app.telemetry.manager import telemetry_manager
            
            # Subscribe telemetry broadcaster and persistence recorders to 'telemetry' topics
            from backend.app.telemetry.recorder import telemetry_recorder
            event_bus.subscribe("telemetry", telemetry_manager.broadcast)
            event_bus.subscribe("telemetry", telemetry_recorder.record_event)

            
            # Start asynchronous worker dispatcher
            await event_bus.start_dispatcher()
            
            logger.info("Data storage and Event Bus instances initialized securely.")
        except Exception as e:
            logger.critical(f"CRITICAL: DB Initialization Failed! Proceeding in degraded state. Error: {e}", exc_info=True)
        
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info(f"Shutting down {settings.APP_NAME}")
        from backend.app.memory.mongodb_client import mongo_client
        from backend.app.memory.neo4j_client import neo4j_client
        from backend.app.event_bus.bus import event_bus
        
        # Halt event bus dispatcher
        await event_bus.stop_dispatcher()
        
        mongo_client.disconnect()
        neo4j_client.close()
        logger.info("Resources released cleanly.")

        
    # Include standard REST/WS routes
    app.include_router(health_router, tags=["System"])
    
    # Version 1 API grouping
    app.include_router(
        chat_router, 
        prefix=f"{settings.API_V1_STR}/chat", 
        tags=["Conversational"]
    )
    
    app.include_router(
        telemetry_router,
        prefix=f"{settings.API_V1_STR}/telemetry",
        tags=["System", "Telemetry"]
    )
    
    from backend.app.api.v1.memory import router as memory_router
    app.include_router(
        memory_router,
        prefix=f"{settings.API_V1_STR}/memory",
        tags=["Memory Lifecycle"]
    )

    from backend.app.api.v1.sessions import router as sessions_router
    app.include_router(
        sessions_router,
        prefix=f"{settings.API_V1_STR}/sessions",
        tags=["Context Spaces"]
    )

    from backend.app.api.v1.auth import router as auth_router
    app.include_router(
        auth_router,
        prefix=f"{settings.API_V1_STR}/auth",
        tags=["Authentication"]
    )

    from backend.app.api.v1.documents import router as documents_router
    app.include_router(
        documents_router,
        prefix=f"{settings.API_V1_STR}/documents",
        tags=["Document Ingestion & RAG"]
    )

    from backend.app.api.v1.search import router as search_router
    app.include_router(
        search_router,
        prefix=f"{settings.API_V1_STR}/search",
        tags=["Search Aggregation"]
    )

    from backend.app.api.v1.tools import router as tools_router
    app.include_router(
        tools_router,
        prefix=f"{settings.API_V1_STR}/tools",
        tags=["Tools Configuration"]
    )

    from backend.app.api.v1.calendar import router as calendar_router
    app.include_router(
        calendar_router,
        prefix=f"{settings.API_V1_STR}/calendar",
        tags=["Calendar Module"]
    )

    from backend.app.api.v1.clock import router as clock_router
    app.include_router(
        clock_router,
        prefix=f"{settings.API_V1_STR}/tools/clock",
        tags=["Clock & Timers"]
    )

    from backend.app.api.v1.contacts import router as contacts_router
    app.include_router(
        contacts_router,
        prefix=f"{settings.API_V1_STR}/contacts",
        tags=["Contacts Directory"]
    )


    
    logger.info("FastAPI routes mapped successfully.")
    
    return app

# Main App Instance for Uvicorn runner
app = create_app()
