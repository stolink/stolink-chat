"""일관성 검증 서비스.

Agent가 생성한 consistency_reports를 활용하여
작가에게 설정 충돌, 경고, 개선 제안을 제공합니다.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from app.services.postgres_service import postgres_service

logger = logging.getLogger(__name__)


@dataclass
class ConflictInfo:
    """설정 충돌 정보."""
    type: str
    severity: str  # HIGH, MEDIUM, LOW
    source: str
    existing: str
    new_value: str
    description: str = ""
    suggestion: str = ""


@dataclass
class ConsistencyReport:
    """일관성 검증 리포트."""
    id: str
    project_id: str
    overall_score: int
    conflicts: List[ConflictInfo] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    high_severity_count: int = 0
    needs_human_review: int = 0
    created_at: Optional[datetime] = None


class ConsistencyService:
    """일관성 검증 및 알림 서비스.

    프로젝트의 설정 충돌을 감지하고 작가에게 알립니다.
    """

    async def get_project_consistency(
        self,
        project_id: str,
        limit: int = 5
    ) -> List[ConsistencyReport]:
        """프로젝트의 최근 일관성 리포트 조회.

        Args:
            project_id: 프로젝트 ID
            limit: 조회할 리포트 수

        Returns:
            ConsistencyReport 리스트
        """
        if not postgres_service.pool:
            logger.warning("PostgreSQL pool not available")
            return []

        sql = """
            SELECT id, project_id, overall_score, conflicts_json,
                   warnings_json, high_severity_count,
                   requires_human_review_count, created_at
            FROM consistency_reports
            WHERE project_id = $1::uuid
            ORDER BY created_at DESC
            LIMIT $2
        """

        try:
            async with postgres_service.pool.acquire() as conn:
                rows = await conn.fetch(sql, project_id, limit)

                reports = []
                for row in rows:
                    conflicts = self._parse_conflicts(row["conflicts_json"])
                    warnings = self._parse_warnings(row["warnings_json"])

                    reports.append(ConsistencyReport(
                        id=str(row["id"]),
                        project_id=str(row["project_id"]),
                        overall_score=row["overall_score"] or 100,
                        conflicts=conflicts,
                        warnings=warnings,
                        high_severity_count=row["high_severity_count"] or len([c for c in conflicts if c.severity == "HIGH"]),
                        needs_human_review=row["requires_human_review_count"] or 0,
                        created_at=row["created_at"]
                    ))

                return reports

        except Exception as e:
            logger.error(f"Consistency report query failed: {e}")
            return []

    def _parse_conflicts(self, conflicts_json: str) -> List[ConflictInfo]:
        """충돌 JSON 파싱."""
        if not conflicts_json:
            return []

        try:
            conflicts_data = json.loads(conflicts_json)
            conflicts = []

            for c in conflicts_data:
                conflicts.append(ConflictInfo(
                    type=c.get("type", "UNKNOWN"),
                    severity=c.get("severity", "MEDIUM"),
                    source=c.get("source", ""),
                    existing=c.get("existing", ""),
                    new_value=c.get("change", c.get("new", "")),
                    description=c.get("description", ""),
                    suggestion=c.get("suggestion", "")
                ))

            return conflicts
        except Exception as e:
            logger.error(f"Failed to parse conflicts: {e}")
            return []

    def _parse_warnings(self, warnings_json: str) -> List[str]:
        """경고 JSON 파싱."""
        if not warnings_json:
            return []

        try:
            return json.loads(warnings_json)
        except:
            return []

    async def get_relevant_conflicts(
        self,
        project_id: str,
        query: str,
        character_names: List[str] = None
    ) -> List[ConflictInfo]:
        """쿼리와 관련된 충돌만 필터링.

        Args:
            project_id: 프로젝트 ID
            query: 사용자 쿼리
            character_names: 관련 캐릭터 이름 리스트

        Returns:
            관련된 충돌 리스트
        """
        reports = await self.get_project_consistency(project_id, limit=3)

        if not reports:
            return []

        relevant_conflicts = []
        query_lower = query.lower()
        char_names_lower = [n.lower() for n in (character_names or [])]

        for report in reports:
            for conflict in report.conflicts:
                # 쿼리 키워드 매칭
                existing_text = (conflict.existing or "").lower()
                new_text = (conflict.new_value or "").lower()

                if any(keyword in existing_text or keyword in new_text
                       for keyword in query_lower.split()):
                    relevant_conflicts.append(conflict)
                    continue

                # 캐릭터 이름 매칭
                if char_names_lower:
                    if any(name in existing_text or
                           name in new_text
                           for name in char_names_lower):
                        relevant_conflicts.append(conflict)

        return relevant_conflicts

    def format_conflicts_for_prompt(
        self,
        conflicts: List[ConflictInfo],
        warnings: List[str] = None
    ) -> str:
        """충돌 정보를 프롬프트용 텍스트로 포맷.

        Args:
            conflicts: 충돌 리스트
            warnings: 경고 리스트

        Returns:
            포맷된 텍스트
        """
        if not conflicts and not warnings:
            return ""

        parts = []

        if conflicts:
            parts.append("감지된 설정 충돌:")
            for i, c in enumerate(conflicts[:5], 1):
                parts.append(f"{i}. [{c.type}]")
                if c.existing:
                    parts.append(f"   기존: {c.existing[:100]}")
                if c.new_value:
                    parts.append(f"   변경: {c.new_value[:100]}")
                if c.suggestion:
                    parts.append(f"   제안: {c.suggestion}")

        if warnings:
            parts.append("\n경고사항:")
            for w in warnings[:3]:
                parts.append(f"- {w[:150]}")

        return "\n".join(parts)

    def format_conflicts_for_response(
        self,
        conflicts: List[ConflictInfo]
    ) -> Dict[str, Any]:
        """클라이언트 응답용 충돌 정보 포맷.

        Args:
            conflicts: 충돌 리스트

        Returns:
            SSE 이벤트용 딕셔너리
        """
        if not conflicts:
            return None

        return {
            "type": "consistency",
            "data": {
                "hasConflicts": True,
                "count": len(conflicts),
                "highSeverity": len([c for c in conflicts if c.severity == "HIGH"]),
                "conflicts": [
                    {
                        "type": c.type,
                        "severity": c.severity,
                        "existing": c.existing[:200] if c.existing else None,
                        "newValue": c.new_value[:200] if c.new_value else None,
                        "suggestion": c.suggestion
                    }
                    for c in conflicts[:5]
                ]
            }
        }

    async def check_character_consistency(
        self,
        project_id: str,
        character_name: str
    ) -> Dict[str, Any]:
        """특정 캐릭터 관련 일관성 체크.

        Args:
            project_id: 프로젝트 ID
            character_name: 캐릭터 이름

        Returns:
            캐릭터 일관성 정보
        """
        conflicts = await self.get_relevant_conflicts(
            project_id, character_name, [character_name]
        )

        character_conflicts = [c for c in conflicts if "CHARACTER" in c.type.upper()]

        return {
            "character_name": character_name,
            "has_conflicts": len(character_conflicts) > 0,
            "conflict_count": len(character_conflicts),
            "conflicts": character_conflicts,
            "is_consistent": len(character_conflicts) == 0
        }


# 싱글톤 인스턴스
consistency_service = ConsistencyService()
