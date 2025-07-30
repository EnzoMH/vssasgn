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
            
            print(f"\n🤖 AI 분석 미리보기:")
            analysis = result["ai_analysis"]
            if analysis["analysis_method"] == "multi_page_analysis":
                preview = analysis["integrated_analysis"][:500] + "..."
            else:
                preview = analysis["analysis_result"][:500] + "..."
            print(f"   {preview}")
            
            print(f"\n📝 전체 분석 결과는 {output_file}에서 확인하세요!")
        else:
            print(f"❌ PDF 처리 실패: {result['pdf_info'].get('error', '알 수 없는 오류')}")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())