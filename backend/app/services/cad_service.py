"""
CAD 파일 처리 및 분석 서비스
DWG/DXF 파일을 웹에서 시각화할 수 있는 형태로 변환
"""
import os
import logging
import tempfile
import shutil
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import base64
from io import BytesIO

try:
    import ezdxf
    from PIL import Image, ImageDraw
    import cv2
    import numpy as np
except ImportError as e:
    print(f"⚠️ CAD 처리에 필요한 라이브러리가 설치되지 않았습니다: {e}")
    print("pip install ezdxf Pillow opencv-python을 실행해주세요.")
    ezdxf = None
    Image = None
    cv2 = None
    np = None

from .ai_service import WarehouseAI

logger = logging.getLogger(__name__)

class CADService:
    """DWG/DXF 파일 처리 및 분석 서비스"""
    
    def __init__(self, ai_service: WarehouseAI = None):
        self.ai_service = ai_service or WarehouseAI()
        self.upload_dir = Path("cad_uploads")
        self.upload_dir.mkdir(exist_ok=True)
        
        # 지원하는 파일 형식
        self.supported_formats = {'.dwg', '.dxf', '.dwf'}
        
        # 최대 파일 크기 (50MB)
        self.max_file_size = 50 * 1024 * 1024
    
    async def process_cad_file(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """
        CAD 파일을 처리하고 웹 시각화용 데이터로 변환
        """
        try:
            logger.info(f"CAD 파일 처리 시작: {original_filename}")
            
            # 파일 확장자 확인
            file_ext = Path(original_filename).suffix.lower()
            if file_ext not in self.supported_formats:
                raise ValueError(f"지원하지 않는 파일 형식: {file_ext}")
            
            # 파일 크기 확인
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                raise ValueError(f"파일 크기가 너무 큽니다: {file_size / (1024*1024):.1f}MB (최대 50MB)")
            
            result = {
                "success": True,
                "filename": original_filename,
                "file_size": file_size,
                "file_type": file_ext,
                "processing_method": None,
                "data": None,
                "error": None
            }
            
            # DXF 파일 처리
            if file_ext == '.dxf':
                result["data"] = await self._process_dxf_file(file_path)
                result["processing_method"] = "direct_dxf_parsing"
            
            # DWG 파일 처리 (DXF로 변환 시도)
            elif file_ext == '.dwg':
                # DWG → DXF 변환 시도
                dxf_path = await self._convert_dwg_to_dxf(file_path)
                if dxf_path:
                    result["data"] = await self._process_dxf_file(dxf_path)
                    result["processing_method"] = "dwg_to_dxf_conversion"
                else:
                    # 변환 실패 시 이미지 기반 처리
                    result["data"] = await self._process_as_image(file_path)
                    result["processing_method"] = "image_based_ai_analysis"
            
            # 기타 파일은 이미지 기반 처리
            else:
                result["data"] = await self._process_as_image(file_path)
                result["processing_method"] = "image_based_ai_analysis"
            
            logger.info(f"CAD 파일 처리 완료: {original_filename} ({result['processing_method']})")
            return result
            
        except Exception as e:
            logger.error(f"CAD 파일 처리 오류: {str(e)}")
            return {
                "success": False,
                "filename": original_filename,
                "error": str(e),
                "data": None
            }
    
    async def _process_dxf_file(self, file_path: str) -> Dict[str, Any]:
        """DXF 파일을 직접 파싱하여 구조화된 데이터 추출"""
        if not ezdxf:
            raise ImportError("ezdxf 라이브러리가 설치되지 않았습니다.")
        
        try:
            # DXF 파일 로드
            doc = ezdxf.readfile(file_path)
            msp = doc.modelspace()
            
            # 도면 경계 계산
            bounds = self._calculate_bounds(msp)
            
            # 엔티티별 분석
            entities = {
                'lines': [],
                'rectangles': [],
                'circles': [],
                'texts': [],
                'blocks': []
            }
            
            for entity in msp:
                entity_data = self._parse_entity(entity)
                if entity_data:
                    entity_type = entity_data.get('type')
                    if entity_type in entities:
                        entities[entity_type].append(entity_data)
            
            # 창고 레이아웃 해석
            warehouse_data = self._interpret_warehouse_layout(entities, bounds)
            
            return warehouse_data
            
        except Exception as e:
            logger.error(f"DXF 파일 파싱 오류: {str(e)}")
            raise
    
    async def _convert_dwg_to_dxf(self, dwg_path: str) -> Optional[str]:
        """DWG 파일을 DXF로 변환 (ezdxf로는 DWG 직접 읽기 제한적)"""
        try:
            # ezdxf는 DWG 직접 읽기가 제한적이므로 
            # 향후 ODA File Converter 또는 다른 도구 연동 가능
            logger.warning("DWG → DXF 변환은 현재 제한적입니다. 이미지 기반 분석으로 전환합니다.")
            return None
            
        except Exception as e:
            logger.error(f"DWG → DXF 변환 오류: {str(e)}")
            return None
    
    async def _process_as_image(self, file_path: str) -> Dict[str, Any]:
        """파일을 이미지로 변환 후 AI 분석"""
        try:
            # 1. 파일을 이미지로 변환
            image_path = await self._convert_to_image(file_path)
            
            # 2. AI 분석
            analysis_result = await self._analyze_with_ai(image_path)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"이미지 기반 처리 오류: {str(e)}")
            raise
    
    async def _convert_to_image(self, file_path: str) -> str:
        """CAD 파일을 이미지로 변환"""
        try:
            # 임시 이미지 파일 경로
            temp_dir = tempfile.mkdtemp()
            image_path = os.path.join(temp_dir, "cad_preview.png")
            
            # 파일 확장자에 따른 처리
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext == '.dxf' and ezdxf:
                # DXF를 이미지로 변환
                await self._dxf_to_image(file_path, image_path)
            else:
                # 기본 플레이스홀더 이미지 생성
                await self._create_placeholder_image(image_path)
            
            return image_path
            
        except Exception as e:
            logger.error(f"이미지 변환 오류: {str(e)}")
            raise
    
    async def _dxf_to_image(self, dxf_path: str, output_path: str):
        """DXF 파일을 PNG 이미지로 변환"""
        if not ezdxf or not Image:
            raise ImportError("필요한 라이브러리가 설치되지 않았습니다.")
        
        try:
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()
            
            # 도면 경계 계산
            bounds = self._calculate_bounds(msp)
            if not bounds:
                raise ValueError("도면 경계를 계산할 수 없습니다.")
            
            # 이미지 크기 설정
            margin = 50
            scale = 10  # DXF 좌표계 → 픽셀 스케일
            width = int((bounds['max_x'] - bounds['min_x']) * scale) + margin * 2
            height = int((bounds['max_y'] - bounds['min_y']) * scale) + margin * 2
            
            # 이미지 생성
            img = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(img)
            
            # 엔티티 그리기
            for entity in msp:
                self._draw_entity_on_image(draw, entity, bounds, scale, margin)
            
            # 이미지 저장
            img.save(output_path, 'PNG')
            logger.info(f"DXF 이미지 변환 완료: {output_path}")
            
        except Exception as e:
            logger.error(f"DXF → 이미지 변환 오류: {str(e)}")
            raise
    
    async def _create_placeholder_image(self, output_path: str):
        """플레이스홀더 이미지 생성"""
        if not Image:
            raise ImportError("Pillow 라이브러리가 설치되지 않았습니다.")
        
        # 기본 창고 레이아웃 이미지 생성
        img = Image.new('RGB', (800, 600), 'white')
        draw = ImageDraw.Draw(img)
        
        # 창고 외곽
        draw.rectangle([50, 50, 750, 550], outline='black', width=3)
        
        # 샘플 랙들
        racks = [
            (100, 100, 150, 200),  # A랙
            (200, 100, 250, 200),  # B랙
            (300, 100, 350, 200),  # C랙
            (500, 100, 550, 200),  # D랙
            (600, 100, 650, 200),  # E랙
        ]
        
        for i, (x1, y1, x2, y2) in enumerate(racks):
            draw.rectangle([x1, y1, x2, y2], outline='blue', fill='lightblue', width=2)
            # 랙 라벨
            label = chr(65 + i)  # A, B, C, ...
            draw.text((x1 + 20, y1 + 40), f"{label}랙", fill='black')
        
        # 통로
        draw.line([80, 300, 720, 300], fill='gray', width=3)
        
        # 출입구
        draw.rectangle([350, 45, 450, 55], outline='red', fill='red', width=2)
        draw.text((375, 30), "출입구", fill='red')
        
        img.save(output_path, 'PNG')
        logger.info(f"플레이스홀더 이미지 생성: {output_path}")
    
    async def _analyze_with_ai(self, image_path: str) -> Dict[str, Any]:
        """AI를 사용하여 창고 도면 분석"""
        try:
            # 이미지를 base64로 인코딩
            with open(image_path, 'rb') as img_file:
                image_data = base64.b64encode(img_file.read()).decode('utf-8')
            
            # AI 분석 프롬프트
            prompt = """
이 창고 도면 이미지를 분석하고 다음 정보를 JSON 형태로 추출해주세요:

{
  "outline": {
    "x": 0,
    "y": 0,
    "width": 전체_창고_너비,
    "height": 전체_창고_높이
  },
  "racks": [
    {
      "id": "A",
      "x": x좌표,
      "y": y좌표,
      "width": 너비,
      "height": 높이,
      "capacity": 예상용량,
      "currentStock": null
    }
  ],
  "aisles": [
    {
      "startX": 시작x,
      "startY": 시작y,
      "endX": 끝x,
      "endY": 끝y,
      "width": 통로_너비
    }
  ],
  "gates": [
    {
      "x": x좌표,
      "y": y좌표,
      "width": 너비,
      "height": 높이,
      "type": "entrance"
    }
  ]
}

좌표는 픽셀 단위로, 창고의 실제 구조를 파악하여 정확한 위치 정보를 제공해주세요.
랙 ID는 A, B, C 등의 알파벳 또는 숫자로 명명해주세요.
"""
            
            # Gemini Vision API 호출
            result = await self.ai_service.analyze_image_with_prompt(image_data, prompt)
            
            if result.get("success"):
                # JSON 파싱 시도
                try:
                    warehouse_data = json.loads(result["response"])
                    return warehouse_data
                except json.JSONDecodeError:
                    # JSON 파싱 실패 시 기본 레이아웃 반환
                    logger.warning("AI 응답 JSON 파싱 실패, 기본 레이아웃 사용")
                    return self._get_default_warehouse_layout()
            else:
                raise Exception(f"AI 분석 실패: {result.get('error', 'Unknown error')}")
            
        except Exception as e:
            logger.error(f"AI 분석 오류: {str(e)}")
            # 오류 시 기본 레이아웃 반환
            return self._get_default_warehouse_layout()
    
    def _get_default_warehouse_layout(self) -> Dict[str, Any]:
        """기본 창고 레이아웃 데이터"""
        return {
            "outline": {
                "x": 50,
                "y": 50,
                "width": 700,
                "height": 500
            },
            "racks": [
                {"id": "A", "x": 100, "y": 100, "width": 50, "height": 100, "capacity": 100, "currentStock": 75},
                {"id": "B", "x": 200, "y": 100, "width": 50, "height": 100, "capacity": 120, "currentStock": 90},
                {"id": "C", "x": 300, "y": 100, "width": 50, "height": 100, "capacity": 80, "currentStock": 60},
                {"id": "D", "x": 500, "y": 100, "width": 50, "height": 100, "capacity": 150, "currentStock": 120},
                {"id": "E", "x": 600, "y": 100, "width": 50, "height": 100, "capacity": 100, "currentStock": 85},
            ],
            "aisles": [
                {"startX": 80, "startY": 300, "endX": 720, "endY": 300, "width": 20}
            ],
            "gates": [
                {"x": 350, "y": 45, "width": 100, "height": 10, "type": "entrance"}
            ]
        }
    
    # 유틸리티 메서드들
    def _calculate_bounds(self, msp) -> Optional[Dict[str, float]]:
        """모델스페이스의 경계 계산"""
        if not msp:
            return None
        
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        for entity in msp:
            if hasattr(entity.dxf, 'start') and hasattr(entity.dxf, 'end'):
                # LINE
                min_x = min(min_x, entity.dxf.start.x, entity.dxf.end.x)
                max_x = max(max_x, entity.dxf.start.x, entity.dxf.end.x)
                min_y = min(min_y, entity.dxf.start.y, entity.dxf.end.y)
                max_y = max(max_y, entity.dxf.start.y, entity.dxf.end.y)
            elif hasattr(entity.dxf, 'center'):
                # CIRCLE
                center = entity.dxf.center
                radius = entity.dxf.radius
                min_x = min(min_x, center.x - radius)
                max_x = max(max_x, center.x + radius)
                min_y = min(min_y, center.y - radius)
                max_y = max(max_y, center.y + radius)
        
        if min_x == float('inf'):
            return None
        
        return {
            'min_x': min_x,
            'min_y': min_y,
            'max_x': max_x,
            'max_y': max_y
        }
    
    def _parse_entity(self, entity) -> Optional[Dict[str, Any]]:
        """DXF 엔티티를 파싱"""
        try:
            entity_type = entity.dxftype()
            
            if entity_type == 'LINE':
                return {
                    'type': 'lines',
                    'start': {'x': entity.dxf.start.x, 'y': entity.dxf.start.y},
                    'end': {'x': entity.dxf.end.x, 'y': entity.dxf.end.y}
                }
            elif entity_type == 'CIRCLE':
                return {
                    'type': 'circles',
                    'center': {'x': entity.dxf.center.x, 'y': entity.dxf.center.y},
                    'radius': entity.dxf.radius
                }
            elif entity_type == 'TEXT':
                return {
                    'type': 'texts',
                    'position': {'x': entity.dxf.insert.x, 'y': entity.dxf.insert.y},
                    'text': entity.dxf.text,
                    'height': entity.dxf.height
                }
            # 추가 엔티티 타입들...
            
            return None
            
        except Exception as e:
            logger.warning(f"엔티티 파싱 오류: {str(e)}")
            return None
    
    def _interpret_warehouse_layout(self, entities: Dict, bounds: Dict) -> Dict[str, Any]:
        """파싱된 엔티티들로부터 창고 레이아웃 해석"""
        # 이 부분은 DXF 엔티티들을 분석하여 창고 구조를 해석하는 복잡한 로직
        # 현재는 간단한 예시로 구현
        
        warehouse_data = {
            "outline": {
                "x": bounds['min_x'],
                "y": bounds['min_y'],
                "width": bounds['max_x'] - bounds['min_x'],
                "height": bounds['max_y'] - bounds['min_y']
            },
            "racks": [],
            "aisles": [],
            "gates": []
        }
        
        # 직사각형들을 랙으로 해석
        for i, rect in enumerate(entities.get('rectangles', [])[:10]):  # 최대 10개
            warehouse_data["racks"].append({
                "id": chr(65 + i),  # A, B, C, ...
                "x": rect.get('x', 0),
                "y": rect.get('y', 0),
                "width": rect.get('width', 50),
                "height": rect.get('height', 100),
                "capacity": 100,
                "currentStock": None
            })
        
        return warehouse_data
    
    def _draw_entity_on_image(self, draw, entity, bounds, scale, margin):
        """DXF 엔티티를 이미지에 그리기"""
        try:
            entity_type = entity.dxftype()
            
            def coord_transform(x, y):
                # DXF 좌표를 이미지 좌표로 변환
                px = int((x - bounds['min_x']) * scale) + margin
                py = int((bounds['max_y'] - y) * scale) + margin  # Y축 뒤집기
                return px, py
            
            if entity_type == 'LINE':
                start = coord_transform(entity.dxf.start.x, entity.dxf.start.y)
                end = coord_transform(entity.dxf.end.x, entity.dxf.end.y)
                draw.line([start, end], fill='black', width=1)
                
            elif entity_type == 'CIRCLE':
                center = coord_transform(entity.dxf.center.x, entity.dxf.center.y)
                radius = int(entity.dxf.radius * scale)
                bbox = [
                    center[0] - radius, center[1] - radius,
                    center[0] + radius, center[1] + radius
                ]
                draw.ellipse(bbox, outline='black')
            
            # 추가 엔티티 타입들...
            
        except Exception as e:
            logger.warning(f"엔티티 그리기 오류: {str(e)}")
    
    async def cleanup_temp_files(self, file_path: str):
        """임시 파일 정리"""
        try:
            if os.path.exists(file_path):
                if os.path.isfile(file_path):
                    os.remove(file_path)
                else:
                    shutil.rmtree(file_path)
                logger.info(f"임시 파일 정리 완료: {file_path}")
        except Exception as e:
            logger.warning(f"임시 파일 정리 오류: {str(e)}")