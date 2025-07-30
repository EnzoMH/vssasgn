import os
import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from .ai_service import WarehouseAI

class PDFAnalysisService:
    """PDF 문서 분석 및 AI 처리 서비스"""
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.ai_service = WarehouseAI(logger=self.logger)
        
        if fitz is None:
            self.logger.warning("⚠️ PyMuPDF가 설치되지 않았습니다. pip install PyMuPDF를 실행해주세요.")
    
    def extract_text_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """PDF에서 텍스트 및 이미지 정보 추출"""
        if fitz is None:
            raise ImportError("PyMuPDF가 설치되지 않았습니다. pip install PyMuPDF를 실행해주세요.")
        
        try:
            pdf_document = fitz.open(pdf_path)
            
            extracted_data = {
                "metadata": pdf_document.metadata,
                "page_count": pdf_document.page_count,
                "pages": [],
                "full_text": "",
                "images": []
            }
            
            full_text_parts = []
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                
                # 텍스트 추출
                page_text = page.get_text()
                
                # 이미지 정보 추출
                image_list = page.get_images()
                page_images = []
                
                for img_index, img in enumerate(image_list):
                    try:
                        # 이미지 메타데이터만 추출 (실제 이미지는 너무 클 수 있음)
                        xref = img[0]
                        img_dict = pdf_document.extract_image(xref)
                        page_images.append({
                            "image_index": img_index,
                            "width": img_dict.get("width"),
                            "height": img_dict.get("height"),
                            "ext": img_dict.get("ext"),
                            "size": len(img_dict.get("image", b""))
                        })
                    except Exception as e:
                        self.logger.warning(f"이미지 {img_index} 처리 중 오류: {e}")
                
                page_info = {
                    "page_number": page_num + 1,
                    "text": page_text,
                    "text_length": len(page_text),
                    "images": page_images,
                    "image_count": len(page_images)
                }
                
                extracted_data["pages"].append(page_info)
                full_text_parts.append(page_text)
            
            # 전체 텍스트 합치기
            extracted_data["full_text"] = "\n\n".join(full_text_parts)
            
            pdf_document.close()
            
            self.logger.info(f"✅ PDF 텍스트 추출 완료: {pdf_path}")
            self.logger.info(f"📄 총 {extracted_data['page_count']}페이지, "
                           f"텍스트 길이: {len(extracted_data['full_text'])}자")
            
            return extracted_data
            
        except Exception as e:
            self.logger.error(f"❌ PDF 텍스트 추출 실패: {e}")
            raise
    
    async def analyze_document_with_ai(self, extracted_data: Dict[str, Any], 
                                     analysis_prompt: str = None) -> Dict[str, Any]:
        """AI를 통한 문서 내용 분석 및 구조화"""
        
        if not analysis_prompt:
            analysis_prompt = """
당신은 문서 분석 전문가입니다. 주어진 PDF 문서의 내용을 분석하여 다음과 같이 구조화된 정보를 제공해주세요:

**분석 결과를 다음 JSON 형태로 정리해주세요:**

```json
{
    "document_summary": {
        "title": "문서 제목",
        "type": "문서 유형 (과제, 매뉴얼, 보고서 등)",
        "main_purpose": "문서의 주요 목적",
        "key_sections": ["주요 섹션들의 리스트"]
    },
    "detailed_structure": {
        "sections": [
            {
                "section_name": "섹션명",
                "content_summary": "해당 섹션의 주요 내용 요약",
                "key_points": ["핵심 포인트들"],
                "requirements": ["요구사항들 (있다면)"],
                "deliverables": ["산출물들 (있다면)"]
            }
        ]
    },
    "tasks_and_requirements": {
        "step1": {
            "title": "Step 1 제목",
            "description": "상세 설명",
            "requirements": ["요구사항들"],
            "deliverables": ["산출물들"],
            "technologies": ["사용 기술/도구들"]
        },
        "step2": {
            "title": "Step 2 제목", 
            "description": "상세 설명",
            "requirements": ["요구사항들"],
            "deliverables": ["산출물들"],
            "technologies": ["사용 기술/도구들"]
        }
    },
    "technical_specifications": {
        "programming_languages": ["사용할 프로그래밍 언어들"],
        "frameworks": ["프레임워크들"],
        "databases": ["데이터베이스"],
        "apis": ["API들"],
        "other_tools": ["기타 도구들"]
    },
    "evaluation_criteria": {
        "criteria": ["평가 기준들"],
        "weights": ["가중치 (명시되어 있다면)"]
    },
    "timeline_and_deadlines": {
        "overall_deadline": "전체 마감일",
        "milestones": ["중간 마일스톤들"]
    }
}
```

**문서 내용:**
"""
        
        try:
            # 텍스트가 너무 긴 경우 분할 처리
            full_text = extracted_data.get("full_text", "")
            
            if len(full_text) > 50000:  # 50,000자 이상인 경우
                self.logger.info("📄 문서가 길어서 페이지별로 분할 분석을 진행합니다.")
                
                # 페이지별 분석 후 통합
                page_analyses = []
                for page_info in extracted_data.get("pages", []):
                    if len(page_info["text"].strip()) > 100:  # 의미있는 텍스트가 있는 페이지만
                        page_prompt = f"{analysis_prompt}\n\n페이지 {page_info['page_number']}:\n{page_info['text']}"
                        page_result = await self.ai_service.answer_query(
                            "이 페이지의 내용을 분석해주세요.", 
                            {"page_text": page_info['text']}
                        )
                        page_analyses.append({
                            "page_number": page_info['page_number'],
                            "analysis": page_result
                        })
                
                # 전체 통합 분석
                integration_prompt = f"""
다음은 각 페이지별 분석 결과입니다. 이를 통합하여 전체 문서의 구조화된 분석을 제공해주세요:

{chr(10).join([f"페이지 {pa['page_number']}: {pa['analysis']}" for pa in page_analyses])}

위의 페이지별 분석을 바탕으로 전체 문서의 통합된 구조화 분석을 JSON 형태로 제공해주세요.
"""
                
                final_analysis = await self.ai_service.answer_query(
                    integration_prompt,
                    {"page_analyses": page_analyses}
                )
                
                return {
                    "analysis_method": "multi_page_analysis",
                    "page_count": len(page_analyses),
                    "page_analyses": page_analyses,
                    "integrated_analysis": final_analysis,
                    "document_info": {
                        "total_pages": extracted_data.get("page_count", 0),
                        "total_text_length": len(full_text),
                        "has_images": len(extracted_data.get("images", [])) > 0
                    }
                }
            
            else:
                # 전체 문서 한번에 분석
                complete_prompt = f"{analysis_prompt}\n\n{full_text}"
                
                analysis_result = await self.ai_service.answer_query(
                    "주어진 문서를 분석하여 구조화된 정보를 제공해주세요.",
                    {"full_document": full_text}
                )
                
                return {
                    "analysis_method": "full_document_analysis", 
                    "analysis_result": analysis_result,
                    "document_info": {
                        "total_pages": extracted_data.get("page_count", 0),
                        "total_text_length": len(full_text),
                        "has_images": len(extracted_data.get("images", [])) > 0
                    }
                }
                
        except Exception as e:
            self.logger.error(f"❌ AI 문서 분석 실패: {e}")
            raise
    
    async def process_pdf_completely(self, pdf_path: str, 
                                   custom_prompt: str = None) -> Dict[str, Any]:
        """PDF 전체 처리 파이프라인 (텍스트 추출 + AI 분석)"""
        
        try:
            self.logger.info(f"🚀 PDF 처리 시작: {pdf_path}")
            
            # 1. PDF에서 텍스트 추출
            extracted_data = self.extract_text_from_pdf(pdf_path)
            
            # 2. AI 분석
            analysis_result = await self.analyze_document_with_ai(
                extracted_data, 
                analysis_prompt=custom_prompt
            )
            
            # 3. 결과 통합
            complete_result = {
                "pdf_info": {
                    "file_path": pdf_path,
                    "file_name": Path(pdf_path).name,
                    "metadata": extracted_data.get("metadata", {}),
                    "extraction_success": True
                },
                "extracted_data": extracted_data,
                "ai_analysis": analysis_result,
                "processing_timestamp": asyncio.get_event_loop().time()
            }
            
            self.logger.info("✅ PDF 처리 완료")
            return complete_result
            
        except Exception as e:
            self.logger.error(f"❌ PDF 처리 실패: {e}")
            return {
                "pdf_info": {
                    "file_path": pdf_path,
                    "file_name": Path(pdf_path).name,
                    "extraction_success": False,
                    "error": str(e)
                },
                "extracted_data": None,
                "ai_analysis": None,
                "processing_timestamp": asyncio.get_event_loop().time()
            }

