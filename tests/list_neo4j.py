from app.services.neo4j_service import neo4j_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def list_neo4j_data():
    if not neo4j_service.driver:
        print("Driver not initialized")
        return

    with neo4j_service.driver.session() as session:
        # 1. List Projects
        print("=== Projects ===")
        result = session.run("MATCH (p:Project) RETURN p.id as id LIMIT 10")
        for record in result:
            print(f"Project ID: {record['id']}")

        # 2. List Characters
        print("\n=== Characters ===")
        result = session.run("MATCH (c:Character) WHERE c.name IN ['코제트', '장발장'] AND c.project_id = 'cd250a32-e05d-4752-9795-8364674e7859' RETURN c.project_id as project_id, c.name as name, c.id as id LIMIT 20")
        for record in result:
            print(f"Project: {record['project_id']} | Name: {record['name']} | ID: {record['id']}")

        # 3. List Relationships
        print("\n=== Relationships ===")
        result = session.run("""
            MATCH (s:Character)-[r:RELATED_TO]->(t:Character)
            RETURN s.name as source, t.name as target, r.types as types, s.project_id as project_id
            LIMIT 20
        """)
        for record in result:
            print(f"Project: {record['project_id']} | {record['source']} -[{record['types']}]-> {record['target']}")

if __name__ == "__main__":
    list_neo4j_data()
