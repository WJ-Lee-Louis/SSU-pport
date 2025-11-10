import os
import warnings
from langchain.agents import Tool
from langgraph.graph import StateGraph, START
from langchain_core.runnables import RunnableLambda
from typing import Any, Dict, List, Optional, TypedDict
import sys

# LangChain 경고 메시지 무시
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core.globals")
# for OCR Node

# for Summary Node
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from SummaryContent import GeminiSummarizer
from SuggestionEngine import SuggestionEngine

# Add parent directory to path to import db module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logging_config import setup_logger
from tools.ocr_tool import perform_ocr_on_url

class NotifyState(TypedDict):
    title: str                      # from Crawl-Detect Engine
    content: str                    # from Crawl-Detect Engine
    image: List[dict]               # from Crawl-Detect Engine
    category: str                   # from Crawl-Detect Engine

    ocr_text: List[dict]        # from OCR(optional) node
    json_summary: Dict[str, Any]    # from Summary node

class LanggraphPipeline:
    def __init__(self):
        self.logger = setup_logger()
        self.logger.info("LanggraphPipeline 초기화 시작")
        
        try:
            self.suggestion_engine = SuggestionEngine()
            self.llm_agent = self._make_graph()
            self.logger.info("LanggraphPipeline 초기화 완료")
        except Exception as e:
            self.logger.error(f"LanggraphPipeline 초기화 실패: {e}")
            raise
        
    def _make_graph(self):
        graph = StateGraph(NotifyState)
        
        #노드 세팅
        graph.add_node("OCR_Node", RunnableLambda(self._OCR))
        graph.add_node("Summary_Node", RunnableLambda(self._Summary))

        # 조건 함수
        graph.add_conditional_edges(
            START,
            self._OCR_branching_condition,
            {True: "OCR_Node", False: "Summary_Node"}
        )
        #3. 엣지 연결
        graph.add_edge("OCR_Node", "Summary_Node")
        graph.set_finish_point("Summary_Node")

        llm_agent = graph.compile()
        return llm_agent
    
    def run(self, json_input: Dict[str, Any]) -> Dict[str, Any]:
        # json_input을 llm_agent에 전달하여 처리하고 결과 반환
        if self.llm_agent is None:
            raise ValueError("LLM Agent가 초기화되지 않았습니다.")
        try:
            self.logger.info(f"[LLM Agent 실행] - {json_input['title']}")
            result = self.llm_agent.invoke(
                {'title':json_input['title'],
                'content':json_input['content'],
                'image':json_input['image'],
                'category':json_input['category']}
            )['json_summary']
            
            return {
                'status': 'success',
                'json_summary': result
            }
        except Exception as e:
            self.logger.error(f"LLM Agent 오류: {e}")
            return {
                'status': 'error',
                'json_summary': {}
            }

    def _OCR(self, state):
        image= state.get('image', [])
        for i in image:
            i['ocr_text'] = perform_ocr_on_url(i['url'])
        ocr_text = [{"filename": i['filename'], "ocr_text": i['ocr_text']} for i in image]
        return {'ocr_text':ocr_text}

    def _Summary(self, state):
        """Summary 노드 - AI 모델을 사용한 공지사항 요약"""
        title = state.get('title')
        ocr_text = state.get('ocr_text') or []
        content = state.get('content')
        category = state.get('category', '')
        
        try:
            self.logger.info(f"요약 시작: {title[:30]}...")
            
            summarizer = GeminiSummarizer()
            summary_result = summarizer.summarize(title, ocr_text, content)
            
            # summary_result가 문자열인 경우 (성공적으로 JSON을 반환한 경우)
            if isinstance(summary_result, str) and not summary_result.startswith("요약에 실패했습니다"):
                # JSON 문자열이 유효한지 간단히 검증
                try:
                    import json
                    parsed_data = json.loads(summary_result)
                    self.logger.debug("JSON 파싱 성공")
                except json.JSONDecodeError:
                    parsed_data = None
                    self.logger.error("JSON 파싱 실패")
                
                if parsed_data:
                    self.logger.info("요약 및 파싱 성공")
                    
                    # 다양한 소스에서 제안사항 수집
                    suggestion_lists = []
                    
                    # 제안 엔진에서 생성된 제안사항
                    engine_suggestions = self.suggestion_engine.generate_parsing_suggestions(parsed_data)
                    if engine_suggestions:
                        suggestion_lists.append(engine_suggestions)
                    
                    # 카테고리 기반 일반 제안사항
                    general_suggestions = self.suggestion_engine.generate_general_suggestions(category)
                    if general_suggestions:
                        suggestion_lists.append(general_suggestions)
                    
                    # 모든 제안사항 통합
                    final_suggestions = self.suggestion_engine.consolidate_suggestions(suggestion_lists)
                    
                    self.logger.info(f"통합 제안사항 {len(final_suggestions)}개 생성")
                    
                    return {
                        'json_summary': {
                            'status': 'success',
                            'data': summary_result,
                            'parsed_data': parsed_data,
                            'suggestions': final_suggestions
                        }
                    }
                else:
                    self.logger.error("파싱 실패")
                    error_suggestions = self.suggestion_engine.generate_error_suggestions('parsing', '파싱 실패')
                    return {
                        'json_summary': {
                            'status': 'error',
                            'error': '파싱 실패',
                            'data': summary_result,
                            'suggestions': error_suggestions
                        }
                    }
            else:
                # summary_result가 오류 메시지인 경우
                self.logger.error(f"요약 실패: {summary_result}")
                error_suggestions = self.suggestion_engine.generate_error_suggestions('summary', summary_result)
                return {
                    'json_summary': {
                        'status': 'error',
                        'error': summary_result,
                        'suggestions': error_suggestions
                    }
                }
                
        except Exception as e:
            error_msg = f"Summary 노드에서 예상치 못한 오류: {e}"
            self.logger.error(error_msg)
            error_suggestions = self.suggestion_engine.generate_error_suggestions('unexpected', str(e))
            return {
                'json_summary': {
                    'status': 'error',
                    'error': error_msg,
                    'suggestions': error_suggestions
                }
            }

    def _OCR_branching_condition(self, state):
        """OCR 분기 조건 - 이미지 존재 여부에 따라 OCR 노드 실행 결정"""
        images = state.get('image', [])
        has_images = bool(images and len(images) > 0)
        
        if has_images:
            self.logger.debug(f"이미지 {len(images)}개 발견 - OCR 노드 실행")
            return True
        else:
            self.logger.debug("이미지 없음 - OCR 건너뛰고 요약으로 직행")
            return False

    def _validate_pipeline_input(self, json_input: Dict[str, Any]) -> Dict[str, Any]:
        """파이프라인 입력 데이터 유효성 검사"""
        required_fields = ['title', 'content', 'category']
        missing_fields = []
        
        for field in required_fields:
            if not json_input.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            return {
                'is_valid': False,
                'error': f'필수 필드 누락: {", ".join(missing_fields)}',
                'suggestions': [f'{field} 필드를 확인해주세요' for field in missing_fields]
            }
        
        # 제목 길이 검사
        title = json_input['title'].strip()
        if len(title) < 5:
            return {
                'is_valid': False,
                'error': '제목이 너무 짧습니다',
                'suggestions': ['더 구체적인 제목을 입력해주세요']
            }
        
        # 내용 길이 검사
        content = json_input['content'].strip()
        if len(content) < 50:
            return {
                'is_valid': False,
                'error': '내용이 너무 짧습니다',
                'suggestions': ['더 상세한 내용을 입력해주세요']
            }
        
        return {'is_valid': True}
    
    def get_pipeline_health(self) -> Dict[str, Any]:
        """파이프라인 상태 확인"""
        from datetime import datetime
        
        health_status = {
            'pipeline_initialized': self.llm_agent is not None,
            'logger_active': self.logger is not None,
            'timestamp': datetime.now().isoformat()
        }
        
        # 추가 건강성 체크
        try:
            # GeminiSummarizer 테스트
            summarizer = GeminiSummarizer()
            health_status['gemini_available'] = summarizer.model is not None
        except Exception as e:
            health_status['gemini_available'] = False
            health_status['gemini_error'] = str(e)
        
        self.logger.info(f"파이프라인 상태 체크: {health_status}")
        return health_status

