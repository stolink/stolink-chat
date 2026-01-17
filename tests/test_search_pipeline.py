"""검색 파이프라인 테스트.

실행: python tests/test_search_pipeline.py
"""

import sys
sys.path.insert(0, '.')

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_search_pipeline():
    """검색 파이프라인 테스트."""
    from app.services.embedding_service import embedding_service
    from app.services.unified_search_service import unified_search_service
    from app.services.postgres_service import postgres_service
    from app.services.neo4j_service import neo4j_service

    print("=" * 60)
    print("검색 파이프라인 테스트")
    print("=" * 60)

    # PostgreSQL 초기화
    await postgres_service.initialize()

    # 1. 테스트할 프로젝트 ID 찾기
    print("\n📁 테스트할 프로젝트 ID 확인:")
    import asyncpg
    from app.config import settings

    conn = await asyncpg.connect(settings.postgres_dsn)
    projects = await conn.fetch("""
        SELECT DISTINCT d.project_id, COUNT(*) as section_count
        FROM sections s
        JOIN documents d ON s.document_id = d.id
        WHERE s.embedding IS NOT NULL
        GROUP BY d.project_id
    """)
    await conn.close()

    if not projects:
        print("  ❌ sections에 데이터가 없습니다.")
        return

    test_project_id = str(projects[0]['project_id'])
    print(f"  - 프로젝트 ID: {test_project_id}")
    print(f"  - sections 수: {projects[0]['section_count']}")

    # 2. 테스트 쿼리
    test_queries = [
        "주인공은 누구야?",
        "이 소설의 배경은 어디야?",
        "등장인물 소개해줘"
    ]

    for query in test_queries:
        print(f"\n🔍 테스트 쿼리: \"{query}\"")
        print("-" * 40)

        # 3. 임베딩 생성
        try:
            query_embedding = embedding_service.get_embedding(query)
            print(f"  ✅ 임베딩 생성 완료 ({len(query_embedding)} dims)")
        except Exception as e:
            print(f"  ❌ 임베딩 생성 실패: {e}")
            continue

        # 4. 통합 검색
        try:
            results = await unified_search_service.search(
                project_id=test_project_id,
                query_embedding=query_embedding,
                query_text=query
            )

            sections = results.get("sections", [])
            characters = results.get("characters", [])
            events = results.get("events", [])

            print(f"\n  📊 검색 결과:")
            print(f"    - sections: {len(sections)}개")
            print(f"    - characters: {len(characters)}개")
            print(f"    - events: {len(events)}개")

            # 상세 결과 출력
            if sections:
                print(f"\n  📄 Sections 상세:")
                for s in sections[:2]:
                    print(f"    - [{s.get('nav_title', 'N/A')}] score={s.get('score', 0):.3f}")
                    print(f"      {s['content'][:100]}...")

            if characters:
                print(f"\n  👤 Characters 상세:")
                for c in characters[:2]:
                    print(f"    - {c.get('name', 'N/A')} ({c.get('role', 'N/A')})")

        except Exception as e:
            print(f"  ❌ 검색 실패: {e}")
            import traceback
            traceback.print_exc()

    # 정리
    await postgres_service.close()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(test_search_pipeline())
