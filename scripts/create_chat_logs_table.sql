-- chat_logs 테이블 생성 DDL
-- 챗봇 대화 로그 영구 저장용

CREATE TABLE IF NOT EXISTS chat_logs (
    id BIGSERIAL PRIMARY KEY,
    
    -- 식별 정보
    project_id UUID NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(100),
    
    -- 대화 내용
    role VARCHAR(20) NOT NULL,          -- 'user' or 'ai'
    content TEXT NOT NULL,
    
    -- 메타데이터
    sources_json JSONB,                 -- AI 응답 시 참조한 소스 정보
    
    -- 타임스탬프
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 성능 최적화 인덱스
CREATE INDEX IF NOT EXISTS idx_chat_logs_project ON chat_logs(project_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_session ON chat_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_user ON chat_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_logs_created ON chat_logs(created_at DESC);

-- 복합 인덱스 (특정 프로젝트의 특정 세션 조회용)
CREATE INDEX IF NOT EXISTS idx_chat_logs_project_session ON chat_logs(project_id, session_id);

COMMENT ON TABLE chat_logs IS '챗봇 대화 로그 영구 저장 테이블';
COMMENT ON COLUMN chat_logs.role IS 'user 또는 ai';
COMMENT ON COLUMN chat_logs.sources_json IS 'AI 응답 생성 시 참조한 RAG 소스 정보';
