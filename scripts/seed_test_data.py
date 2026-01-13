#!/usr/bin/env python3
"""
테스트 데이터 삽입 스크립트 (Neo4j 전용)
로컬에서 관계 카드 기능 테스트를 위한 샘플 데이터 생성

사용법:
    cd chat/stolink-chat
    source venv/bin/activate
    python3 scripts/seed_test_data.py

참고: 캐릭터 데이터는 Neo4j에만 저장됨 (PostgreSQL characters 테이블 없음)
"""

from neo4j import GraphDatabase

# ============================================
# 설정
# ============================================
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "stolink123"

# 기존 프로젝트 ID 사용 (DB에서 확인된 실제 프로젝트)
TEST_PROJECT_ID = "d006f313-eba9-4812-9483-1435f16e278d"

# 테스트 캐릭터 데이터
TEST_CHARACTERS = [
    {
        "id": "test-char-alex-001",
        "name": "알렉스",
        "role": "protagonist",
        "backstory": "왕국의 정당한 왕위 계승자. 어린 시절 마커스와 친구였으나 왕위 계승 문제로 갈등이 생겼다.",
        "description": "검은 머리와 녹색 눈을 가진 젊은 왕자",
        "status": "alive",
        "faction": "왕국 정통파"
    },
    {
        "id": "test-char-marcus-001",
        "name": "마커스",
        "role": "antagonist",
        "backstory": "왕국의 대공. 알렉스의 어린 시절 친구였으나 왕위를 노리며 적대 관계가 되었다.",
        "description": "금발에 푸른 눈을 가진 야심찬 귀족",
        "status": "alive",
        "faction": "귀족 연합"
    }
]

# 테스트 관계 데이터
TEST_RELATIONSHIP = {
    "source_id": TEST_CHARACTERS[0]["id"],
    "target_id": TEST_CHARACTERS[1]["id"],
    "types": ["enemy", "rival"],
    "strength": 7,
    "description": "어린 시절 친구였으나 왕위 계승 갈등으로 적대 관계가 됨. 서로에 대한 복잡한 감정을 가지고 있다.",
    "bidirectional": True,
    "since": "왕위 계승 선언 이후",
    "revealedInChapter": 3
}


def seed_neo4j():
    """Neo4j에 테스트 캐릭터 노드 및 관계 삽입"""
    print("\n🔗 Neo4j 데이터 삽입 중...")
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        with driver.session() as session:
            # 기존 테스트 데이터 삭제 (테스트 캐릭터만)
            session.run("""
                MATCH (c:Character)
                WHERE c.id STARTS WITH 'test-char-'
                DETACH DELETE c
            """)
            print("   ✓ 기존 테스트 캐릭터 삭제")
            
            # 캐릭터 노드 생성
            for char in TEST_CHARACTERS:
                session.run("""
                    MERGE (c:Character {id: $id})
                    SET c.project_id = $project_id,
                        c.name = $name,
                        c.role = $role,
                        c.backstory = $backstory,
                        c.description = $description,
                        c.status = $status,
                        c.faction = $faction
                """, id=char["id"], project_id=TEST_PROJECT_ID, 
                    name=char["name"], role=char["role"], 
                    backstory=char["backstory"], description=char["description"],
                    status=char["status"], faction=char["faction"])
                print(f"   ✓ 노드 생성: {char['name']}")
            
            # 관계 생성
            rel = TEST_RELATIONSHIP
            session.run("""
                MATCH (source:Character {id: $source_id})
                MATCH (target:Character {id: $target_id})
                MERGE (source)-[r:RELATED_TO]->(target)
                SET r.types = $types,
                    r.strength = $strength,
                    r.description = $description,
                    r.bidirectional = $bidirectional,
                    r.since = $since,
                    r.revealedInChapter = $revealedInChapter,
                    r.source = $source_id
            """, source_id=rel["source_id"], target_id=rel["target_id"],
                types=rel["types"], strength=rel["strength"],
                description=rel["description"], bidirectional=rel["bidirectional"],
                since=rel["since"], revealedInChapter=rel["revealedInChapter"])
            print(f"   ✓ 관계 생성: 알렉스 -[RELATED_TO {rel['types']}]-> 마커스")
            
            # 검증: 생성된 데이터 확인
            result = session.run("""
                MATCH (source:Character {id: $source_id})-[r:RELATED_TO]->(target:Character {id: $target_id})
                RETURN source.name as sourceName, target.name as targetName, r.types as types, r.strength as strength
            """, source_id=rel["source_id"], target_id=rel["target_id"])
            
            record = result.single()
            if record:
                print(f"\n   ✅ 검증 성공: {record['sourceName']} -> {record['targetName']}")
                print(f"      관계: {record['types']}, 강도: {record['strength']}")
        
        driver.close()
        print("\n✅ Neo4j 완료!")
        
    except Exception as e:
        print(f"❌ Neo4j 오류: {e}")
        print("\n💡 Neo4j가 실행 중인지 확인하세요:")
        print("   docker ps | grep neo4j")
        raise


def print_test_info():
    """테스트 방법 안내"""
    print("\n" + "="*60)
    print("🧪 테스트 데이터 삽입 완료!")
    print("="*60)
    print(f"""
📌 프로젝트 ID: {TEST_PROJECT_ID}

📌 삽입된 캐릭터:
   - 알렉스 (protagonist): 왕국의 정당한 왕위 계승자
   - 마커스 (antagonist): 왕위를 노리는 대공

📌 삽입된 관계:
   - 알렉스 <--[적대, 라이벌 | 강도 7]--> 마커스

🚀 테스트 방법:
   1. Chat 백엔드 시작:
      cd chat/stolink-chat
      source venv/bin/activate
      uvicorn app.main:app --reload --port 8001
   
   2. 프론트엔드에서 챗봇 열기 (해당 프로젝트)
   
   3. 챗봇에서 "알렉스와 마커스 관계가 어때?" 입력
   
   4. 관계 카드가 표시되는지 확인!
""")


def main():
    print("="*60)
    print("🌱 관계 카드 테스트 데이터 시딩 스크립트 (Neo4j 전용)")
    print("="*60)
    
    seed_neo4j()
    print_test_info()


if __name__ == "__main__":
    main()
