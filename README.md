# StoLink Graph RAG Chat Service

실시간 Graph RAG 기반 챗봇 백엔드 서비스입니다. 소설 작가가 작성하는 콘텐츠를 Neo4j에 저장하고, 프로젝트별로 맞춤화된 AI 답변을 SSE 스트리밍 방식으로 제공합니다.

## 🏗️ 아키텍처

```
Editor Content → FastAPI → Redis/Celery → Embedding → Neo4j
User Question → FastAPI → Neo4j Search → OpenAI SSE Stream → Response
```

### 주요 기술 스택

- **FastAPI**: 비동기 웹 프레임워크
- **Celery + Redis**: 백그라운드 임베딩 처리
- **Neo4j**: 벡터 검색을 지원하는 그래프 데이터베이스
- **OpenAI API**: 임베딩 생성 및 챗봇 응답 (SSE 스트리밍)
- **Python 3.11**: 최신 파이썬 런타임

## 📋 사전 요구사항

- Docker & Docker Compose
- 기존 Neo4j 컨테이너 (`stolink-neo4j-local`)
- OpenAI API 키

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# 필수 환경변수 설정
nano .env
```

**필수 환경변수:**
```bash
NEO4J_PASSWORD=your_neo4j_password
OPENAI_API_KEY=sk-your-openai-api-key
```

### 2. Docker 네트워크 설정

기존 Neo4j 컨테이너를 공유 네트워크에 연결합니다:

```bash
# 네트워크 생성 (없는 경우)
docker network create stolink-network

# 기존 Neo4j 컨테이너를 네트워크에 연결
docker network connect stolink-network stolink-neo4j-local
```

### 3. 서비스 시작

```bash
# 서비스 빌드 및 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

### 4. 헬스 체크

```bash
curl http://localhost:8000/health
```

**응답 예시:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-03T10:00:00",
  "services": {
    "neo4j": "healthy",
    "celery": "healthy",
    "redis": "healthy"
  }
}
```

## 📚 API 문서

서비스 실행 후 다음 URL에서 자동 생성된 API 문서를 확인할 수 있습니다:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 주요 엔드포인트

#### 1. 에디터 콘텐츠 저장

```bash
POST /api/editor/save
```

**요청 예시:**
```bash
curl -X POST http://localhost:8000/api/editor/save \
  -H "Content-Type: application/json" \
  -d '{
    "chunk_uuid": "chunk-001",
    "content": "홍길동은 조선시대의 의적이다. 탐관오리를 징벌하고 가난한 백성을 도왔다.",
    "project_id": "project-001",
    "user_id": "user-001",
    "metadata": {"chapter": "1", "scene": "opening"}
  }'
```

**응답:**
```json
{
  "status": "accepted",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Content accepted for processing"
}
```

#### 2. 챗봇 스트리밍 (SSE)

```bash
POST /api/chat/stream
```

**요청 예시:**
```bash
curl -N -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "message": "홍길동은 누구인가요?",
    "project_id": "project-001",
    "user_id": "user-001"
  }'
```

**SSE 응답 스트림:**
```
data: {"type": "sources", "sources": [{"chunk_uuid": "chunk-001", "content": "...", "similarity_score": 0.89}]}

data: {"type": "token", "content": "홍"}

data: {"type": "token", "content": "길"}

data: {"type": "token", "content": "동"}

data: {"type": "token", "content": "은"}

...

data: {"type": "done", "message": "Stream completed"}
```

#### 3. 챗봇 일반 응답 (비스트리밍)

```bash
POST /api/chat
```

**요청 예시:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "홍길동의 성격은?",
    "project_id": "project-001",
    "user_id": "user-001"
  }'
```

#### 4. 태스크 상태 확인

```bash
GET /api/editor/task/{task_id}
```

## 🔧 개발 모드

### 로컬 개발 환경

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# FastAPI 개발 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Celery 워커 실행 (별도 터미널)
celery -A app.celery_app worker --loglevel=info
```

## 🗂️ 프로젝트 구조

```
sto-link-chat/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 진입점
│   ├── celery_app.py        # Celery 설정 및 태스크
│   ├── config.py            # 환경 설정
│   ├── routers/
│   │   ├── editor.py        # 에디터 저장 API
│   │   └── chat.py          # 챗봇 API (SSE)
│   ├── services/
│   │   ├── neo4j_service.py # Neo4j 연동
│   │   ├── embedding_service.py # OpenAI 임베딩
│   │   └── chat_service.py  # 챗봇 응답 생성
│   └── models/
│       └── schemas.py       # Pydantic 스키마
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## 🧪 테스트

### Neo4j 데이터 확인

Neo4j Browser에서 확인:
- URL: http://localhost:7474
- 로그인: neo4j / {your_password}

**쿼리 예시:**
```cypher
// 저장된 청크 확인
MATCH (c:Chunk {project_id: "project-001"})
RETURN c
LIMIT 10

// 벡터 인덱스 확인
SHOW INDEXES
```

### Redis 모니터링

```bash
# Redis CLI 접속
docker exec -it stolink-chat-redis redis-cli

# 큐 확인
KEYS *
LLEN celery
```

## 🐛 트러블슈팅

### Neo4j 연결 실패

```bash
# Neo4j 컨테이너 상태 확인
docker ps | grep neo4j

# 네트워크 연결 확인
docker network inspect stolink-network
```

### Celery 워커 동작 안 함

```bash
# 워커 로그 확인
docker-compose logs celery-worker

# Redis 연결 확인
docker exec -it stolink-chat-redis redis-cli ping
```

### OpenAI API 에러

- API 키가 올바른지 확인
- API 사용량 한도 확인
- 네트워크 방화벽 설정 확인

## 📊 성능 최적화

### Celery 동시성 조정

```yaml
# docker-compose.yml
celery-worker:
  command: celery -A app.celery_app worker --loglevel=info --concurrency=4
```

### Neo4j 벡터 인덱스 최적화

```cypher
// 인덱스 통계 확인
CALL db.index.vector.queryNodes('chunk_embedding', 10, [/* test vector */])
```

## 🔒 보안 고려사항

- `.env` 파일을 `.gitignore`에 추가
- API 키는 환경변수로만 관리
- 프로덕션에서는 HTTPS 사용
- CORS 설정을 프로덕션 도메인으로 제한

## 📝 라이센스

이 프로젝트는 StoLink 프로젝트의 일부입니다.

## 🤝 기여

이슈 및 PR은 언제나 환영합니다!

## 📞 문의

프로젝트 관련 문의사항은 이슈로 남겨주세요.
# stolink-chat
