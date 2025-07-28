import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# 현재 스크립트의 경로를 sys.path에 추가하여 모듈 임포트 가능하도록 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.data_service import DataService
from app.services.data_analysis_service import DataAnalysisService
from app.services.ai_service import WarehouseAI
from app.models.ml_models import AnomalyDetector # AnomalyDetector 임포트 경로 수정

# 환경 변수 로드
load_dotenv()

# 로거 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("데이터 분석 스크립트 시작")

    # 서비스 인스턴스 초기화
    data_service = DataService()
    ai_service = WarehouseAI(logger=logger) # AI 서비스 초기화
    # AnomalyDetector와 DataAnalysisService 초기화
    anomaly_detector = AnomalyDetector()
    data_analysis_service = DataAnalysisService(data_service, anomaly_detector)

    # 데이터 로드
    logger.info("원본 데이터 로딩 중...")
    await data_service.load_all_data(rawdata_path="../rawdata") # Corrected path
    if not data_service.data_loaded:
        logger.error("데이터 로드에 실패했습니다. rawdata 디렉토리와 파일들을 확인해주세요.")
        return
    logger.info("원본 데이터 로드 완료.")

    print("\n--- 📊 데이터 분석 결과 ---\n")

    # 1. 각 데이터프레임 기술 통계 요약
    print("### 1. 입고 데이터 기술 통계 ###")
    inbound_stats = data_analysis_service.get_descriptive_stats('inbound_data')
    print(inbound_stats)

    print("\n### 2. 출고 데이터 기술 통계 ###")
    outbound_stats = data_analysis_service.get_descriptive_stats('outbound_data')
    print(outbound_stats)

    print("\n### 3. 상품 마스터 데이터 기술 통계 ###")
    product_stats = data_analysis_service.get_descriptive_stats('product_master')
    print(product_stats)

    # 4. 일별 물동량 요약
    print("\n### 4. 일별 입출고 물동량 요약 ###")
    daily_movement_df = data_analysis_service.get_daily_movement_summary() # DataFrame으로 받음
    print(daily_movement_df.to_dict(orient='records')) # Dict 리스트로 출력

    # 5. 상품별 인사이트
    print("\n### 5. 상품별 입출고 인사이트 ###")
    product_insights = data_analysis_service.get_product_insights()
    print(product_insights)

    # 6. 랙 활용률 요약
    print("\n### 6. 랙 활용률 요약 ###")
    rack_utilization = data_analysis_service.get_rack_utilization_summary()
    print(rack_utilization)

    print("\n### 7. 이상 징후 탐지 결과 ###")
    anomalies_result = await data_analysis_service.detect_anomalies_data() # data_analysis_service에서 호출
    if anomalies_result["anomalies"]:
        print(f"감지된 이상 징후 날짜: {anomalies_result['anomalies']}")
        print(anomalies_result["message"])
    else:
        print(anomalies_result["message"])

    print("\n--- 🤖 AI 기반 인사이트 추출 ---\n")

    # AI에게 데이터 분석 결과에 대한 인사이트 요청
    ai_query_results = {
        "inbound_stats": inbound_stats,
        "outbound_stats": outbound_stats,
        "product_stats": product_stats,
        "daily_movement": daily_movement_df.to_dict(orient='records'), # AI에 전달 시 Dict 리스트로 변환
        "product_insights": product_insights,
        "rack_utilization": rack_utilization,
        "anomalies": anomalies_result # 이상 징후 결과 추가
    }

    ai_question = (
        "다음은 스마트 물류창고의 데이터 분석 결과입니다. "
        "주요 트렌드, 특이사항, 개선점, 이상 징후, 그리고 이 데이터로 무엇을 더 할 수 있을지에 대한 " # 질문에 '이상 징후' 추가
        "심층적인 인사이트를 제공해주세요. 한국어로 답변해주세요."
    )

    try:
        ai_response = await ai_service.answer_query(ai_question, ai_query_results)
        print("### AI Chatbot의 인사이트 ###")
        print(ai_response)
    except Exception as e:
        logger.error(f"AI 서비스 호출 중 오류 발생: {e}")
        print(f"AI 인사이트를 가져오는 데 실패했습니다: {e}")

    logger.info("데이터 분석 스크립트 종료")

if __name__ == "__main__":
    # Windows에서 asyncio.run()이 충돌할 수 있으므로, ProactorEventLoop 사용을 명시
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main()) 