# CLAUDE.md - StoLink Chatbot Service Constitution

> 이 문서는 AI 모델이 프로젝트 컨텍스트를 이해하고, Python 기반 챗봇 서비스의 코드 품질을 유지하기 위한 **프로젝트 헌법(Constitution)**입니다.

**버전:** 1.1
**최종 수정:** 2026년 1월 3일
**문서 상태:** 활성 (Updated)

---

<project_info>
<description>
StoLink Chatbot - 소설 창작을 지원하는 Graph RAG 기반 AI 서비스
사용자가 작성한 소설 내용을 실시간으로 벡터화하여 Neo4j와 PostgreSQL에 저장하고, 맥락을 이해하는 챗봇 응답을 제공합니다.
Spring Boot 메인 백엔드와 별도로 동작하는 독립적인 Python-Native 마이크로서비스입니다.
</description>

<tech_stack>

- **Language**: Python 3.10+
- **Web Framework**: FastAPI (Async)
- **Background Processing**: FastAPI BackgroundTasks
- **Database**:
  - Neo4j 5.x (Graph + Vector Index)
  - PostgreSQL + pgvector (Sentence Vector Index)
- **Cache/Messaging**: Redis 7.0 (Chat History, Pub/Sub)
- **AI/LLM**: OpenAI (GPT-4o-mini), LangChain 0.3
- **Deployment**: Docker Compose
  </tech_stack>

<architecture>
**Event-Driven RAG Pipeline**
1. **Ingest**: Frontend → FastAPI (`/api/editor/save`) → FastAPI BackgroundTasks → OpenAI Embedding → Neo4j Storage (Chunk Node)
2. **Retrieval**: Frontend → FastAPI (`/api/chat/stream`) → Hybrid Search (Neo4j Chunk + Postgres Sentence) → GPT-4o Generation → SSE Response
</architecture>
</project_info>

---

<coding_rules>
<python>

- **MUST**: Type Hints (PEP 484) 필수 사용. 모든 함수 파라미터와 리턴 타입 명시.
- **MUST**: Pydantic 모델을 사용한 데이터 검증 및 스키마 정의 (`app/models/`).
- **MUST**: 비동기 (`async/await`) 처리 원칙. I/O 바운드 작업은 `await` 사용.
- **MUST**: Docstring 규약 준수 (Google Style).
- **SHOULD**: 포맷터는 `black`, 린터는 `flake8` 또는 `ruff` 기준.
  </python>

<fastapi>
- **MUST**: 의존성 주입 (`Depends`) 적극 활용 (인증, DB 세션 등).
- **MUST**: API 라우터는 `app/routers/` 폴더에 분리.
- **MUST**: 요청/응답 스키마는 `app/models/schemas.py`에 정의.
- **MUST**: 에러 처리는 `HTTPException` 또는 커스텀 핸들러 사용.
</fastapi>

<database>
- **MUST**: 벡터 검색 및 그래프 쿼리는 `app/services/` 내 전용 서비스 클래스(`neo4j_service.py`, `postgres_service.py`)에 캡슐화.
- **MUST**: Cypher 및 SQL 쿼리 내 하드코딩 지양, 파라미터 바인딩 사용.
- **MUST**: 통합 검색 로직은 `unified_search_service.py`를 통해 수행.
</database>

<neo4j>
- **SHOULD**: `Chunk` 노드는 `uuid`, `content`, `project_id`, `embedding` 속성을 가짐.
</neo4j>
</coding_rules>

---

<file_structure>

```
sto-link-chat/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 앱 진입점 (CORS, 미들웨어)
│   ├── config.py            # 환경 설정 (Pydantic Settings)
│   ├── middleware/          # 인증, 에러 핸들링 미들웨어
│   ├── dependencies/        # 권한 체크 등 의존성 함수
│   ├── models/              # Pydantic 데이터 모델
│   │   └── schemas.py       # API 요청/응답 스키마
│   ├── routers/             # API 엔드포인트
│   │   ├── editor.py        # 에디터 데이터 수신 (BackgroundTasks)
│   │   └── chat.py          # 챗봇 스트리밍
│   └── services/            # 비즈니스 로직
│       ├── neo4j_service.py # Graph DB 연동
│       ├── postgres_service.py # PostgreSQL (pgvector) 연동
│       ├── unified_search_service.py # Hybrid Search 로직
│       ├── embedding_service.py # OpenAI 임베딩
│       ├── redis_service.py # Redis Chat History & Pub/Sub
│       └── chat_service.py  # RAG 로직 및 프롬프트
├── tests/                   # Pytest 테스트 코드
├── docker-compose.yml       # 인프라 구성 (Redis, App)
├── Dockerfile               # Python 앱 이미지
└── requirements.txt         # 의존성 목록
```

</file_structure>

---

<commands>
| 명령어 | 설명 |
|---|---|
| `docker-compose up -d --build` | 전체 서비스 (재)빌드 및 실행 |
| `docker-compose ps` | 컨테이너 상태 확인 |
| `docker-compose logs -f [service]` | 로그 실시간 확인 (예: `fastapi`) |
| `uvicorn app.main:app --reload` | (로컬) FastAPI 개발 서버 실행 |
</commands>

---

<api_reference>

### Editor

- `POST /api/editor/save`: 소설 내용 저장 및 비동기 임베딩 요청
  - Body: `{ "chunk_uuid": str, "content": str, "project_id": str, ... }`
  - Note: 처리는 `BackgroundTasks`로 비동기 실행됨.

### Chat

- `POST /api/chat/stream`: RAG 기반 챗봇 스트리밍 응답 (SSE)
  - Body: `{ "message": str, "project_id": str, "history": [...] }`
  - Response: Server-Sent Events (`data: ...`)

### Management

- `GET /health`: 서버 상태 확인
- `GET /docs`: Swagger UI
  </api_reference>

---

<environment>
`.env` 파일 설정:
- `OPENAI_API_KEY`: 필수
- `NEO4J_URI`: `bolt://host.docker.internal:7687` (Docker 실행 시)
- `NEO4J_USER` / `NEO4J_PASSWORD`
- `REDIS_URL`: `redis://redis:6379/0`
- `POSTGRES_HOST`: `host.docker.internal`
- `POSTGRES_PORT`: `5432`
- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`: PGVector DB 설정
</environment>
