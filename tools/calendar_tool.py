from __future__ import annotations
from typing import Dict, Any, List
from urllib.parse import quote

#calendar 함수별 반환값 정리
"""
=== 주요 공개 함수들 ===
build_gcal_urls(item: Dict[str, Any]) -> List[Dict[str, Any]]
    - Google Calendar URL 생성 (단일/복수 일정 모두 처리)
    - 반환: url 필드가 추가된 schedule 배열
"""

def build_gcal_urls(item: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Google Calendar URL 생성 함수 (단일/복수 일정 모두 처리).
    schedule 배열의 각 항목에 url 필드를 추가하여 반환.
    
    Args:
        item: 공지사항 딕셔너리 (schedule 포함 형식)
    
    Returns:
        List[Dict[str, Any]]: url 필드가 추가된 schedule 배열
    """
    schedule = item.get("schedule", [])
    if not schedule:
        return []
    
    # schedule이 있으면 각 항목에 URL 추가
    result = []
    title = (item.get("title") or "제목 없음").strip()
    summary = (item.get("summary") or "").strip()
    
    for schedule_item in schedule:
        description = schedule_item.get("description", "").strip()
        date_str = schedule_item.get("date", "").strip()
        location = schedule_item.get("location", "").strip()
        
        if not date_str:
            continue
            
        # Google Calendar 형식으로 변환 (YYYYMMDD/YYYYMMDD)
        try:
            # "2025.09.04" -> "20250904/20250905"
            date_parts = date_str.replace(".", "-").split("-")
            if len(date_parts) == 3:
                year, month, day = map(int, date_parts)
                start_date = f"{year:04d}{month:02d}{day:02d}"
                end_date = f"{year:04d}{month:02d}{day+1:02d}"
                dates = f"{start_date}/{end_date}"
            else:
                continue
        except:
            continue
        
        event_title = f"{title} - {description}" if description else title
        
        lines = []
    
        if location:
            lines.append(f"[장소] {location}")
        if summary:
            if lines:
                lines.append("")
            lines.append(summary)
        
        details = "\n".join(lines)
        
        def enc(v: str, *, keep_slash=False) -> str:
            if v is None: return ""
            safe = "/T:-_." if keep_slash else "-_.~"
            return quote(v, safe=safe)
        
        query = [
            ("action", "TEMPLATE"),
            ("text", enc(event_title)),
            ("dates", enc(dates, keep_slash=True)),
            ("details", enc(details)),
            ("ctz", enc("Asia/Seoul")),
        ]
        qs = "&".join(f"{k}={v}" for k, v in query if v)
        gcal_url = f"https://calendar.google.com/calendar/render?{qs}"
        
        # 원본 항목에 url 필드 추가
        result_item = schedule_item.copy()
        result_item["url"] = gcal_url
        result.append(result_item)
    
    return result
