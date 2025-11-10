"""
AI 모듈용 제안/추천 엔진
다양한 상황에서 사용자에게 유용한 제안사항을 제공
"""

import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re

# Add parent directory to path to import utils module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logging_config import setup_logger

class SuggestionEngine:
    """AI 모듈 전반에서 사용할 수 있는 제안사항 생성 엔진"""
    
    def __init__(self):
        self.logger = setup_logger()
        self.logger.info("SuggestionEngine 초기화 완료")
    
    def generate_parsing_suggestions(self, parsed_data: Dict[str, Any]) -> List[str]:
        """파싱된 데이터 기반 제안사항 생성"""
        suggestions = []
        
        try:
            # 제목 관련 제안
            title = parsed_data.get('title', '')
            if '장학' in title:
                suggestions.append("💰 장학금 공지입니다. 자격요건을 꼼꼼히 확인해보세요")
            elif '취업' in title or '채용' in title:
                suggestions.append("💼 취업/채용 관련 공지입니다. 지원 자격과 마감일을 확인해보세요")
            elif '교환학생' in title or '해외' in title:
                suggestions.append("✈️ 국제교류 관련 공지입니다. 어학점수 요건을 미리 확인해보세요")
            
            # 일정 관련 제안
            schedules = parsed_data.get('schedule', [])
            if schedules:
                for schedule in schedules:
                    if '마감' in schedule.get('description', ''):
                        date_str = schedule.get('date', '')
                        suggestions.extend(self._generate_deadline_suggestions(date_str))
            else:
                suggestions.append("⏰ 일정 정보가 없습니다. 관련 부서에 문의하여 마감일을 확인해보세요")
            
            # 신청 방법 관련 제안
            application_method = parsed_data.get('application_method', '')
            if application_method:
                if '온라인' in application_method:
                    suggestions.append("🌐 온라인 신청 - 브라우저 호환성과 인터넷 연결을 확인해주세요")
                if '방문' in application_method:
                    suggestions.append("🚪 직접 방문 제출 - 운영시간과 필요 서류를 미리 준비해주세요")
                if '이메일' in application_method:
                    suggestions.append("📧 이메일 제출 - 파일 용량 제한과 첨부파일 형식을 확인해주세요")
            
            # 대상 관련 제안
            target = parsed_data.get('target', '')
            if target:
                if '학년' in target:
                    suggestions.append("🎓 학년 제한이 있습니다. 본인의 해당 여부를 확인해주세요")
                if '학과' in target:
                    suggestions.append("📚 특정 학과 대상입니다. 본인 학과의 해당 여부를 확인해주세요")
            
            # 중요사항 관련 제안
            important_notes = parsed_data.get('important_notes', '')
            if important_notes:
                if '정원' in important_notes:
                    suggestions.append("👥 모집 정원이 있습니다. 조기 신청을 권장합니다")
                if '서류' in important_notes:
                    suggestions.append("📋 필요 서류가 있습니다. 미리 준비해두시면 좋습니다")
                if '면접' in important_notes:
                    suggestions.append("🗣️ 면접이 있을 수 있습니다. 관련 자료를 미리 준비해보세요")
            
        except Exception as e:
            self.logger.error(f"제안사항 생성 중 오류: {e}")
            suggestions.append("❓ 상세 내용을 직접 확인해주세요")
        
        return suggestions
    
    def generate_error_suggestions(self, error_type: str, error_message: str) -> List[str]:
        """오류 유형별 해결 제안사항 생성"""
        suggestions = []
        
        try:
            if 'api' in error_type.lower() or 'key' in error_message.lower():
                suggestions.extend([
                    "🔑 API 키를 확인해주세요",
                    "🔧 환경변수 GOOGLE_API_KEY 설정을 확인해주세요",
                    "📱 API 사용량 한도를 확인해주세요"
                ])
            
            elif 'network' in error_type.lower() or 'connection' in error_message.lower():
                suggestions.extend([
                    "🌐 인터넷 연결을 확인해주세요",
                    "🔄 잠시 후 다시 시도해주세요",
                    "🛡️ 방화벽 설정을 확인해주세요"
                ])
            
            elif 'json' in error_type.lower() or 'parsing' in error_message.lower():
                suggestions.extend([
                    "📝 입력 데이터 형식을 확인해주세요",
                    "🔄 다시 시도해주세요",
                    "📞 기술지원팀에 문의해주세요"
                ])
            
            elif 'validation' in error_type.lower():
                suggestions.extend([
                    "✅ 필수 필드가 모두 입력되었는지 확인해주세요",
                    "📏 입력 데이터의 길이와 형식을 확인해주세요",
                    "🔍 입력값을 다시 검토해주세요"
                ])
            
            else:
                suggestions.extend([
                    "🔄 잠시 후 다시 시도해주세요",
                    "📞 관리자에게 문의해주세요",
                    "📝 오류 상황을 기록해두시면 도움이 됩니다"
                ])
                
        except Exception as e:
            self.logger.error(f"오류 제안사항 생성 중 오류: {e}")
            suggestions = ["📞 기술지원팀에 문의해주세요"]
        
        return suggestions
    
    def generate_quality_suggestions(self, data_quality: Dict[str, Any]) -> List[str]:
        """데이터 품질 기반 제안사항 생성"""
        suggestions = []
        
        try:
            if not data_quality.get('is_complete', True):
                suggestions.append("⚠️ 일부 정보가 누락되어 있습니다")
                
                missing_fields = data_quality.get('missing_fields', [])
                for field in missing_fields:
                    if field == 'summary':
                        suggestions.append("📝 요약 정보를 더 상세히 확인해주세요")
                    elif field == 'schedule':
                        suggestions.append("⏰ 일정 정보를 별도로 확인해주세요")
                    elif field == 'target':
                        suggestions.append("🎯 신청 대상을 별도로 확인해주세요")
            
            warnings = data_quality.get('warnings', [])
            if warnings:
                for warning in warnings:
                    if '일정' in warning:
                        suggestions.append("📅 공식 홈페이지에서 일정을 다시 확인해보세요")
                    elif '대상' in warning:
                        suggestions.append("👤 신청 자격을 관련 부서에 직접 문의해보세요")
                        
        except Exception as e:
            self.logger.error(f"품질 제안사항 생성 중 오류: {e}")
            suggestions.append("🔍 원문을 직접 확인해주세요")
        
        return suggestions
    
    def generate_general_suggestions(self, category: str) -> List[str]:
        """카테고리별 일반적인 제안사항 생성"""
        suggestions = []
        
        try:
            category = category.lower()
            
            if '장학' in category:
                suggestions.extend([
                    "💡 다른 장학금도 함께 검토해보세요",
                    "📋 지원 서류를 미리 준비해두세요",
                    "⏰ 마감일 전에 여유있게 신청하세요"
                ])
            
            elif '취업' in category or '채용' in category:
                suggestions.extend([
                    "📄 이력서와 자기소개서를 미리 준비하세요",
                    "🔍 회사 정보를 미리 조사해보세요",
                    "💼 관련 자격증이나 경험을 정리해보세요"
                ])
            
            elif '교육' in category or '강의' in category:
                suggestions.extend([
                    "📚 사전 학습 자료가 있는지 확인해보세요",
                    "🕐 수업 시간표를 미리 확인하세요",
                    "📝 필요한 준비물이 있는지 확인해보세요"
                ])
            
            elif '행사' in category:
                suggestions.extend([
                    "🎫 참가 신청 방법을 미리 확인하세요",
                    "📍 행사 장소와 교통편을 확인해보세요",
                    "👕 드레스코드가 있는지 확인해보세요"
                ])
            
            else:
                suggestions.extend([
                    "📖 공지사항을 주기적으로 확인하세요",
                    "❓ 궁금한 점은 담당자에게 문의하세요",
                    "📱 관련 앱이나 웹사이트를 북마크해두세요"
                ])
                
        except Exception as e:
            self.logger.error(f"일반 제안사항 생성 중 오류: {e}")
            suggestions = ["📞 담당 부서에 직접 문의해주세요"]
        
        return suggestions
    
    def _generate_deadline_suggestions(self, date_str: str) -> List[str]:
        """마감일 기반 제안사항 생성"""
        suggestions = []
        
        try:
            if not date_str:
                return ["⏰ 마감일을 별도로 확인해주세요"]
            
            # 날짜 파싱 시도
            date_patterns = [
                r'(\d{4})\.(\d{1,2})\.(\d{1,2})',  # YYYY.MM.DD
                r'(\d{4})-(\d{1,2})-(\d{1,2})',   # YYYY-MM-DD
                r'(\d{1,2})/(\d{1,2})/(\d{4})',   # MM/DD/YYYY
            ]
            
            deadline = None
            for pattern in date_patterns:
                match = re.search(pattern, date_str)
                if match:
                    try:
                        if pattern == date_patterns[2]:  # MM/DD/YYYY
                            month, day, year = match.groups()
                            deadline = datetime(int(year), int(month), int(day))
                        else:  # YYYY.MM.DD or YYYY-MM-DD
                            year, month, day = match.groups()
                            deadline = datetime(int(year), int(month), int(day))
                        break
                    except ValueError:
                        continue
            
            if deadline:
                now = datetime.now()
                days_left = (deadline - now).days
                
                if days_left < 0:
                    suggestions.append("⚠️ 마감일이 지났습니다. 연장 가능 여부를 확인해보세요")
                elif days_left == 0:
                    suggestions.append("🚨 오늘이 마감일입니다!")
                elif days_left <= 3:
                    suggestions.append(f"⏰ {days_left}일 후 마감입니다. 서둘러 준비하세요!")
                elif days_left <= 7:
                    suggestions.append(f"📅 일주일 내 마감({days_left}일 후)입니다. 미리 준비하세요")
                elif days_left <= 14:
                    suggestions.append(f"📋 2주 내 마감입니다. 필요한 서류를 준비해보세요")
                else:
                    suggestions.append(f"📆 마감까지 {days_left}일 남았습니다. 계획적으로 준비하세요")
            else:
                suggestions.append("📅 마감일 형식을 확인하여 일정을 관리하세요")
                
        except Exception as e:
            self.logger.error(f"마감일 제안사항 생성 중 오류: {e}")
            suggestions.append("📅 마감일을 달력에 표시해두세요")
        
        return suggestions
    
    def consolidate_suggestions(self, suggestion_lists: List[List[str]], max_suggestions: int = 10) -> List[str]:
        """여러 제안사항 리스트를 통합하고 중복 제거"""
        all_suggestions = []
        
        try:
            # 모든 제안사항을 하나의 리스트로 합치기
            for suggestion_list in suggestion_lists:
                if isinstance(suggestion_list, list):
                    all_suggestions.extend(suggestion_list)
            
            # 중복 제거 (순서 유지)
            unique_suggestions = []
            seen = set()
            
            for suggestion in all_suggestions:
                if suggestion not in seen:
                    unique_suggestions.append(suggestion)
                    seen.add(suggestion)
            
            # 최대 개수 제한
            final_suggestions = unique_suggestions[:max_suggestions]
            
            self.logger.info(f"제안사항 통합 완료: {len(final_suggestions)}개")
            return final_suggestions
            
        except Exception as e:
            self.logger.error(f"제안사항 통합 중 오류: {e}")
            return ["📞 관련 부서에 직접 문의해주세요"]