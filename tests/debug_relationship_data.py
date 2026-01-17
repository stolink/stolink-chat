import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.services.neo4j_service import neo4j_service
from app.services.unified_search_service import unified_search_service
from app.services.embedding_service import embedding_service

async def check_data():
    project_id = "1" # Assuming default or we need to find one.
    # Actually, let's try to find the project first or just list characters generally if possible,
    # but neo4j_service methods usually require project_id.
    # Let's assume the user is working on a specific project.
    # Since I don't know the exact project_id, I might need to query it or guess.
    # However, for the purpose of the script, I'll search characters by name across the DB if possible,
    # OR better: I'll use the search_characters method which takes project_id.

    # Wait, I need a valid project_id.
    # Let's peek at the DB to find a project_id first.

    print("--- 1. Getting Project ID ---")
    query_proj = "MATCH (p:Project) RETURN p.id LIMIT 1"

    with neo4j_service.driver.session() as session:
        result = session.run(query_proj)
        record = result.single()

        if record:
            project_id = record["p.id"]
            print(f"Found Project Node: {project_id}")
        else:
            print("No Project Node found. Checking Character nodes...")
            result = session.run("MATCH (c:Character) RETURN c.project_id LIMIT 1")
            record = result.single()
            if record:
                project_id = record["c.project_id"]
                print(f"Found Project ID from Character: {project_id}")
            else:
                print("CRITICAL: No Data found in Neo4j.")
                return

    # Check Total Characters
    with neo4j_service.driver.session() as session:
        count = session.run(f"MATCH (c:Character {{project_id: '{project_id}'}}) RETURN count(c) as count").single()["count"]
        print(f"Total Characters in Project: {count}")

    print("\n--- 2. Direct Character Lookup (Exact & Fuzzy) ---")
    char_yoon = neo4j_service.get_character_by_name(project_id, "윤재")
    char_mijeong = neo4j_service.get_character_by_name(project_id, "미정")

    print(f"Found '윤재' node: {char_yoon is not None}")
    if char_yoon: print(f"ID: {char_yoon['id']}, Name: {char_yoon['name']}")

    print(f"Found '미정' node: {char_mijeong is not None}")
    if char_mijeong: print(f"ID: {char_mijeong['id']}, Name: {char_mijeong['name']}")

    if not char_yoon or not char_mijeong:
        # Try finding '박미정' since the text mentioned '박미정'
        print("Trying '박미정'...")
        char_mijeong = neo4j_service.get_character_by_name(project_id, "박미정")
        print(f"Found '박미정' node: {char_mijeong is not None}")
        if char_mijeong: print(f"ID: {char_mijeong['id']}, Name: {char_mijeong['name']}")

    if char_yoon and char_mijeong:
        print("\n--- 3. Checking Relationship Edge ---")
        rel = neo4j_service.get_relationship_between(project_id, char_yoon['id'], char_mijeong['id'])
        if rel:
            print("RELATIONSHIP FOUND:")
            print(rel)
        else:
            print("NO RELATIONSHIP EDGE FOUND between these two IDs.")

    print("\n--- 4. Checking Search Retrieval (Unified Search) ---")
    # Simulate what chat service does
    query_text = "윤재와 미정의 관계는 어떻게 돼?"
    # We need an embedding mock or actual call.
    # Using actual embedding service if available

    try:
        embedding = await asyncio.to_thread(embedding_service.get_embedding, query_text)
        search_results = await unified_search_service.search(
            project_id=project_id,
            query_embedding=embedding,
            query_text=query_text
        )

        print(f"Search found {len(search_results.get('characters', []))} characters.")
        for i, c in enumerate(search_results.get('characters', [])):
            print(f"Rank {i+1}: {c['name']} (score/source: {c.get('source')})")

        # Check if our target chars are in top 4
        c_names = [c['name'] for c in search_results.get('characters', [])[:4]]
        print(f"Top 4 candidates: {c_names}")

    except Exception as e:
        print(f"Search simulation failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_data())