# 편의 함수들
async def analyze_vss_assignment(pdf_path: str = None) -> Dict[str, Any]:
    """VSS 과제 PDF 분석을 위한 특화된 함수"""
    
    if pdf_path is None:
        pdf_path = r"C:\Users\MyoengHo Shin\pjt\vss_asgnM\legacy\VSS_입사테스트과제_AI.pdf"
    
    vss_prompt = """
당신은 VSS 입사 테스트 과제를 분석하는 전문 컨설턴트입니다. 
현재 우리는 창고 관리 시스템(입고/출고 데이터, 상품 데이터)과 Gemini AI 기반 RAG를 이미 구축한 상태입니다.

**매우 구체적이고 실행 가능한 분석을 요청합니다. 반드시 다음 JSON 구조로 답변해주세요:**

```json
{
    "critical_insights": {
        "main_challenge": "이 과제에서 가장 어려운 부분은 무엇인가?",
        "competitive_advantage": "우리가 이미 가진 강점은 무엇인가?",
        "time_bottlenecks": "시간이 가장 많이 걸릴 작업들",
        "must_have_vs_nice_to_have": "필수 구현 vs 선택적 구현 구분"
    },
    "step_by_step_detailed": {
        "step1": {
            "exact_requirements": ["정확히 무엇을 구현해야 하는지"],
            "current_status": "우리 프로젝트에서 이미 완료된 부분",
            "gap_analysis": "추가로 개발해야 할 부분들",
            "specific_tasks": ["구체적인 개발 작업 리스트"],
            "code_components": ["구현해야 할 코드 컴포넌트들"],
            "integration_points": "기존 시스템과의 연결 방법"
        },
        "step2": {
            "chart_requirements": ["구체적으로 어떤 차트들을 만들어야 하는지"],
            "llm_chart_logic": "LLM이 차트를 생성하는 구체적인 로직",
            "user_interaction": "사용자 인터랙션 구현 방법",
            "data_flow": "inOutboundData에서 차트까지의 데이터 흐름",
            "kpi_calculations": "KPI/LOI 계산 공식들",
            "frontend_requirements": "프론트엔드에서 구현해야 할 기능들"
        },
        "step3_alternatives": {
            "dwg_problem": "DWG 파일이 없는 문제 해결 방안",
            "virtual_approach": "가상 도면 시스템 구현 방법",
            "canvas_implementation": "Canvas/WebGL 구현 전략",
            "data_structure": "도면 데이터를 어떻게 구조화할 것인가",
            "realistic_scope": "실제로 구현 가능한 범위"
        },
        "step4": {
            "multimodal_scope": "멀티모달 구현 범위와 방법",
            "integration_strategy": "Step 1-3와의 통합 방법",
            "demo_scenarios": "데모에서 보여줄 시나리오들"
        }
    },
    "technical_roadmap": {
        "week1_priorities": ["첫 주에 집중할 핵심 작업들"],
        "week2_priorities": ["둘째 주 작업들"],
        "minimum_viable_demo": "최소한의 데모를 위해 필요한 것들",
        "technology_choices": {
            "frontend": "React vs 기존 HTML/JS 중 어느 것이 현실적인가",
            "charts": "Chart.js vs D3.js vs 기타 추천",
            "3d_rendering": "Three.js vs Canvas vs WebGL 중 선택",
            "file_upload": "파일 업로드 구현 방법"
        }
    },
    "risk_mitigation": {
        "step3_backup_plan": "DWG 구현이 안 될 경우 B플랜",
        "frontend_challenges": "프론트엔드 개발 시간 부족 해결책",
        "integration_risks": "시스템 통합 시 발생할 수 있는 문제들",
        "demo_fallbacks": "데모 시연 시 문제 발생 대비책"
    },
    "evaluation_strategy": {
        "showcase_priorities": "평가자에게 어떤 부분을 강조할 것인가",
        "technical_depth": "기술적 깊이를 보여줄 수 있는 부분들",
        "business_value": "비즈니스 가치를 어필할 수 있는 요소들",
        "innovation_points": "혁신적이라고 어필할 수 있는 부분들"
    },
    "immediate_action_items": {
        "today": ["오늘 당장 시작할 수 있는 작업들"],
        "this_week": ["이번 주에 완료해야 할 작업들"],
        "next_week": ["다음 주 목표들"],
        "dependencies": "작업 간 의존성 관계"
    }
}
```

**분석 시 특별히 고려해야 할 현재 상황:**
- 이미 구축됨: FastAPI 백엔드, Gemini AI, 창고 입고/출고 데이터 분석
- 있음: 기본 HTML/CSS/JS 프론트엔드, Chart.js
- 없음: React 환경, DWG 파일, 고급 3D 시각화
- 제약: 프론트엔드 개발자 없음, 높은 UX/UI 요구사항

**핵심 질문들에 대한 구체적 답변 요청:**
1. Step 2에서 "LLM 활용 차트 드로잉"의 정확한 의미는?
2. Step 3 DWG 없이 어떻게 우회할 것인가?
3. 각 Step별 최소 구현 vs 최대 구현 범위는?
4. 현재 창고 데이터로 어떤 인상적인 데모를 만들 수 있는가?
5. 평가자가 가장 주목할 기술적 포인트는?
"""
    
    service = PDFAnalysisService()
    result = await service.process_pdf_completely(pdf_path, vss_prompt)
    
    return result

# 실행 스크립트
if __name__ == "__main__":
    import asyncio
    
    async def main():
        try:
            result = await analyze_vss_assignment()
            
            print("=" * 80)
            print("🎯 VSS 과제 분석 결과")
            print("=" * 80)
            
            if result["pdf_info"]["extraction_success"]:
                print(f"✅ PDF 처리 성공: {result['pdf_info']['file_name']}")
                print(f"📄 페이지 수: {result['extracted_data']['page_count']}")
                print(f"📝 텍스트 길이: {len(result['extracted_data']['full_text'])}자")
                print("\n🤖 AI 분석 결과:")
                print("-" * 50)
                
                if result["ai_analysis"]["analysis_method"] == "multi_page_analysis":
                    print("📋 통합 분석 결과:")
                    print(result["ai_analysis"]["integrated_analysis"])
                else:
                    print("📋 전체 분석 결과:")
                    print(result["ai_analysis"]["analysis_result"])
            else:
                print(f"❌ PDF 처리 실패: {result['pdf_info']['error']}")
                
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
    
    asyncio.run(main())