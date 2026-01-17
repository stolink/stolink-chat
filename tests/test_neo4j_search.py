from app.services.neo4j_service import neo4j_service
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_search():
    project_id = "cd250a32-e05d-4752-9795-8364674e7859"
    query = "코제트는 누구인가요?"

    print(f"Searching characters for query: '{query}' in project {project_id}")
    results = neo4j_service.search_characters(project_id, query)

    print(f"\nFound {len(results)} characters:")
    for char in results:
        print(f"- Name: {char['name']}")
        print(f"  Role: {char['role']}")
        print(f"  Backstory: {char['backstory'][:100]}...")

if __name__ == "__main__":
    test_search()
