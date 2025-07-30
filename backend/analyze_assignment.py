"""
VSS 과제 PDF 분석 실행 스크립트
"""
import asyncio
import sys
import json
import logging
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pdf_analysis.log', encoding='utf-8')
    ]
)

from app.services.pdf_analysis_service import analyze_vss_assignment

async def main():
    print("🚀 VSS 입사 테스트 과제 분석을 시작합니다...")
    print("-" * 60)
    
    try:
        # PDF 분석 실행
        result = await analyze_vss_assignment()
        
        # 결과 저장
        output_file = project_root / "assignment_analysis.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 분석 완료! 결과가 {output_file}에 저장되었습니다.")
        
        # 주요 결과 출력
        if result["pdf_info"]["extraction_success"]:
            print(f"\n📊 기본 정보:")
            print(f"   - 파일명: {result['pdf_info']['file_name']}")
            print(f"   - 페이지 수: {result['extracted_data']['page_count']}")
            print(f"   - 텍스트 길이: {len(result['extracted_data']['full_text']):,}자")
            
            print(f"\n🤖 AI 분석 결과:")
            print("=" * 80)
            analysis = result["ai_analysis"]
            if analysis["analysis_method"] == "multi_page_analysis":
                analysis_text = analysis["integrated_analysis"]
            else:
                analysis_text = analysis["analysis_result"]
            
            # JSON 형태인지 확인하고 파싱 시도
            try:
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', analysis_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    parsed_json = json.loads(json_str)
                    
                    print("🎯 핵심 인사이트:")
                    if "critical_insights" in parsed_json:
                        insights = parsed_json["critical_insights"]
                        for key, value in insights.items():
                            print(f"   • {key}: {value}")
                    
                    print(f"\n📋 즉시 실행 가능한 작업들:")
                    if "immediate_action_items" in parsed_json:
                        actions = parsed_json["immediate_action_items"]
                        if "today" in actions:
                            print(f"   🚀 오늘: {', '.join(actions['today'][:3])}...")
                        if "this_week" in actions:
                            print(f"   📅 이번 주: {', '.join(actions['this_week'][:3])}...")
                    
                    print(f"\n⚠️ 주요 위험 요소:")
                    if "risk_mitigation" in parsed_json:
                        risks = parsed_json["risk_mitigation"]
                        for key, value in list(risks.items())[:3]:
                            print(f"   • {key}: {value[:100]}...")
                    
                    print(f"\n💡 기술 선택 추천:")
                    if "technical_roadmap" in parsed_json and "technology_choices" in parsed_json["technical_roadmap"]:
                        tech = parsed_json["technical_roadmap"]["technology_choices"]
                        for key, value in tech.items():
                            print(f"   • {key}: {value}")
                            
                else:
                    # JSON 파싱 실패시 기존 방식
                    preview = analysis_text[:1000] + "..."
                    print(f"{preview}")
                    
            except Exception as e:
                # 파싱 오류시 기존 방식
                preview = analysis_text[:1000] + "..."
                print(f"{preview}")
            
            print("=" * 80)
            print(f"\n📝 전체 상세 분석 결과는 {output_file}에서 확인하세요!")
            print(f"💡 다음 단계: 분석 결과를 바탕으로 구체적인 개발 계획을 세워보세요!")
        else:
            print(f"❌ PDF 처리 실패: {result['pdf_info'].get('error', '알 수 없는 오류')}")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())