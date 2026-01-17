"""PostgreSQL 데이터 상태 확인 스크립트.

실행: python tests/check_postgres_data.py
"""

import sys
sys.path.insert(0, '.')

import asyncio
from app.config import settings


async def check_postgres_data():
    """PostgreSQL에 저장된 데이터 현황을 확인."""
    import asyncpg

    print("=" * 60)
    print("PostgreSQL 데이터 상태 확인")
    print("=" * 60)

    try:
        conn = await asyncpg.connect(settings.postgres_dsn)
    except Exception as e:
        print(f"❌ PostgreSQL 연결 실패: {e}")
        return

    try:
        # 1. 테이블 목록 확인
        print("\n📊 테이블 목록:")
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        for t in tables:
            print(f"  - {t['table_name']}")

        # 2. sections 테이블 확인
        print("\n📦 sections 테이블:")
        try:
            section_count = await conn.fetchval("SELECT COUNT(*) FROM sections")
            print(f"  - 전체 레코드: {section_count}개")

            if section_count > 0:
                # 임베딩 차원 확인
                embedding_info = await conn.fetchrow("""
                    SELECT
                        COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embedding,
                        AVG(array_length(embedding::float[], 1)) as avg_dimension
                    FROM sections
                """)
                print(f"  - 임베딩 있는 레코드: {embedding_info['with_embedding']}개")
                if embedding_info['avg_dimension']:
                    print(f"  - 임베딩 차원: {int(embedding_info['avg_dimension'])}")

                # 프로젝트별 분포
                projects = await conn.fetch("""
                    SELECT project_id, COUNT(*) as cnt
                    FROM sections
                    GROUP BY project_id
                    ORDER BY cnt DESC
                    LIMIT 5
                """)
                print(f"  - 프로젝트별 분포 (상위 5개):")
                for p in projects:
                    print(f"    · {p['project_id']}: {p['cnt']}개")

                # 샘플 데이터
                sample = await conn.fetchrow("""
                    SELECT section_id, nav_title,
                           LEFT(content, 100) as content_preview,
                           array_length(embedding::float[], 1) as emb_dim
                    FROM sections
                    WHERE embedding IS NOT NULL
                    LIMIT 1
                """)
                if sample:
                    print(f"\n  📄 샘플 데이터:")
                    print(f"    - ID: {sample['section_id']}")
                    print(f"    - 제목: {sample['nav_title']}")
                    print(f"    - 내용: {sample['content_preview']}...")
                    print(f"    - 임베딩 차원: {sample['emb_dim']}")
        except Exception as e:
            print(f"  - sections 테이블 조회 실패: {e}")

        # 3. characters 테이블 확인
        print("\n👤 characters 테이블:")
        try:
            char_count = await conn.fetchval("SELECT COUNT(*) FROM characters")
            print(f"  - 전체 레코드: {char_count}개")
        except Exception as e:
            print(f"  - characters 테이블 없음 또는 오류: {e}")

        # 4. events 테이블 확인
        print("\n📅 events 테이블:")
        try:
            event_count = await conn.fetchval("SELECT COUNT(*) FROM events")
            print(f"  - 전체 레코드: {event_count}개")
        except Exception as e:
            print(f"  - events 테이블 없음 또는 오류: {e}")

        # 5. chat_logs 테이블 확인
        print("\n💬 chat_logs 테이블:")
        try:
            log_count = await conn.fetchval("SELECT COUNT(*) FROM chat_logs")
            print(f"  - 전체 레코드: {log_count}개")
        except Exception as e:
            print(f"  - chat_logs 테이블 없음 또는 오류: {e}")

    finally:
        await conn.close()

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(check_postgres_data())
