"""Neo4j 데이터 상태 확인 스크립트.

실행: python tests/check_neo4j_data.py
"""

import sys
sys.path.insert(0, '.')

from app.services.neo4j_service import neo4j_service


def check_neo4j_data():
    """Neo4j에 저장된 데이터 현황을 확인."""

    print("=" * 60)
    print("Neo4j 데이터 상태 확인")
    print("=" * 60)

    driver = neo4j_service.driver
    if not driver:
        print("❌ Neo4j 연결 실패")
        return

    with driver.session() as session:
        # 1. 노드 타입별 개수
        print("\n📊 노드 타입별 개수:")
        result = session.run("""
            CALL db.labels() YIELD label
            CALL apoc.cypher.run('MATCH (n:`' + label + '`) RETURN count(n) as count', {})
            YIELD value
            RETURN label, value.count as count
            ORDER BY value.count DESC
        """)
        for record in result:
            print(f"  - {record['label']}: {record['count']}개")

        # 2. Chunk 노드 상세 확인
        print("\n📦 Chunk 노드 상태:")
        chunk_result = session.run("""
            MATCH (c:Chunk)
            RETURN
                count(c) as total,
                count(c.embedding) as with_embedding,
                count(c.content) as with_content
        """)
        chunk_record = chunk_result.single()
        if chunk_record:
            total = chunk_record['total']
            with_emb = chunk_record['with_embedding']
            with_content = chunk_record['with_content']
            print(f"  - 전체 Chunk: {total}개")
            print(f"  - 임베딩 있는 Chunk: {with_emb}개")
            print(f"  - 컨텐츠 있는 Chunk: {with_content}개")

            if total > 0 and with_emb > 0:
                # 샘플 임베딩 차원 확인
                dim_result = session.run("""
                    MATCH (c:Chunk)
                    WHERE c.embedding IS NOT NULL
                    RETURN size(c.embedding) as dimension
                    LIMIT 1
                """)
                dim_record = dim_result.single()
                if dim_record:
                    print(f"  - 임베딩 차원: {dim_record['dimension']}")
        else:
            print("  - Chunk 노드 없음")

        # 3. Character 노드 확인
        print("\n👤 Character 노드 상태:")
        char_result = session.run("""
            MATCH (c:Character)
            RETURN count(c) as total
        """)
        char_record = char_result.single()
        print(f"  - 전체 Character: {char_record['total']}개")

        # 4. Project 노드 확인
        print("\n📁 Project 노드 상태:")
        proj_result = session.run("""
            MATCH (p:Project)
            RETURN p.id as id
        """)
        projects = [r['id'] for r in proj_result]
        print(f"  - Project IDs: {projects if projects else '없음'}")

        # 5. 벡터 인덱스 상태 확인
        print("\n🔍 벡터 인덱스 상태:")
        try:
            index_result = session.run("""
                SHOW INDEXES
                WHERE type = 'VECTOR'
            """)
            indexes = list(index_result)
            if indexes:
                for idx in indexes:
                    print(f"  - 이름: {idx.get('name', 'N/A')}")
                    print(f"    라벨: {idx.get('labelsOrTypes', 'N/A')}")
                    print(f"    속성: {idx.get('properties', 'N/A')}")
                    print(f"    상태: {idx.get('state', 'N/A')}")
            else:
                print("  - 벡터 인덱스 없음")
        except Exception as e:
            print(f"  - 인덱스 조회 실패: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    check_neo4j_data()
