A. SSE 스트리밍 클라이언트

  // hooks/useChatStream.ts
  import { useState, useCallback } from 'react';

  interface StreamToken {
    type: 'token' | 'sources' | 'done' | 'error';
    content?: string;
    sources?: SourceChunk[];
    error?: string;
  }

  export const useChatStream = () => {
    const [streaming, setStreaming] = useState(false);
    const [response, setResponse] = useState('');
    const [sources, setSources] = useState<SourceChunk[]>([]);

    const sendMessage = useCallback(async (
      message: string,
      projectId: string,
      userId: string
    ) => {
      setStreaming(true);
      setResponse('');
      setSources([]);

      try {
        const response = await fetch('http://localhost:8000/api/chat/stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
          },
          body: JSON.stringify({
            message,
            project_id: projectId,
            user_id: userId,
          }),
        });

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        while (reader) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = JSON.parse(line.slice(6)) as StreamToken;

              if (data.type === 'token') {
                setResponse(prev => prev + data.content);
              } else if (data.type === 'sources') {
                setSources(data.sources || []);
              } else if (data.type === 'done') {
                setStreaming(false);
              } else if (data.type === 'error') {
                console.error('Stream error:', data.error);
                setStreaming(false);
              }
            }
          }
        }
      } catch (error) {
        console.error('Chat stream error:', error);
        setStreaming(false);
      }
    }, []);

    return { streaming, response, sources, sendMessage };
  };

  B. 에디터 저장 API 호출

  // services/editorService.ts
  import { apiClient } from '@/api/client';

  export const saveEditorContent = async (
    chunkUuid: string,
    content: string,
    projectId: string,
    userId: string,
    metadata?: Record<string, any>
  ) => {
    const response = await apiClient.post('/api/editor/save', {
      chunk_uuid: chunkUuid,
      content,
      project_id: projectId,
      user_id: userId,
      metadata,
    });

    return response.data;
  };

  // 자동 저장 훅
  export const useAutoSave = (projectId: string, userId: string) => {
    const [saving, setSaving] = useState(false);

    const autoSave = useCallback(
      debounce(async (chunkUuid: string, content: string) => {
        if (!content.trim()) return;

        setSaving(true);
        try {
          await saveEditorContent(chunkUuid, content, projectId, userId);
        } catch (error) {
          console.error('Auto-save failed:', error);
        } finally {
          setSaving(false);
        }
      }, 2000), // 2초 디바운스
      [projectId, userId]
    );

    return { autoSave, saving };
  };

  C. 챗봇 UI 컴포넌트

  // components/ChatPanel.tsx
  import { useState } from 'react';
  import { useChatStream } from '@/hooks/useChatStream';
  import { Button } from '@/components/ui/button';
  import { Textarea } from '@/components/ui/textarea';

  interface ChatPanelProps {
    projectId: string;
    userId: string;
  }

  export const ChatPanel = ({ projectId, userId }: ChatPanelProps) => {
    const [message, setMessage] = useState('');
    const { streaming, response, sources, sendMessage } = useChatStream();

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      if (!message.trim() || streaming) return;

      await sendMessage(message, projectId, userId);
      setMessage('');
    };

    return (
      <div className="flex flex-col h-full">
        {/* 응답 영역 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {response && (
            <div className="bg-cloud-50 rounded-lg p-4">
              <div className="prose prose-sm max-w-none">
                {response}
                {streaming && (
                  <span className="inline-block w-2 h-4 bg-mocha-500 animate-pulse ml-1" />
                )}
              </div>

              {/* 출처 표시 */}
              {sources.length > 0 && (
                <div className="mt-4 pt-4 border-t border-mocha-200">
                  <p className="text-xs text-espresso-900 font-medium mb-2">
                    참고한 내용:
                  </p>
                  {sources.map((source, idx) => (
                    <div key={source.chunk_uuid} className="text-xs text-espresso-700 mb-1">
                      [{idx + 1}] {source.content.slice(0, 100)}...
                      <span className="text-mocha-500 ml-1">
                        (관련도: {(source.similarity_score * 100).toFixed(0)}%)
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 입력 영역 */}
        <form onSubmit={handleSubmit} className="p-4 border-t border-mocha-200">
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="작품에 대해 질문해보세요..."
            disabled={streaming}
            className="mb-2"
          />
          <Button type="submit" disabled={streaming || !message.trim()}>
            {streaming ? '응답 생성 중...' : '전송'}
          </Button>
        </form>
      </div>
    );
  };

  2. 에디터 통합

  // components/editor/TiptapEditor.tsx
  import { useEditor } from '@tiptap/react';
  import { useAutoSave } from '@/services/editorService';

  export const TiptapEditor = ({ documentId, projectId, userId }) => {
    const { autoSave, saving } = useAutoSave(projectId, userId);

    const editor = useEditor({
      extensions: [/* ... */],
      content: '',
      onUpdate: ({ editor }) => {
        const content = editor.getText();
        autoSave(documentId, content);
      },
    });

    return (
      <div>
        {saving && <span className="text-xs text-mocha-500">저장 중...</span>}
        <EditorContent editor={editor} />
      </div>
    );
  };

  3. 백엔드 추가 구현 필요

  A. 인증/권한 미들웨어

  # app/middleware/auth.py (추가 필요)
  from fastapi import HTTPException, Depends
  from fastapi.security import HTTPBearer

  security = HTTPBearer()

  async def verify_token(credentials = Depends(security)):
      # JWT 토큰 검증 로직
      # StoLink 기존 인증 시스템과 연동
      pass

  async def get_current_user(token = Depends(verify_token)):
      # 현재 사용자 정보 추출
      pass

  B. 프로젝트 권한 체크

  # app/dependencies/permissions.py (추가 필요)
  from app.middleware.auth import get_current_user

  async def check_project_access(
      project_id: str,
      user = Depends(get_current_user)
  ):
      # 사용자가 해당 프로젝트에 접근 권한이 있는지 확인
      # Spring Boot 백엔드 API 호출
      pass

  C. 에러 핸들링 개선

  # app/middleware/error_handler.py (추가 필요)
  from fastapi import Request
  from fastapi.responses import JSONResponse

  @app.exception_handler(Exception)
  async def global_exception_handler(request: Request, exc: Exception):
      logger.error(f"Unhandled error: {exc}", exc_info=True)
      return JSONResponse(
          status_code=500,
          content={
              "error": "internal_server_error",
              "message": "죄송합니다. 오류가 발생했습니다."
          }
      )

  4. 인프라 추가 구현

  A. 모니터링 (선택)

  # docker-compose.yml에 추가
    # Flower - Celery 모니터링
    flower:
      build: .
      command: celery -A app.celery_app flower --port=5555
      ports:
        - "5555:5555"
      environment:
        - CELERY_BROKER_URL=redis://redis:6379/0
      depends_on:
        - redis

  B. 로깅 개선

  # app/config.py에 추가
  import logging
  from logging.handlers import RotatingFileHandler

  def setup_logging():
      handler = RotatingFileHandler(
          'logs/app.log',
          maxBytes=10485760,  # 10MB
          backupCount=10
      )
      handler.setFormatter(logging.Formatter(
          '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
      ))
      logging.getLogger().addHandler(handler)

  5. 테스트 코드

  # tests/test_chat.py (추가 필요)
  import pytest
  from fastapi.testclient import TestClient
  from app.main import app

  client = TestClient(app)

  def test_chat_stream():
      response = client.post(
          "/api/chat/stream",
          json={
              "message": "테스트 질문",
              "project_id": "test-project",
              "user_id": "test-user"
          },
          headers={"Accept": "text/event-stream"}
      )
      assert response.status_code == 200

  📝 implementation_plan.md 수정 필요

  RabbitMQ → Redis로 변경:

  # implementation_plan.md 업데이트가 필요합니다
  sed -i 's/RabbitMQ/Redis/g' implementation_plan.md

  구현하시겠습니까?

> package com.stolink.backend.domain.character.entity;

import com.stolink.backend.domain.project.entity.Project;
import com.stolink.backend.global.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.*;

import java.util.UUID;

/**
 * AI 서버 호환용 캐릭터 엔티티 (PostgreSQL)
 * AI 서버가 character 테이블을 조회하므로 추가함.
 */
@Entity
@Table(name = "characters")
@Getter
@Setter
@Builder
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
public class CharacterEntity extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "project_id", nullable = false)
    private Project project;

    // AI 생성 ID (예: char-세라-001)
    @Column(name = "character_id", length = 100)
    private String characterId;

    @Column(nullable = false, length = 100)
    private String name;

    @Column(length = 50)
    private String role; // protagonist, antagonist, etc.

    @Column(length = 50)
    private String status; // alive, dead, unknown, active

    // Profile fields
    @Column
    private Integer age;

    @Column(length = 30)
    private String gender;

    @Column(length = 50)
    private String race;

    @Column(length = 10)
    private String mbti;

    @Column(columnDefinition = "TEXT")
    private String backstory;

    @Column(length = 100)
    private String faction;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Column(name = "image_url", length = 500)
    private String imageUrl;

    // JSON fields for complex objects
    @Column(name = "aliases_json", columnDefinition = "TEXT")
    private String aliasesJson;

    @Column(name = "profile_json", columnDefinition = "TEXT")
    private String profileJson;

    @Column(name = "appearance_json", columnDefinition = "TEXT")
    private String appearanceJson;

    @Column(name = "visual_json", columnDefinition = "TEXT")
    private String visualJson;

    @Column(name = "personality_json", columnDefinition = "TEXT")
    private String personalityJson;

    @Column(name = "relations_json", columnDefinition = "TEXT")
    private String relationsJson;

    @Column(name = "current_mood_json", columnDefinition = "TEXT")
    private String currentMoodJson;

    @Column(name = "meta_json", columnDefinition = "TEXT")
    private String metaJson;

    @Column(name = "embedding_json", columnDefinition = "TEXT")
    private String embeddingJson;

    @Column(name = "motivation", columnDefinition = "TEXT")
    private String motivation;

    @Column(name = "inventory_json", columnDefinition = "TEXT")
    private String inventoryJson;

    @Column(name = "first_appearance", length = 255)
    private String firstAppearance;
}
 이건 스프링의 캐릭터 엔티티이고,package com.stolink.backend.domain.document.entity;

import com.stolink.backend.domain.project.entity.Project;
import com.stolink.backend.global.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.*;

import java.util.UUID;

@Entity
@Table(name = "documents")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Document extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "project_id", nullable = false)
    private Project project;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "parent_id")
    private Document parent;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private DocumentType type;

    @Column(nullable = false)
    private String title;

    @Column(columnDefinition = "TEXT")
    private String content = "";

    @Column(columnDefinition = "TEXT")
    private String synopsis = "";

    @Column(name = "\"order\"", nullable = false)
    private Integer order = 0;

    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private DocumentStatus status = DocumentStatus.DRAFT;

    // AI 분석 상태 (대용량 문서 분석 아키텍처)
    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private AnalysisStatus analysisStatus = AnalysisStatus.NONE;

    @Column
    private Integer analysisRetryCount = 0;

    @Column(length = 50)
    private String label;

    @Column(length = 7)
    private String labelColor;

    @Column(nullable = false)
    private Integer wordCount = 0;

    private Integer targetWordCount;

    @Column(nullable = false)
    private Boolean includeInCompile = true;

    @Column(columnDefinition = "text")
    private String keywords; // Comma-separated tags

    @Column(columnDefinition = "TEXT")
    private String notes;

    @Builder
    public Document(UUID id, Project project, Document parent, DocumentType type, String title, String content,
            String synopsis, Integer order, DocumentStatus status, String label, String labelColor, Integer wordCount,
            Integer targetWordCount, Boolean includeInCompile, String keywords, String notes) {
        this.id = id;
        this.project = project;
        this.parent = parent;
        this.type = type;
        this.title = title;
        this.content = content;
        this.synopsis = synopsis;
        this.order = order;
        this.status = status;
        this.label = label;
        this.labelColor = labelColor;
        this.wordCount = wordCount;
        this.targetWordCount = targetWordCount;
        this.includeInCompile = includeInCompile;
        this.keywords = keywords;
        this.notes = notes;
    }

    public void updateContent(String content) {
        this.content = content;
        this.wordCount = calculateWordCount(content);
    }

    public void update(String title, String synopsis, Integer order, DocumentStatus status,
            Integer targetWordCount, Boolean includeInCompile, String notes) {
        if (title != null)
            this.title = title;
        if (synopsis != null)
            this.synopsis = synopsis;
        if (order != null)
            this.order = order;
        if (status != null)
            this.status = status;
        if (targetWordCount != null)
            this.targetWordCount = targetWordCount;
        if (includeInCompile != null)
            this.includeInCompile = includeInCompile;
        if (notes != null)
            this.notes = notes;
    }

    public void updateLabel(String label, String labelColor) {
        if (label != null)
            this.label = label;
        if (labelColor != null)
            this.labelColor = labelColor;
    }

    public void updateKeywords(String keywords) {
        this.keywords = keywords;
    }

    /**
     * 문서의 부모를 변경합니다 (폴더 이동)
     * 
     * @param newParent 새로운 부모 문서 (null이면 루트로 이동)
     * @param newOrder  새 부모 아래에서의 순서
     */
    public void updateParent(Document newParent, int newOrder) {
        this.parent = newParent;
        this.order = newOrder;
    }

    private int calculateWordCount(String text) {
        if (text == null || text.isEmpty()) {
            return 0;
        }
        // Simple word count - can be enhanced
        return text.replaceAll("<[^>]*>", "").trim().length();
    }

    public enum DocumentType {
        FOLDER, TEXT
    }

    public enum DocumentStatus {
        DRAFT, REVISED, FINAL
    }

    /**
     * AI 분석 상태 (대용량 문서 분석 아키텍처)
     */
    public enum AnalysisStatus {
        NONE, // 분석 요청 전
        PENDING, // 분석 대기
        QUEUED, // RabbitMQ 발행됨
        PROCESSING, // Python 처리 중
        COMPLETED, // 분석 완료
        FAILED // 분석 실패
    }

    // === 분석 상태 관리 메서드 ===

    public void updateAnalysisStatus(AnalysisStatus status) {
        this.analysisStatus = status;
    }

    public void incrementRetryCount() {
        this.analysisRetryCount++;
    }

    public void resetAnalysisForRetry() {
        this.analysisStatus = AnalysisStatus.QUEUED;
        this.analysisRetryCount++;
    }
}
이건 도큐먼트 엔티티야. 참고해서 구현 시작 