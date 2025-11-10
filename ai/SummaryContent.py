import os
import sys
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from dotenv import load_dotenv
import json
import re
from typing import Dict, Any, List

# Add parent directory to path to import utils module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logging_config import setup_logger

# 기본 프롬프트 템플릿
DEFAULT_PROMPT_TEMPLATE = """
### 

---
### Data of Notice ###
{input_content}
---

You are a highly competent assistant responsible for accurately extracting key information from academic notices and delivering it to students.

Analyze the following academic notice. Extract the essential information and return it **strictly in JSON format**.
- The JSON keys must be in English and snake_case.
- All JSON values must be written in Korean.
- If a specific field or piece of information is not mentioned in the text, make field empty but do not remove it.
- In the `schedule` field, find and extract only crucial single dates like deadlines (마감일).
- If the text provides a period (e.g., 'Application Period: YYYY.MM.DD HH:MM ~ YYYY.MM.DD HH:MM'), extract ONLY the end date and its corresponding time, and set the description to '신청 마감' (Application Deadline).

Prioritize the most critical information by placing the `title` and `summary` first in the JSON structure.

---
### JSON Format ###
{{
    "title": "{input_title}", (title should not change or be removed)
    "summary": "(A detailed summary of the notice. It MUST include the main purpose, key activities, and expected benefits for participants.)",
    "schedule": [
        {{
            "description": "(The type of deadline, e.g., '신청 마감', '서류 제출 마감'. MUST be a single event.)",
            "date": "(The corresponding single date ONLY. e.g., 'YYYY.MM.DD HH:MM' or 'YYYY.MM.DD'. If the time is specified in the notice, it must be included.)",
            "location": "(A place where the event on the specified date takes place)"
        }}
    ],
    "target": "(Who the notice is for)",
    "application_method": "(A full phrase describing the method, e.g., 'OOO 홈페이지에서 온라인 신청', 'XX관 YY실로 방문 제출')",
    "important_notes": "(Key details like capacity, selection method, benefits, or contact info. Key details are separated by a slash.e.g., '정원: OO명 / 선발 방식: 서류 심사 / 혜택: 활동비 지원 / 문의: OOO팀 (02-123-4567)'))"
}}
"""

class GeminiSummarizer:
    def __init__(self, model_name: str = 'gemini-2.5-flash'):
        self.logger = setup_logger()
        try:
            # API 키 로드
            api_key = os.getenv("GOOGLE_API_KEY") or self._load_api_key_from_env()
            if not api_key:
                raise ValueError("API 키를 찾을 수 없습니다.")
            genai.configure(api_key=api_key)

            # 생성 옵션 설정
            self.generation_config = {
                "temperature": 0.2,         
                "top_p": 1,                 
                "top_k": 1,                 
                # "max_output_tokens": 2048,  
            }
            
            # 모델 초기화
            self.model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=self.generation_config
            )
            # print(f"GeminiSummarizer 초기화 완료 (모델: {model_name})")

        except Exception as e:
            self.logger.error(f"초기화 중 오류 발생: {e}")
            self.model = None

    # API 키 반환
    def _load_api_key_from_env(self):
        load_dotenv()
        return os.getenv("GOOGLE_API_KEY")

    # 요약 함수
    def summarize(self, title: str, ocr_text: str, content: str, prompt_template: str = DEFAULT_PROMPT_TEMPLATE) -> str:
        if not self.model:
            return "요약에 실패했습니다. 모델이 초기화되지 않았습니다."

        try:
            input_content=f"{content}{'\n\nThe following is the content of img ocr. Please note that there may be typos.\n' + str(ocr_text) if ocr_text else ''}"

            prompt = prompt_template.format(input_title=title, input_content=input_content)
            response = self.model.generate_content(
                prompt,
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                }
            )
            
            # LLM의 전체 응답 텍스트를 변수에 저장
            raw_response_text = response.text
            
            # 정규 표현식(re)을 사용해 텍스트에서 '{...}' 패턴을 탐색
            json_match = re.search(r'\{.*\}', raw_response_text, re.DOTALL)
            
            # JSON 패턴을 찾았는지 확인
            if json_match:
                # 찾은 JSON 문자열을 추출
                json_string = json_match.group(0)
                
                # 추출한 문자열이 실제 JSON 형식이 맞는지 검증
                json.loads(json_string)

                return json_string.strip() # 검증된 순수 JSON 문자열을 반환
            else:
                # LLM 응답에서 '{...}' 패턴을 찾지 못한 경우
                raise ValueError("LLM 응답에서 유효한 JSON을 찾을 수 없습니다.")

        except Exception as e:
            error_msg = f"요약 중 예상치 못한 오류: {e}"
            self.logger.error(error_msg)
            return f"요약에 실패했습니다: {error_msg}"
    
    def _validate_inputs(self, title: str, content: str) -> Dict[str, Any]:
        """입력 데이터 유효성 검사"""
        if not title or not title.strip():
            return {
                'is_valid': False,
                'error': '제목이 비어있습니다',
                'suggestions': ['유효한 제목을 입력해주세요']
            }
        
        if not content or not content.strip():
            return {
                'is_valid': False,
                'error': '콘텐츠가 비어있습니다',
                'suggestions': ['유효한 콘텐츠를 입력해주세요']
            }
        
        if len(content.strip()) < 50:
            return {
                'is_valid': False,
                'error': '콘텐츠가 너무 짧습니다',
                'suggestions': ['더 상세한 콘텐츠를 제공해주세요']
            }
        
        return {'is_valid': True}
    
    def _extract_and_validate_json(self, response_text: str) -> Dict[str, Any]:
        """응답에서 JSON 추출 및 검증"""
        try:
            # JSON 패턴 찾기
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if not json_match:
                return {
                    'status': 'error',
                    'error': 'LLM 응답에서 JSON 형식을 찾을 수 없습니다',
                    'suggestions': ['프롬프트를 수정하거나 다시 시도해주세요']
                }
            
            json_string = json_match.group(0)
            
            # JSON 유효성 검증
            try:
                parsed_data = json.loads(json_string)
                self.logger.debug("JSON 파싱 성공")
                
                return {
                    'status': 'success',
                    'json_string': json_string.strip(),
                    'parsed_data': parsed_data
                }
                
            except json.JSONDecodeError as e:
                return {
                    'status': 'error',
                    'error': f'JSON 형식 오류: {e}',
                    'suggestions': ['응답 형식을 다시 확인해주세요']
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'error': f'JSON 추출 중 오류: {e}',
                'suggestions': ['응답 형식을 확인하거나 다시 시도해주세요']
            }
    
    def _generate_quality_suggestions(self, parsed_data: Dict[str, Any]) -> List[str]:
        """파싱된 데이터 품질 기반 제안사항 생성"""
        suggestions = []
        
        # 요약 품질 검사
        summary = parsed_data.get('summary', '')
        if len(summary) < 50:
            suggestions.append("요약이 너무 간단합니다. 더 상세한 정보가 필요할 수 있습니다.")
        
        # 일정 정보 검사
        schedule = parsed_data.get('schedule')
        if not schedule:
            suggestions.append("일정 정보가 없습니다. 마감일 등을 확인해주세요.")
        
        # 신청 방법 검사
        application_method = parsed_data.get('application_method')
        if not application_method:
            suggestions.append("신청 방법 정보가 없습니다. 신청 방법을 확인해주세요.")
        
        return suggestions