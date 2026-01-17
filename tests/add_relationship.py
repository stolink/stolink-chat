from app.services.neo4j_service import neo4j_service

def add_test_relationship():
    project_id = "cd250a32-e05d-4752-9795-8364674e7859"
    char1_id = "759b1d15-757d-40ee-828f-af60e0578cb6" # 코제트
    char2_id = "e8eb4efb-e61b-4e23-8405-fc4f0a1602f8" # 장발장
    # Ensure they exist and link them
    query = """
    MATCH (c1:Character {id: $id1, project_id: $pid})
    MATCH (c2:Character {id: $id2, project_id: $pid})
    MERGE (c1)-[r:RELATED_TO]->(c2)
    SET r.types = ['부녀'],
        r.strength = 10,
        r.description = '장발장은 코제트의 양아버지이며 그녀를 보호한다.',
        r.bidirectional = true,
        r.since = '코제트의 어린 시절',
        r.revealedInChapter = 2
    RETURN r
    """
    with neo4j_service.driver.session() as session:
        result = session.run(query, id1=char1_id, id2=char2_id, pid=project_id)
        if result.single():
            print("Successfully added relationship between 코제트 and 장발장")
        else:
            print("Failed to add relationship (Characters might not exist with these IDs)")

if __name__ == "__main__":
    add_test_relationship()
