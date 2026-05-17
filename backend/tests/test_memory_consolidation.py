import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.memory.mongodb_client import mongo_client
from backend.app.scheduler.consolidation import SemanticFact, KnowledgeDistillationResult

def test_daily_naming():
    """Verifies naming schemas generate cleanly partitionable formats."""
    fixed_date = datetime(2026, 5, 13)
    coll_name = mongo_client.get_daily_collection_name(fixed_date)
    assert coll_name == "raw_chats_2026_05_13"
    print("✓ Schema naming pattern verified.")

def test_safeguard_protections():
    """Ensures critical deletion protections cannot be circumvented."""
    fixed_date = datetime(2026, 5, 13)
    
    # Test that random name blocks
    class MockMongo(type(mongo_client)):
        def get_daily_collection_name(self, date):
            return "user-docs"  # Attempting collision injection

    mocked = MockMongo()
    try:
        # Mock internal connection
        mocked.client = True
        mocked.db = True
        # Should raise explicit permission error
        asyncio.run(mocked.prune_daily_conversations(fixed_date))
        assert False, "Safety bypass occurred!"
    except PermissionError as e:
        print(f"✓ Hardened Safeguard successfully BLOCKED protected collection drop: {e}")
        
    try:
        class MockInject(type(mongo_client)):
            def get_daily_collection_name(self, date):
                return "some_random_admin_db"
        mocked_inj = MockInject()
        mocked_inj.client = True
        mocked_inj.db = True
        asyncio.run(mocked_inj.prune_daily_conversations(fixed_date))
        assert False, "Safety bypass occurred!"
    except PermissionError as e:
        print(f"✓ Safeguard successfully BLOCKED unpartitioned namespaced drop.")

def test_distillation_schema():
    """Verifies Pydantic schemas used by with_structured_output compile cleanly."""
    fact = SemanticFact(
        entity="Coffee",
        type="Preference",
        fact="Likes Ethiopian light roast",
        confidence=0.95
    )
    
    results = KnowledgeDistillationResult(memories=[fact])
    dumped = results.model_dump()
    
    assert "memories" in dumped
    assert dumped["memories"][0]["entity"] == "Coffee"
    assert dumped["memories"][0]["confidence"] == 0.95
    print("✓ Pydantic LLM Structured schema generation verified.")

def run_all():
    print("\n=== RUNNING MEMORY PIPELINE VALIDATIONS ===\n")
    try:
        test_daily_naming()
        test_safeguard_protections()
        test_distillation_schema()
        print("\n[ALL MEMORY INTEGRITY CHECKS PASSED SUCCESSFULLY]")
    except Exception as e:
        print(f"\n[VALIDATION FAILURE] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_all()
