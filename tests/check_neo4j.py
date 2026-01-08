from app.services.neo4j_service import neo4j_service

def verify_neo4j():
    if not neo4j_service.driver:
        print("Driver not initialized")
        return

    with neo4j_service.driver.session() as session:
        # 1. Check for Chunk nodes
        result = session.run("MATCH (c:Chunk) RETURN count(c) as count")
        count = result.single()["count"]
        print(f"Total Chunk nodes: {count}")

        # 2. Check for Indexes
        result = session.run("SHOW INDEXES")
        indexes = [record["name"] for record in result]
        print(f"Current Indexes: {indexes}")

        # 3. Check specific project
        project_id = "0b881641-b75d-44d6-9ef6-ddb3cb329ff6"
        result = session.run("MATCH (c:Chunk {project_id: $pid}) RETURN c.uuid as uuid, c.content as content LIMIT 3", pid=project_id)
        print(f"Chunks for project {project_id}:")
        for record in result:
            print(f" - {record['uuid']}: {record['content'][:30]}...")

if __name__ == "__main__":
    verify_neo4j()
