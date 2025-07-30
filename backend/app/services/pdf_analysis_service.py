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
        pdf_path = r"C:\Users\MyoengHo Shin\pjt\vss_asgnM\VSS_입사테스트과제_AI.pdf"
    
    vss_prompt = """
당신은 VSS 입사 테스트 과제를 분석하는 전문가입니다. 
이 과제는 AI/ML 관련 기술 과제로 보이며, 단계별로 구성되어 있을 것입니다.

다음 형태로 분석 결과를 제공해주세요:

```json
{
    "assignment_overview": {
        "company": "VSS",
        "position": "AI/ML 관련 직무",
        "assignment_type": "입사 테스트 과제",
        "main_objective": "과제의 주요 목표"
    },
    "steps_breakdown": {
        "step1": {
            "title": "Step 1 제목",
            "objective": "목표",
            "requirements": ["요구사항들"],
            "deliverables": ["제출물들"],
            "technologies": ["필요 기술들"],
            "difficulty": "난이도 (1-5)",
            "estimated_time": "예상 소요 시간"
        },
        "step2": {
            "title": "Step 2 제목",
            "objective": "목표", 
            "requirements": ["요구사항들"],
            "deliverables": ["제출물들"],
            "technologies": ["필요 기술들"],
            "difficulty": "난이도 (1-5)",
            "estimated_time": "예상 소요 시간"
        },
        "step3": {
            "title": "Step 3 제목 (DWG/CAD 관련)",
            "objective": "목표",
            "requirements": ["요구사항들"], 
            "deliverables": ["제출물들"],
            "technologies": ["필요 기술들"],
            "difficulty": "난이도 (1-5)",
            "estimated_time": "예상 소요 시간",
            "feasibility": "현재 데이터 상황에서의 실현 가능성"
        },
        "step4": {
            "title": "Step 4 제목",
            "objective": "목표",
            "requirements": ["요구사항들"],
            "deliverables": ["제출물들"],
            "dependencies": ["Step 2 완료 후 진행 가능한 부분들"],
            "difficulty": "난이도 (1-5)",
            "estimated_time": "예상 소요 시간"
        }
    },
    "technical_stack": {
        "programming_languages": ["Python", "기타"],
        "ml_frameworks": ["scikit-learn", "TensorFlow", "PyTorch", "기타"],
        "data_processing": ["pandas", "numpy", "기타"],
        "visualization": ["matplotlib", "plotly", "기타"],
        "web_frameworks": ["FastAPI", "Flask", "기타"],
        "databases": ["필요한 DB들"],
        "cad_tools": ["CAD 관련 도구들 (Step 3)"]
    },
    "current_project_alignment": {
        "data_available": ["현재 가지고 있는 데이터들 (입고/출고 데이터)"],
        "completed_components": ["이미 완료된 부분들 (데이터 분석)"],
        "missing_components": ["부족한 부분들 (DWG 파일 등)"],
        "adaptable_steps": ["현재 상황에 맞게 수정 가능한 단계들"]
    },
    "implementation_strategy": {
        "immediate_next_steps": ["바로 시작할 수 있는 작업들"],
        "step_by_step_plan": ["단계별 실행 계획"],
        "risk_factors": ["위험 요소들 (데이터 부족 등)"],
        "mitigation_strategies": ["위험 완화 방안들"]
    },
    "evaluation_criteria": {
        "technical_competency": ["기술적 역량 평가 기준"],
        "code_quality": ["코드 품질 기준"],
        "documentation": ["문서화 요구사항"],
        "presentation": ["발표/데모 요구사항"]
    }
}
```

분석 시 특히 다음 사항들을 주의깊게 살펴보세요:
- 각 Step별 구체적인 요구사항
- 현재 가지고 있는 창고 데이터 (입고/출고 데이터)와의 연관성
- Step 3의 DWG/CAD 파일 요구사항과 대안책
- RAG (Retrieval-Augmented Generation) 구축 요구사항
- ML/AI 모델 개발 요구사항
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