def main():
    llm_agent = LanggraphPipeline()
    from IPython.display import Image, display

    try:
        # 이미지를 반환한다면, 파일로 저장
        img = llm_agent.llm_agent.get_graph().draw_mermaid_png()
        with open("graph.png", "wb") as f:
            f.write(img)
    except Exception as e:
        print(f"Error displaying graph: {e}")
    
    a = llm_agent.run({
    "title": "봉사[경기 부천] 고리울청소년센터 청소년 지역사회 연계프로그램 ‘청개구리 문화놀이터’ 자원활동가 모집",
    "url": "https://scatch.ssu.ac.kr/%ea%b3%b5%ec%a7%80%ec%82%ac%ed%95%ad/?f&category=%EB%B4%89%EC%82%AC&paged=1&slug=%EA%B2%BD%EA%B8%B0-%EB%B6%80%EC%B2%9C-%EA%B3%A0%EB%A6%AC%EC%9A%B8%EC%B2%AD%EC%86%8C%EB%85%84%EC%84%BC%ED%84%B0-%EC%B2%AD%EC%86%8C%EB%85%84-%EC%A7%80%EC%97%AD%EC%82%AC%ED%9A%8C-%EC%97%B0%EA%B3%84&keyword",
    "content": "<div>\n<span>봉사</span>\n<h2>[경기 부천] 고리울청소년센터 청소년 지역사회 연계프로그램 ‘청개구리 문화놀이터’ 자원활동가 모집</h2>\n<div>\n<div><i></i> 2025년 8월 25일</div>\n<div><i></i> 50</div>\n<div>\n<button><i></i></button>\n</div>\n</div>\n<hr/>\n<div>\n<p><a><img/></a></p>\n<p><span>[경기 부천] 고리울청소년센터 청소년 지역사회 연계프로그램 ‘청개구리 문화놀이터’ 자원활동가 모집</span></p>\n<p><span>– 고리울청소년센터는 부천시에서 지원, 부천여성청소년재단에서 위탁운영하고 있는 청소년수련시설입니다.</span><br/>\n<span>– 지역 청소년들의 건강한 성장과 돌봄을 위해 지역주민 참여를 기반으로한 ‘청개구리 문화놀이터(먹거리 및 체험 제공)’사업을 운영하고 있습니다. 청소년 지역사회 연계프로그램에 관심있는 자원활동가를 모집하오니 많은 관심과 홍보 협조를 요청드립니다.</span></p>\n<p><span>* 모집기간 및 신청방법: 연중 상시, 전화 또는 문자 신청 후 OT, 상호결정</span><br/>\n<span>* 문의사항: 고리울청소년센터 전서희(070-4991-4595/317008@bwyf.or.kr)</span></p>\n</div>\n</div>",
    "image": [
      {
        "url": "https://scatch.ssu.ac.kr/wp-content/uploads/sites/5/2025/08/KakaoTalk_20250825_151546483-1568x1568.jpg",
        "filename": "KakaoTalk_20250825_151546483-1568x1568.jpg"
      }
    ],
    "fetch_success": True,
    "notification_id": 7,
    "category": "봉사공지",
    "ai_summary": None
  })

    # print("============xxxxxx
    print("================완료2================")
    print(a['json_summary']['data'])
    

if __name__ == "__main__":
    main()