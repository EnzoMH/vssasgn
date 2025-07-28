from fastapi import FastAPI, Request, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from .utils.ai_chat import WarehouseChatbot
from .services.data_service import DataService
from .models.ml_models import DemandPredictor, ProductClusterer, AnomalyDetector # AnomalyDetector 추가
from .services.data_analysis_service import DataAnalysisService
import logging
import io
import pandas as pd
import os
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

# .env 파일 로드 (backend 디렉토리에서)
load_dotenv("../.env")

# 로거 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

# DataService, Chatbot, ML Models, DataAnalysisService 인스턴스 초기화
data_service = DataService()
chatbot = WarehouseChatbot()
demand_predictor = DemandPredictor()
product_clusterer = ProductClusterer()
anomaly_detector = AnomalyDetector() # AnomalyDetector 인스턴스 추가
data_analysis_service = DataAnalysisService(data_service, anomaly_detector) # anomaly_detector 전달

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
    total_inventory = product_df['현재고'].sum() if '현재고' in product_df.columns else 0
    daily_throughput = len(inbound_df) + len(outbound_df) # 간단하게 총 입출고 건수
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
        # '카테고리' 컬럼이 없을 경우, 임시로 '제품명'을 활용하거나 빈 리스트 반환
        if '제품명' in product_df.columns:
            product_df['name'] = product_df['제품명']
            product_df['value'] = 1 # 각 제품을 1로 가정하여 카테고리처럼 사용
            return product_df[['name', 'value']].to_dict(orient='records')
        else:
            return []

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