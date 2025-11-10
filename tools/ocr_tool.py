"""
URL 이미지와 로컬 이미지에서 OCR 텍스트를 추출하는 함수들
LLM Agent에서 사용하기 위해 최적화됨
"""

import requests
import io
import logging
from PIL import Image
import numpy as np
import os
import sys
# PaddleOCR 임포트
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    print("PaddleOCR가 설치되지 않았습니다. 설치하려면: pip install paddleocr")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logging_config import setup_logger
# 로깅 설정
logger = setup_logger()

# 전역 OCR 객체 (한 번만 초기화)
_ocr_instance = None


def _get_ocr_instance():
    """OCR 인스턴스를 가져오거나 생성합니다 (CPU 모드)."""
    global _ocr_instance
    
    if _ocr_instance is None:
        if not PADDLEOCR_AVAILABLE:
            raise ImportError("PaddleOCR가 설치되지 않았습니다.")
        
        try:
            # CPU 모드로 설정, 프로그레스 바 및 로그 비활성화
            _ocr_instance = PaddleOCR(
                use_textline_orientation=True, 
                lang='korean'
            )
            logger.info("PaddleOCR 초기화 완료 (CPU 모드)")
        except Exception as e:
            logger.error(f"PaddleOCR 초기화 실패: {e}")
            raise
    
    return _ocr_instance


def perform_ocr_on_url(img_url: str) -> str:
    """
    URL 이미지에서 OCR 텍스트를 추출합니다.
    
    Args:
        img_url (str): 이미지 URL
        
    Returns:
        str: 추출된 텍스트 (실패시 빈 문자열)
    """
    try:
        logger.info(f"OCR 처리 시작: {img_url}")
        
        # 1. 이미지 다운로드
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(img_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 2. PIL Image로 변환
        image = Image.open(io.BytesIO(response.content))
        
        # RGB로 변환 (필요한 경우)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # 3. numpy 배열로 변환 (PaddleOCR는 PIL Image도 직접 처리 가능)
        img_array = np.array(image)
        
        logger.info(f"이미지 다운로드 완료: {img_array.shape}")
        
        # 4. OCR 수행 (numpy 배열 사용)
        ocr = _get_ocr_instance()
        results = ocr.predict(img_array)
        
        # 5. 텍스트 추출 (PaddleOCR 3.x 결과 구조)
        if not results:
            logger.warning("OCR 결과가 없습니다.")
            return ""
        
        logger.info(f"OCR 결과 타입: {type(results)}, 길이: {len(results) if hasattr(results, '__len__') else 'N/A'}")
        
        text_lines = []
        
        # PaddleOCR 3.x 결과 구조 처리
        if isinstance(results, list) and len(results) > 0:
            first_result = results[0]
            
            # OCRResult 객체에서 rec_texts 추출
            if hasattr(first_result, 'rec_texts'):
                text_lines = first_result.rec_texts
                logger.info(f"rec_texts에서 {len(text_lines)}개 텍스트 라인 추출")
            elif isinstance(first_result, dict) and 'rec_texts' in first_result:
                text_lines = first_result['rec_texts']
                logger.info(f"딕셔너리 rec_texts에서 {len(text_lines)}개 텍스트 라인 추출")
            else:
                logger.warning(f"예상치 못한 결과 구조: {type(first_result)}")
                return ""
        
        ocr_text = '\n'.join(text_lines) if text_lines else ""
        
        logger.info(f"OCR 완료: {len(ocr_text)}자 추출")
        return ocr_text
        
    except Exception as e:
        logger.error(f"OCR 처리 실패: {e}")
        return ""

def test_ocr():
    """테스트 함수"""
    # URL OCR 테스트
    test_url = "https://scatch.ssu.ac.kr/wp-content/uploads/sites/5/2025/08/2025년-8월-학부-졸업자-학위수여-안내-20250814.pdf_page_1.jpg"
    
    print("=== URL OCR 테스트 ===")
    print(f"테스트 URL: {test_url}")
    print("\nOCR 처리 중...")
    
    result_url = perform_ocr_on_url(test_url)
    
    print("\n=== URL OCR 결과 ===")
    if result_url:
        print(f"추출된 텍스트 길이: {len(result_url)}자")
        print("\n추출된 텍스트 (처음 500자):")
        print("=" * 50)
        print(result_url[:500])
        print("=" * 50)
    else:
        print("텍스트를 추출할 수 없습니다.")


if __name__ == "__main__":
    test_ocr()