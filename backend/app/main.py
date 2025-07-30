from fastapi import FastAPI, Request, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from .utils.ai_chat import WarehouseChatbot
from .services.data_service import DataService
from .models.ml_models import DemandPredictor, ProductClusterer, AnomalyDetector # AnomalyDetector 추가
from .services.data_analysis_service import DataAnalysisService
from .services.ai_service import WarehouseAI
from .services.vector_db_service import VectorDBService
from .services.cad_service import CADService
import logging
import io
import pandas as pd
import os
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv, find_dotenv

# 로거 설정 (환경변수 로딩보다 먼저)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# .env 파일을 자동으로 찾아서 로드 (.env 파일 위치에 상관없이)
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)
    logger.info(f"✅ .env 파일 로드됨: {dotenv_path}")
else:
    logger.warning("⚠️ .env 파일을 찾을 수 없습니다. 시스템 환경변수를 사용합니다.")

app = FastAPI(title="Warehouse Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 단일 서버이므로 모든 origin 허용
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙 설정
app.mount("/static", StaticFiles(directory="static"), name="static")

# 메인 페이지 라우트
@app.get("/", response_class=HTMLResponse)
async def main_page():
    with open("static/index.html", "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)

# DataService, Chatbot, ML Models, DataAnalysisService, AI Service, VectorDB 인스턴스 초기화
data_service = DataService()
demand_predictor = DemandPredictor()
product_clusterer = ProductClusterer()
anomaly_detector = AnomalyDetector() # AnomalyDetector 인스턴스 추가
data_analysis_service = DataAnalysisService(data_service, anomaly_detector) # anomaly_detector 전달
ai_service = WarehouseAI() # AI 서비스 인스턴스 추가
vector_db_service = VectorDBService(data_service=data_service) # 벡터 DB 서비스 추가
cad_service = CADService(ai_service=ai_service) # CAD 서비스 추가
chatbot = WarehouseChatbot(data_service=data_service, vector_db_service=vector_db_service) # 서비스 주입

# ML 모델 학습 상태
model_trained = {"demand_predictor": False, "product_clusterer": False, "anomaly_detector": False} # anomaly_detector 상태 추가

@app.on_event("startup")
async def startup_event():
    logger.info("서버 시작 이벤트 발생: 데이터 로딩 시작...")
    await data_service.load_all_data(rawdata_path="../rawdata")
    logger.info("데이터 로딩 완료.")
    
    # 서버 시작 시 ML 모델 사전 학습 (선택 사항)
    try:
        await train_demand_predictor()
        await train_product_clusterer()
        # 이상 탐지 모델은 data_analysis_service.detect_anomalies_data() 호출 시 내부적으로 학습될 수 있음
        # 여기서는 단순히 학습 상태만 True로 설정
        if data_service.data_loaded:
            anomaly_result = await data_analysis_service.detect_anomalies_data() # 학습 및 탐지 수행
            if anomaly_result["anomalies"] is not None: # 학습 성공 여부 판단
                model_trained["anomaly_detector"] = True
            else:
                logger.warning(f"이상 탐지 모델 사전 학습 실패: {anomaly_result.get('message', '알 수 없는 오류')}")

    except Exception as e:
        logger.warning(f"ML 모델 사전 학습 중 오류 발생: {e}")
    
    # 벡터 데이터베이스 인덱싱
    try:
        if data_service.data_loaded:
            logger.info("벡터 데이터베이스 인덱싱 시작...")
            indexing_success = await vector_db_service.index_warehouse_data()
            if indexing_success:
                logger.info("✅ 벡터 데이터베이스 인덱싱 완료")
            else:
                logger.warning("⚠️ 벡터 데이터베이스 인덱싱 실패")
        else:
            logger.warning("⚠️ 데이터가 로드되지 않아 벡터 DB 인덱싱을 건너뜁니다.")
    except Exception as e:
        logger.error(f"❌ 벡터 DB 인덱싱 중 오류 발생: {e}")


async def train_demand_predictor():
    if model_trained["demand_predictor"] or not data_service.data_loaded:
        return
    
    logger.info("수요 예측 모델 학습 시작...")
    try:
        # TODO: 실제 데이터 전처리 및 피처 엔지니어링 필요
        # 여기서는 임시 데이터로 대체
        # 실제로는 data_service.inbound_data와 outbound_data를 결합하여 피처를 만들어야 합니다.

        # 예시: 과거 N일간의 출고량을 피처로, 다음날 출고량을 예측
        # 편의상 현재는 임의의 데이터 생성
        dummy_data = {
            'feature1': [10, 12, 15, 13, 16, 18, 20],
            'feature2': [5, 6, 7, 6, 8, 9, 10],
            'target': [11, 14, 16, 14, 17, 19, 22] # 다음날 출고량
        }
        X = pd.DataFrame(dummy_data).drop(columns=['target'])
        y = pd.Series(dummy_data['target'])
        
        demand_predictor.train(X, y)
        model_trained["demand_predictor"] = True
        logger.info("수요 예측 모델 학습 완료.")
    except Exception as e:
        logger.error(f"수요 예측 모델 학습 중 오류 발생: {e}")
        model_trained["demand_predictor"] = False

async def train_product_clusterer():
    if model_trained["product_clusterer"] or not data_service.data_loaded:
        return
    
    logger.info("제품 클러스터링 모델 학습 시작...")
    try:
        # TODO: 실제 데이터 전처리 및 피처 엔지니어링 필요
        # 여기서는 임시 데이터로 대체
        # 실제로는 product_master와 입출고 데이터를 결합하여 제품별 특성을 만들어야 합니다.

        # 예시: 제품의 특정 속성 (회전율, 재고량 등)을 기반으로 클러스터링
        # 편의상 현재는 임의의 데이터 생성
        dummy_data = {
            'feature_a': [1.0, 2.0, 1.5, 3.0, 2.5, 1.2, 2.8],
            'feature_b': [100, 200, 150, 300, 250, 120, 280]
        }
        features = pd.DataFrame(dummy_data)

        product_clusterer.train(features)
        model_trained["product_clusterer"] = True
        logger.info("제품 클러스터링 모델 학습 완료.")
    except Exception as e:
        logger.error(f"제품 클러스터링 모델 학습 중 오류 발생: {e}")
        model_trained["product_clusterer"] = False

# train_anomaly_detector 함수는 data_analysis_service.detect_anomalies_data()로 이동되었으므로 주석 처리 또는 삭제
# async def train_anomaly_detector():
#    ...

@app.get("/api/dashboard/kpi")
async def get_kpi_data():
    # KPI 계산 로직
    # 실제 데이터 서비스에서 계산된 KPI를 반환하도록 수정
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    inbound_df = data_service.inbound_data
    outbound_df = data_service.outbound_data
    product_df = data_service.product_master

    # 예시 KPI 계산 (실제 데이터 기반으로 더 정교하게 구현 필요)
    total_inventory = int(product_df['현재고'].sum()) if '현재고' in product_df.columns else 0
    daily_throughput = int(len(inbound_df) + len(outbound_df)) # 간단하게 총 입출고 건수
    rack_utilization = 0.87 # 플레이스홀더
    inventory_turnover = 2.3 # 플레이스홀더

    return {
        "total_inventory": total_inventory,
        "daily_throughput": daily_throughput,
        "rack_utilization": rack_utilization,
        "inventory_turnover": inventory_turnover
    }

@app.get("/api/inventory/by-rack")
async def get_inventory_by_rack():
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    # 랙별 재고 현황 데이터 생성 (예시)
    # 실제 데이터프레임 구조에 따라 집계 로직 변경 필요
    product_df = data_service.product_master
    if '랙위치' in product_df.columns and '현재고' in product_df.columns:
        inventory_by_rack = product_df.groupby('랙위치')['현재고'].sum().reset_index()
        inventory_by_rack.columns = ['rackName', 'currentStock'] # 프론트엔드 차트 데이터 키에 맞춤
        # 임의의 용량 데이터 추가
        inventory_by_rack['capacity'] = inventory_by_rack['currentStock'] * 1.2 + 100 # 예시
        return inventory_by_rack.to_dict(orient='records')
    else:
        return []

@app.get("/api/trends/daily")
async def get_daily_trends():
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    daily_trends_df = data_analysis_service.get_daily_movement_summary() # data_analysis_service에서 가져옴
    return daily_trends_df.to_dict(orient='records') # DataFrame을 리스트 오브 딕트로 변환

@app.get("/api/product/category-distribution")
async def get_product_category_distribution():
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    product_df = data_service.product_master

    # '카테고리' 컬럼을 가정하여 집계
    if '카테고리' in product_df.columns:
        category_counts = product_df['카테고리'].value_counts().reset_index()
        category_counts.columns = ['name', 'value'] # 파이차트 데이터 키에 맞춤
        return category_counts.to_dict(orient='records')
    else:
        # '카테고리' 컬럼이 없을 경우, 제품명에서 카테고리 추출 또는 상위 10개 제품
        if '제품명' in product_df.columns and 'ProductName' in product_df.columns:
            # 제품명에서 간단한 카테고리 분류 시도
            try:
                # 현재고 기준으로 상위 10개 제품만 표시
                if '현재고' in product_df.columns:
                    top_products = product_df.nlargest(10, '현재고')
                    category_data = []
                    for _, row in top_products.iterrows():
                        category_data.append({
                            'name': str(row.get('ProductName', row.get('제품명', '알 수 없음')))[:20] + ('...' if len(str(row.get('ProductName', row.get('제품명', '')))) > 20 else ''),
                            'value': int(row.get('현재고', 0))
                        })
                    return category_data
                else:
                    # 현재고 컬럼이 없으면 제품별로 1개씩 할당하여 상위 8개
                    product_counts = product_df['ProductName'].value_counts().head(8).reset_index()
                    product_counts.columns = ['name', 'value']
                    return product_counts.to_dict(orient='records')
            except Exception as e:
                logger.error(f"카테고리 데이터 생성 오류: {e}")
                # 기본 더미 데이터 반환
                return [
                    {'name': '전자제품', 'value': 45},
                    {'name': '가전제품', 'value': 32},
                    {'name': '의류', 'value': 28},
                    {'name': '식품', 'value': 22},
                    {'name': '도서', 'value': 18},
                    {'name': '기타', 'value': 15}
                ]
        else:
            # 기본 더미 데이터 반환
            return [
                {'name': '전자제품', 'value': 45},
                {'name': '가전제품', 'value': 32},
                {'name': '의류', 'value': 28},
                {'name': '식품', 'value': 22},
                {'name': '도서', 'value': 18},
                {'name': '기타', 'value': 15}
            ]

@app.get("/api/analysis/stats/{df_name}")
async def get_analysis_stats(df_name: str):
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    stats = data_analysis_service.get_descriptive_stats(df_name)
    return stats

@app.get("/api/analysis/daily-movement")
async def get_analysis_daily_movement():
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    # data_analysis_service.get_daily_movement_summary()는 이제 DataFrame을 반환
    summary_df = data_analysis_service.get_daily_movement_summary()
    return summary_df.to_dict(orient='records') # 리스트 오브 딕트로 변환

@app.get("/api/analysis/product-insights")
async def get_analysis_product_insights():
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    insights = data_analysis_service.get_product_insights()
    return insights

@app.get("/api/analysis/rack-utilization")
async def get_analysis_rack_utilization():
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    summary = data_analysis_service.get_rack_utilization_summary()
    return summary

@app.get("/api/analysis/anomalies")
async def get_anomalies():
    # 이상 탐지 로직은 data_analysis_service로 이동
    anomalies_result = await data_analysis_service.detect_anomalies_data()
    if not anomalies_result["anomalies"] and anomalies_result.get("message") and "오류" in anomalies_result["message"]:
        raise HTTPException(status_code=500, detail=anomalies_result["message"])
    return anomalies_result

class DemandPredictionRequest(BaseModel):
    features: Dict[str, Any] # 예측에 필요한 피처를 클라이언트에서 전달한다고 가정

@app.post("/api/predict/demand")
async def predict_demand(request: DemandPredictionRequest):
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    if not model_trained["demand_predictor"]:
        await train_demand_predictor()
        if not model_trained["demand_predictor"]:
            raise HTTPException(status_code=500, detail="수요 예측 모델 학습에 실패했습니다.")
    
    try:
        # 클라이언트에서 받은 피처를 DataFrame으로 변환
        input_features = pd.DataFrame([request.features])
        prediction = demand_predictor.predict_daily_demand(input_features)
        # 예측 결과는 numpy 배열이므로 리스트로 변환하여 반환
        return {"prediction": prediction.tolist()}
    except Exception as e:
        logger.error(f"수요 예측 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"수요 예측 처리 중 오류 발생: {e}")

@app.post("/api/upload/data")
async def upload_data(file: UploadFile = File(...)):
    try:
        # 파일 확장자 확인
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in [".csv", ".xlsx", ".xls"]:
            raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다. CSV 또는 Excel 파일을 업로드해주세요.")

        contents = await file.read()
        data_io = io.BytesIO(contents)

        if file_extension == ".csv":
            df = pd.read_csv(data_io)
        else: # .xlsx or .xls
            df = pd.read_excel(data_io)
        
        # TODO: 업로드된 데이터 처리 및 저장 로직 구현
        # 예: data_service에 데이터 추가 또는 특정 위치에 저장
        # 여기서는 단순히 로드하고 성공 메시지를 반환합니다.
        logger.info(f"Uploaded file: {file.filename}, rows: {len(df)}")

        # 데이터 업로드 후 data_service에 반영하고 모델 재학습 (선택 사항)
        # 이 부분은 데이터의 성격과 활용 방식에 따라 복잡도가 달라질 수 있습니다.
        # 예를 들어, 입출고 데이터면 기존 데이터에 concat, 상품 데이터면 replace 등
        # 여기서는 간단히 새로 로드하는 것으로 가정 (실제 서비스에서는 데이터 병합 등 필요)
        await data_service.load_all_data(rawdata_path="../rawdata") # 다시 모든 데이터 로드 (임시)
        model_trained["demand_predictor"] = False # 모델 재학습 필요
        model_trained["product_clusterer"] = False # 모델 재학습 필요
        model_trained["anomaly_detector"] = False # 모델 재학습 필요

        return {"message": f"파일 \'{file.filename}\'이 성공적으로 업로드되었습니다. 총 {len(df)}개의 행이 처리되었습니다.", "rows_processed": len(df)}

    except Exception as e:
        logger.error(f"파일 업로드 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"파일 업로드 중 오류 발생: {e}")

class ChatRequest(BaseModel):
    question: str

@app.post("/api/ai/chat")
async def ai_chat(request: ChatRequest):
    logger.info(f"AI Chat 요청 수신: {request.question}")
    try:
        response_text = await chatbot.process_query(request.question)
        logger.info(f"AI Chat 응답 생성 완료.")
        return {"answer": response_text}
    except Exception as e:
        logger.error(f"AI Chat 처리 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"AI Chat 처리 중 오류 발생: {e}")

@app.post("/api/product/cluster")
async def cluster_products_api():
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    if not model_trained["product_clusterer"]:
        await train_product_clusterer()
        if not model_trained["product_clusterer"]:
            raise HTTPException(status_code=500, detail="제품 클러스터링 모델 학습에 실패했습니다.")

    try:
        # TODO: 실제 제품 클러스터링에 필요한 피처를 product_master에서 추출
        # 현재는 train_product_clusterer에서 사용된 임시 데이터와 동일한 구조를 가정
        dummy_features = {
            'feature_a': [1.0, 2.0, 1.5, 3.0, 2.5, 1.2, 2.8],
            'feature_b': [100, 200, 150, 300, 250, 120, 280]
        }
        features_df = pd.DataFrame(dummy_features)

        clusters = product_clusterer.cluster_products(features_df)
        return {"clusters": clusters.tolist()}
    except Exception as e:
        logger.error(f"제품 클러스터링 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"제품 클러스터링 처리 중 오류 발생: {e}")

# 차트 생성 요청 모델
class ChartGenerationRequest(BaseModel):
    user_request: str  # 사용자의 자연어 차트 요청
    context: str = ""  # 추가 컨텍스트 (선택사항)

@app.post("/api/ai/generate-chart")
async def generate_chart(request: ChartGenerationRequest):
    """LLM을 활용한 차트 설정 생성 API"""
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    logger.info(f"차트 생성 요청: {request.user_request}")
    
    try:
        # 벡터 데이터베이스에서 관련 데이터 검색
        vector_search_result = await vector_db_service.search_relevant_data(
            query=request.user_request,
            n_results=20
        )
        
        # 검색된 실제 데이터가 있으면 사용, 없으면 기본 메타데이터 사용
        if vector_search_result.get("success") and vector_search_result.get("chart_data"):
            # 실제 데이터로 차트 설정 생성
            chart_result = await _generate_chart_from_real_data(
                user_request=request.user_request,
                search_result=vector_search_result
            )
        else:
            # 기존 방식: 메타데이터로 AI 생성
            available_data = await _prepare_available_data_info()
            chart_result = await ai_service.generate_chart_config(
                user_request=request.user_request,
                available_data=available_data
            )
        
        if chart_result["success"]:
            logger.info(f"차트 설정 생성 성공: {chart_result['chart_config']['chart_type']}")
            return {
                "success": True,
                "chart_config": chart_result["chart_config"],
                "message": chart_result["message"]
            }
        else:
            logger.warning(f"차트 설정 생성 실패, 대체 설정 사용: {chart_result['error']}")
            return {
                "success": False,
                "chart_config": chart_result["fallback_config"],
                "message": chart_result["message"],
                "error": chart_result["error"]
            }
            
    except Exception as e:
        logger.error(f"차트 생성 API 처리 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"차트 생성 처리 중 오류 발생: {e}")

async def _prepare_available_data_info() -> dict:
    """사용 가능한 데이터 정보를 정리하여 반환합니다."""
    try:
        available_data = {}
        
        # 입고 데이터 정보
        if data_service.inbound_data is not None and not data_service.inbound_data.empty:
            available_data["inbound_data"] = {
                "description": "입고 데이터 (공급업체별 상품 입고 정보)",
                "columns": list(data_service.inbound_data.columns),
                "row_count": len(data_service.inbound_data),
                "date_range": _get_date_range(data_service.inbound_data, 'Date')
            }
        
        # 출고 데이터 정보
        if data_service.outbound_data is not None and not data_service.outbound_data.empty:
            available_data["outbound_data"] = {
                "description": "출고 데이터 (고객사별 상품 출고 정보)",
                "columns": list(data_service.outbound_data.columns),
                "row_count": len(data_service.outbound_data),
                "date_range": _get_date_range(data_service.outbound_data, 'Date')
            }
        
        # 상품 마스터 데이터 정보
        if data_service.product_master is not None and not data_service.product_master.empty:
            available_data["product_master"] = {
                "description": "상품 마스터 데이터 (상품별 기본 정보 및 재고)",
                "columns": list(data_service.product_master.columns),
                "row_count": len(data_service.product_master)
            }
        
        # 기본 KPI 정보 추가
        available_data["kpi_metrics"] = {
            "description": "계산 가능한 KPI 지표들",
            "metrics": [
                "일별 입고량/출고량",
                "랙별 재고 현황",
                "상품별 회전율",
                "공급업체별 입고 현황",
                "고객사별 출고 현황",
                "재고 수준 분석"
            ]
        }
        
        return available_data
        
    except Exception as e:
        logger.error(f"데이터 정보 수집 중 오류: {e}")
        return {"error": f"데이터 정보 수집 실패: {str(e)}"}

def _get_date_range(df, date_column):
    """데이터프레임에서 날짜 범위를 반환합니다."""
    try:
        if date_column in df.columns:
            dates = pd.to_datetime(df[date_column], errors='coerce')
            min_date = dates.min()
            max_date = dates.max()
            if pd.notna(min_date) and pd.notna(max_date):
                return f"{min_date.strftime('%Y-%m-%d')} ~ {max_date.strftime('%Y-%m-%d')}"
        return "날짜 정보 없음"
    except Exception:
        return "날짜 정보 파싱 실패"

async def _generate_chart_from_real_data(user_request: str, search_result: Dict[str, Any]) -> Dict[str, Any]:
    """벡터 데이터베이스 검색 결과로 실제 차트 설정 생성"""
    try:
        chart_data = search_result.get("chart_data", {})
        
        if not chart_data.get("labels") or not chart_data.get("data"):
            raise ValueError("검색된 데이터에 차트 생성에 필요한 정보가 없습니다.")
        
        # 사용자 요청에서 차트 타입 추정
        chart_type = _infer_chart_type_from_request(user_request)
        
        # 색상 팔레트
        colors = [
            "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
            "#06b6d4", "#84cc16", "#f97316", "#ec4899", "#6b7280"
        ]
        
        # Chart.js 호환 설정 생성
        chart_config = {
            "chart_type": chart_type,
            "title": chart_data.get("title", "데이터 차트"),
            "data": {
                "labels": chart_data["labels"][:10],  # 최대 10개까지만 표시
                "datasets": [{
                    "label": chart_data.get("title", "데이터"),
                    "data": chart_data["data"][:10],
                    "backgroundColor": colors[:len(chart_data["data"][:10])],
                    "borderColor": colors[0],
                    "borderWidth": 2 if chart_type == "line" else 1,
                    "tension": 0.3 if chart_type == "line" else 0
                }]
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": chart_data.get("title", "데이터 차트"),
                        "font": {"size": 16, "weight": "bold"}
                    },
                    "legend": {
                        "display": True,
                        "position": "top"
                    }
                },
                "scales": {} if chart_type in ["pie", "doughnut"] else {
                    "y": {
                        "beginAtZero": True,
                        "title": {
                            "display": True,
                            "text": "수량"
                        }
                    },
                    "x": {
                        "title": {
                            "display": True,
                            "text": "항목"
                        }
                    }
                }
            },
            "query_info": {
                "data_source": f"실제 데이터 검색 ({search_result.get('found_documents', 0)}개 문서)",
                "search_query": user_request,
                "data_type": chart_data.get("type", "unknown")
            }
        }
        
        logger.info(f"✅ 실제 데이터로 차트 설정 생성: {chart_type} - {chart_data.get('title')}")
        
        return {
            "success": True,
            "chart_config": chart_config,
            "message": f"실제 데이터 {search_result.get('found_documents', 0)}개 문서를 기반으로 차트를 생성했습니다.",
            "data_source": "vector_database"
        }
        
    except Exception as e:
        logger.error(f"❌ 실제 데이터 차트 생성 실패: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "실제 데이터로 차트 생성에 실패했습니다. AI 생성으로 대체합니다.",
            "fallback_config": None
        }

def _infer_chart_type_from_request(user_request: str) -> str:
    """사용자 요청에서 차트 타입 추정"""
    request_lower = user_request.lower()
    
    if any(word in request_lower for word in ['파이차트', 'pie', '원그래프', '도넛']):
        return "doughnut" if '도넛' in request_lower else "pie"
    elif any(word in request_lower for word in ['선그래프', 'line', '추이', '트렌드', '변화']):
        return "line"
    elif any(word in request_lower for word in ['막대차트', 'bar', '막대그래프', '비교']):
        return "bar"
    elif any(word in request_lower for word in ['산점도', 'scatter', '분포']):
        return "scatter"
    else:
        # 기본값: 막대차트
        return "bar"

@app.get("/api/vector-db/status")
async def get_vector_db_status():
    """벡터 데이터베이스 상태 확인"""
    try:
        status = vector_db_service.get_status()
        return status
    except Exception as e:
        logger.error(f"벡터 DB 상태 확인 중 오류: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "벡터 데이터베이스 상태를 확인할 수 없습니다."
        }

@app.post("/api/vector-db/reindex")
async def reindex_vector_db():
    """벡터 데이터베이스 재인덱싱"""
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    try:
        logger.info("🔄 벡터 데이터베이스 재인덱싱 시작...")
        success = await vector_db_service.index_warehouse_data(force_rebuild=True)
        
        if success:
            return {
                "success": True,
                "message": "벡터 데이터베이스 재인덱싱이 완료되었습니다.",
                "status": vector_db_service.get_status()
            }
        else:
            raise HTTPException(status_code=500, detail="벡터 데이터베이스 재인덱싱에 실패했습니다.")
            
    except Exception as e:
        logger.error(f"벡터 DB 재인덱싱 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"재인덱싱 중 오류 발생: {str(e)}")

@app.post("/api/cad/upload")
async def upload_cad_file(file: UploadFile = File(...)):
    """DWG/DXF CAD 파일 업로드 및 분석"""
    logger.info(f"CAD 파일 업로드 요청: {file.filename}")
    
    try:
        # 파일 검증
        if not file.filename:
            raise HTTPException(status_code=400, detail="파일명이 없습니다.")
        
        # 지원하는 파일 확장자 확인
        allowed_extensions = {'.dwg', '.dxf', '.dwf'}
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(allowed_extensions)}"
            )
        
        # 파일 크기 확인 (50MB 제한)
        max_size = 50 * 1024 * 1024  # 50MB
        file_content = await file.read()
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=400, 
                detail=f"파일 크기가 너무 큽니다. 최대 크기: 50MB, 현재 크기: {len(file_content) / (1024*1024):.1f}MB"
            )
        
        # 임시 파일 저장
        temp_dir = "cad_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        
        file_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_filename = f"{file_id}_{file.filename}"
        temp_filepath = os.path.join(temp_dir, temp_filename)
        
        with open(temp_filepath, "wb") as temp_file:
            temp_file.write(file_content)
        
        logger.info(f"임시 파일 저장 완료: {temp_filepath}")
        
        # CAD 파일 처리
        result = await cad_service.process_cad_file(temp_filepath, file.filename)
        
        # 임시 파일 정리
        try:
            os.remove(temp_filepath)
        except Exception as cleanup_error:
            logger.warning(f"임시 파일 정리 오류: {cleanup_error}")
        
        if result["success"]:
            logger.info(f"CAD 파일 처리 성공: {file.filename}")
            return {
                "success": True,
                "message": f"파일 '{file.filename}'이 성공적으로 분석되었습니다.",
                "data": result["data"],
                "processing_method": result.get("processing_method"),
                "file_info": {
                    "filename": result["filename"],
                    "size": result["file_size"],
                    "type": result["file_type"]
                }
            }
        else:
            logger.error(f"CAD 파일 처리 실패: {result['error']}")
            raise HTTPException(status_code=500, detail=result["error"])
    
    except HTTPException:
        # HTTP 예외는 그대로 재발생
        raise
    except Exception as e:
        logger.error(f"CAD 파일 업로드 처리 중 예상치 못한 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"파일 처리 중 오류가 발생했습니다: {str(e)}")

@app.get("/api/cad/status")
async def get_cad_status():
    """CAD 서비스 상태 확인"""
    try:
        # 필요한 라이브러리 확인
        libraries_status = {
            "ezdxf": False,
            "pillow": False,
            "opencv": False
        }
        
        try:
            import ezdxf
            libraries_status["ezdxf"] = True
        except ImportError:
            pass
        
        try:
            from PIL import Image
            libraries_status["pillow"] = True
        except ImportError:
            pass
        
        try:
            import cv2
            libraries_status["opencv"] = True
        except ImportError:
            pass
        
        # 업로드 디렉토리 상태
        upload_dir = "cad_uploads"
        upload_dir_exists = os.path.exists(upload_dir)
        upload_dir_writable = os.access(upload_dir, os.W_OK) if upload_dir_exists else False
        
        return {
            "service_available": True,
            "libraries": libraries_status,
            "upload_directory": {
                "exists": upload_dir_exists,
                "writable": upload_dir_writable,
                "path": upload_dir
            },
            "supported_formats": [".dwg", ".dxf", ".dwf"],
            "max_file_size_mb": 50,
            "ai_service_available": ai_service is not None
        }
        
    except Exception as e:
        logger.error(f"CAD 상태 확인 오류: {str(e)}")
        return {
            "service_available": False,
            "error": str(e)
        }

@app.get("/api/warehouse/racks/{rack_id}/stock")
async def get_rack_stock(rack_id: str):
    """특정 랙의 재고 정보 조회"""
    try:
        # 실제 구현에서는 데이터베이스에서 조회
        # 현재는 모의 데이터 반환
        import random
        
        mock_data = {
            "rack_id": rack_id,
            "currentStock": random.randint(10, 150),
            "capacity": random.randint(100, 200),
            "last_updated": "2025-01-20T10:30:00Z",
            "status": "active"
        }
        
        logger.info(f"랙 {rack_id} 재고 정보 조회")
        return mock_data
        
    except Exception as e:
        logger.error(f"랙 재고 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"재고 조회 실패: {str(e)}")

@app.get("/api/warehouse/data/current")
async def get_current_warehouse_data():
    """현재 창고 전체 데이터 조회"""
    try:
        # 실제 구현에서는 data_service와 vector_db_service에서 데이터 조회
        current_data = data_service.get_current_summary()
        
        # 재고 데이터 포함
        warehouse_data = {
            "timestamp": "2025-01-20T10:30:00Z",
            "total_racks": 5,
            "inventory": [
                {"location": "A", "product_name": "제품A", "quantity": 75},
                {"location": "B", "product_name": "제품B", "quantity": 90},
                {"location": "C", "product_name": "제품C", "quantity": 60},
                {"location": "D", "product_name": "제품D", "quantity": 120},
                {"location": "E", "product_name": "제품E", "quantity": 85},
            ],
            "summary": current_data
        }
        
        logger.info("현재 창고 데이터 조회 완료")
        return warehouse_data
        
    except Exception as e:
        logger.error(f"창고 데이터 조회 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"데이터 조회 실패: {str(e)}")

@app.get("/api/health")
async def health_check():
    """Docker 헬스체크용 엔드포인트"""
    try:
        # 기본 서비스 상태 확인
        current_time = datetime.now().isoformat()
        
        # 데이터 서비스 상태
        data_status = "healthy" if data_service else "unhealthy"
        
        # AI 서비스 상태
        ai_status = "healthy" if ai_service else "unhealthy"
        
        # ChromaDB 상태 (간단한 체크)
        try:
            vector_db_status = "healthy" if vector_db_service else "unhealthy"
        except Exception:
            vector_db_status = "degraded"
        
        health_data = {
            "status": "healthy",
            "timestamp": current_time,
            "version": "1.0.0",
            "services": {
                "data_service": data_status,
                "ai_service": ai_status,
                "vector_db": vector_db_status,
                "cad_service": "healthy" if cad_service else "unhealthy"
            },
            "uptime": "running"
        }
        
        # 모든 핵심 서비스가 정상인지 확인
        all_healthy = all(status == "healthy" for status in health_data["services"].values())
        
        if not all_healthy:
            health_data["status"] = "degraded"
            return health_data
            
        return health_data
        
    except Exception as e:
        logger.error(f"헬스체크 중 오류: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        } 