import asyncio
import os
import sys

# Ensure project root is in path so 'backend.app' imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.memory.neo4j_client import neo4j_client
from backend.app.memory.vector_client import chroma_client
from backend.app.memory.mongodb_client import mongo_client
from backend.app.core.config import settings

async def wipe_neo4j():
    print(f"Connecting to Neo4j at {settings.NEO4J_URI}...")
    neo4j_client.connect()
    try:
        with neo4j_client._driver.session(database=settings.NEO4J_DATABASE) as session:
            print("Wiping all nodes and relationships from Neo4j...")
            result = session.run("MATCH (n) DETACH DELETE n")
            summary = result.consume()
            print(f"Neo4j Wipe Complete: {summary.counters.nodes_deleted} nodes deleted.")
    except Exception as e:
        print(f"Error wiping Neo4j: {e}")
    finally:
        neo4j_client.close()

async def wipe_chroma():
    print(f"Connecting to Chroma collection: {settings.CHROMA_COLLECTION_NAME}...")
    try:
        # Re-create client and get collection to avoid async issues
        client = chroma_client._get_client()
        print("Wiping all vectors from Chroma...")
        # Simplest way to wipe chroma collection is to delete and recreate it
        try:
            client.delete_collection(name=settings.CHROMA_COLLECTION_NAME)
        except Exception:
            pass # might not exist
        # Recreate so it's fresh
        client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        print("Chroma Wipe Complete.")
    except Exception as e:
        print(f"Error wiping Chroma: {e}")

async def wipe_mongodb_all():
    print(f"Connecting to MongoDB database: {settings.MONGODB_DB_NAME}...")
    try:
        mongo_client.connect()
        db = mongo_client.db
        collections = await db.list_collection_names()
        
        for coll_name in collections:
            print(f"Clearing documents from collection: {coll_name}...")
            res = await db[coll_name].delete_many({})
            print(f" - {coll_name} Wipe Complete: {res.deleted_count} documents removed.")
            
        print("MongoDB Global Data Wipe Complete.")
    except Exception as e:
        print(f"Error wiping MongoDB: {e}")

async def main():
    print("--- Starting Global Memory Wipe ---")
    await wipe_neo4j()
    await wipe_chroma()
    await wipe_mongodb_all()
    print("--- Memory Wipe Finished ---")

if __name__ == "__main__":
    asyncio.run(main())
