from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.services.credentials.manager import credential_manager
import time

class Neo4jClient:
    """
    Handles permanent semantic knowledge storage within the Neo4j Graph structure.
    Features transaction decorators and automatic connection pool recovery.
    """
    def __init__(self):
        self._driver = None

    async def connect(self):
        """Lazy-loads the Neo4j driver with hybrid credential lookup."""
        if not self._driver:
            uri = await credential_manager.get_secret("neo4j_uri") or settings.NEO4J_URI
            user = await credential_manager.get_secret("neo4j_user") or settings.NEO4J_USER
            password = await credential_manager.get_secret("neo4j_password") or settings.NEO4J_PASSWORD
            
            logger.info(f"[Neo4j] Initializing connection pool to uri: {uri}")
            try:
                self._driver = GraphDatabase.driver(uri, auth=(user, password))
                self._driver.verify_connectivity()
                logger.info("[Neo4j] Authenticated & Connected Successfully.")
            except Exception as e:
                logger.error(f"[Neo4j] FAILED CONNECTING to node: {e}", exc_info=True)
                raise

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("[Neo4j] Driver pool closed.")

    async def save_semantic_memories(self, memories: List[Dict[str, Any]], provenance: Optional[Dict[str, Any]] = None) -> bool:
        """
        Commits long-term knowledge traces inside a single transaction.
        """
        await self.connect()
        database = await credential_manager.get_secret("neo4j_database") or settings.NEO4J_DATABASE
        
        try:
            with self._driver.session(database=database) as session:
                session.execute_write(self._commit_nodes, memories, provenance)
            return True
        except Exception as e:
            logger.error(f"[Neo4j-TRANS] Managed Write Transaction failed: {e}", exc_info=True)
            return False

    @staticmethod
    def _commit_nodes(tx, memories: List[Dict[str, Any]], provenance: Optional[Dict[str, Any]] = None):
        """Commits semantic entities and edges inside standard transactional bounds."""
        session_id = provenance.get("session_id") if provenance else None
        trace_id = provenance.get("trace_id") if provenance else None
        run_id = provenance.get("run_id") if provenance else None
        
        if session_id:
            tx.run(
                "MERGE (s:ConversationSession {session_id: $session_id}) "
                "ON CREATE SET s.created_at = datetime()", 
                session_id=session_id
            )

        for mem in memories:
            entity = mem.get("entity", "unknown").strip()
            etype = mem.get("type", "General").strip()
            fact = mem.get("fact", "").strip()
            
            if not entity or not fact:
                continue

            # Priority 13: Adaptive Memory Lifecycle Reinforcement
            # Upon recommitting or accessing, increment access counters, reset last_accessed, and boost strength.
            cypher = (
                "MERGE (e:Entity {name: $entity}) "
                "ON CREATE SET e.type = $etype, e.created_at = datetime(), e.access_count = 1, e.last_accessed_at = datetime() "
                "ON MATCH SET e.updated_at = datetime(), e.access_count = coalesce(e.access_count, 1) + 1, e.last_accessed_at = datetime() "
                "MERGE (f:Fact {description: $fact}) "
                "ON CREATE SET f.created_at = datetime(), f.access_count = 1, f.last_accessed_at = datetime(), f.strength = 1.0, f.status = 'Active' "
                "ON MATCH SET f.access_count = coalesce(f.access_count, 1) + 1, f.last_accessed_at = datetime(), "
                "             f.strength = CASE WHEN coalesce(f.strength, 1.0) < 1.4 THEN coalesce(f.strength, 1.0) + 0.1 ELSE 1.5 END, "
                "             f.status = 'Active' "
                "MERGE (e)-[r:HAS_FACT]->(f) "
                "SET r.updated_at = datetime(), r.confidence = $confidence"
            )
            
            params = {
                "entity": entity,
                "etype": etype,
                "fact": fact,
                "confidence": mem.get("confidence_score") or mem.get("confidence", 1.0)
            }
            
            if session_id:
                cypher += (
                    " WITH f "
                    "MATCH (s:ConversationSession {session_id: $session_id}) "
                    "MERGE (f)-[d:DERIVED_FROM]->(s) "
                    "SET d.trace_id = $trace_id, d.run_id = $run_id, d.created_at = datetime()"
                )
                params["session_id"] = session_id
                params["trace_id"] = trace_id
                params["run_id"] = run_id
                
            tx.run(cypher, **params)

    async def retrieve_memories_for_entities(self, entities: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetches active facts relating to specific entities.
        """
        await self.connect()
        database = await credential_manager.get_secret("neo4j_database") or settings.NEO4J_DATABASE
        
        query = (
            "MATCH (e:Entity)-[r:HAS_FACT]->(f:Fact) "
            "WHERE e.name IN $entities AND f.status = 'Active' "
            "WITH e, f, r "
            "ORDER BY f.strength DESC, f.last_accessed_at DESC "
            "LIMIT $limit "
            "SET f.last_accessed_at = datetime(), "
            "    f.access_count = coalesce(f.access_count, 1) + 1 "
            "RETURN e.name AS entity, f.description AS fact, f.strength AS strength, r.confidence AS confidence"
        )
        
        try:
            with self._driver.session(database=database) as session:
                result = session.run(query, entities=entities, limit=limit)
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"[Neo4j] Error retrieving memories for {entities}: {e}")
            return []

    async def run_decay_lifecycle(self, decay_factor: float = 0.85, archive_threshold: float = 0.4) -> Dict[str, Any]:
        """
        Runs the programmatic decay algorithm on a scheduled basis.
        """
        await self.connect()
        database = await credential_manager.get_secret("neo4j_database") or settings.NEO4J_DATABASE
        
        # 1. Decay facts untouched in the last 7 days
        decay_cypher = (
            "MATCH (f:Fact) "
            "WHERE f.status = 'Active' AND datetime().epochSeconds - f.last_accessed_at.epochSeconds > (7 * 24 * 3600) "
            "SET f.strength = coalesce(f.strength, 1.0) * $decay_factor "
            "RETURN count(f) AS decayed_count"
        )
        
        # 2. Archive facts whose strength fell below the minimum bar
        archive_cypher = (
            "MATCH (f:Fact) "
            "WHERE f.status = 'Active' AND coalesce(f.strength, 1.0) < $archive_threshold "
            "SET f.status = 'Archived', f.archived_at = datetime() "
            "RETURN count(f) AS archived_count"
        )
        
        results = {"decayed": 0, "archived": 0}
        try:
            with self._driver.session(database=database) as session:
                d_res = session.run(decay_cypher, decay_factor=decay_factor)
                results["decayed"] = d_res.single()["decayed_count"]
                
                a_res = session.run(archive_cypher, archive_threshold=archive_threshold)
                results["archived"] = a_res.single()["archived_count"]
                
            logger.info(f"[Neo4j-Lifecycle] Completed decay cycle: {results['decayed']} decayed, {results['archived']} archived.")
            return results
        except Exception as e:
            logger.error(f"[Neo4j-Lifecycle] Decay routine aborted: {e}", exc_info=True)
            return results

# Singleton provider
neo4j_client = Neo4jClient()
