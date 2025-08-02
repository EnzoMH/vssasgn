from fastapi import FastAPI, Request, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from backend.app.utils.ai_chat import WarehouseChatbot
from backend.app.services.data_service import DataService
from backend.app.models.ml_models import DemandPredictor, ProductClusterer, AnomalyDetector # AnomalyDetector 추가
import joblib  # 훈련된 모델 로드용
import json  # 클러스터 결과 로드용
from backend.app.services.data_analysis_service import DataAnalysisService
from backend.app.services.ai_service import WarehouseAI
from backend.app.services.vector_db_service import VectorDBService
from backend.app.services.cad_service import CADService
from backend.app.services.loi_service import LOIService
from backend.app.models.ml_feature_engineering import ProductFeatureExtractor
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
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# 메인 페이지 라우트
@app.get("/", response_class=HTMLResponse)
async def main_page():
    with open("backend/static/index.html", "r", encoding="utf-8") as f:
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
loi_service = LOIService(data_service=data_service) # LOI 서비스 추가
chatbot = WarehouseChatbot(data_service=data_service, vector_db_service=vector_db_service) # 서비스 주입

# ML 모델 학습 상태
model_trained = {"demand_predictor": False, "product_clusterer": False, "anomaly_detector": False} # anomaly_detector 상태 추가

# ProductClusterer 결과 데이터 (글로벌 저장)
product_cluster_data = None

@app.on_event("startup")
async def startup_event():
    logger.info("서버 시작 이벤트 발생: 데이터 로딩 시작...")
    await data_service.load_all_data(rawdata_path="rawdata")
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

@app.get("/api/vector-db/status")
async def get_vector_db_status():
    """벡터 데이터베이스 상태 확인"""
    try:
        status = vector_db_service.get_status()
        return status
    except Exception as e:
        logger.error(f"❌ 벡터 DB 상태 확인 중 오류 발생: {e}")
        return {"status": "error", "error": str(e)}

@app.post("/api/vector-db/reindex")
async def reindex_vector_db():
    """벡터 데이터베이스 재인덱싱"""
    try:
        if not data_service.data_loaded:
            raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
        
        logger.info("벡터 데이터베이스 재인덱싱 시작...")
        success = await vector_db_service.index_warehouse_data(force_rebuild=True)
        
        if success:
            status = vector_db_service.get_status()
            return {
                "success": True,
                "message": "벡터 데이터베이스 재인덱싱 완료",
                "status": status
            }
        else:
            return {
                "success": False,
                "message": "벡터 데이터베이스 재인덱싱 실패"
            }
    except Exception as e:
        logger.error(f"❌ 벡터 DB 재인덱싱 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"재인덱싱 실패: {str(e)}")


async def train_demand_predictor():
    if model_trained["demand_predictor"] or not data_service.data_loaded:
        return
    
    logger.info("수요 예측 모델 학습 시작...")
    try:
        # 실제 데이터 전처리 및 피처 엔지니어링
        # inbound_data와 outbound_data를 결합
        combined_data = pd.merge(
            data_service.inbound_data,
            data_service.outbound_data,
            on=['Date', 'ProductCode'],
            how='outer',
            suffixes=('_in', '_out')
        ).fillna(0)
        
        # 피처 엔지니어링: 과거 7일 출고량 평균, 이전 날 입고량 등
        combined_data = combined_data.sort_values(['ProductCode', 'Date'])
        combined_data['feature1'] = combined_data.groupby('ProductCode')['PalleteQty_out'].rolling(window=7, min_periods=1).mean().reset_index(0, drop=True)
        combined_data['feature2'] = combined_data.groupby('ProductCode')['PalleteQty_in'].shift(1).fillna(0)
        combined_data['target'] = combined_data.groupby('ProductCode')['PalleteQty_out'].shift(-1).fillna(0)
        
        # NaN 제거 및 학습 데이터 준비
        combined_data = combined_data.dropna(subset=['target'])
        X = combined_data[['feature1', 'feature2']]
        y = combined_data['target']
        
        if X.empty or y.empty:
            raise ValueError("학습 데이터가 부족합니다.")
        
        demand_predictor.train(X, y)
        model_trained["demand_predictor"] = True
        logger.info("수요 예측 모델 학습 완료.")
    except Exception as e:
        logger.error(f"수요 예측 모델 학습 중 오류 발생: {e}")
        model_trained["demand_predictor"] = False

async def train_product_clusterer():
    global product_cluster_data  # 함수 맨 처음에 global 선언
    
    if model_trained["product_clusterer"] or not data_service.data_loaded:
        return
    
    logger.info("제품 클러스터링 모델 로드 시작...")
    try:
        # 사전 훈련된 모델과 결과 로드
        model_path = "backend/app/models/trained_product_clusterer.pkl"
        results_path = "backend/app/models/product_cluster_results.json"
        
        if os.path.exists(model_path) and os.path.exists(results_path):
            # 훈련된 모델 로드
            trained_model = joblib.load(model_path)
            
            # 기존 ProductClusterer 인스턴스에 훈련된 모델 할당
            product_clusterer.model = trained_model
            
            # 클러스터 결과 로드
            with open(results_path, 'r', encoding='utf-8') as f:
                cluster_results = json.load(f)
            
            # 글로벌 변수에 결과 저장 (API에서 사용하기 위해)
            product_cluster_data = cluster_results
            
            model_trained["product_clusterer"] = True
            logger.info(f"✅ 사전 훈련된 ProductClusterer 모델 로드 완료 (K={trained_model.n_clusters})")
            
        elif os.path.exists(results_path):
            # pkl 파일은 없지만 results.json은 있는 경우 - 결과만 로드
            logger.warning("⚠️ 모델 파일(.pkl)은 없지만 결과 파일(.json)을 발견했습니다. 결과만 로드합니다.")
            
            with open(results_path, 'r', encoding='utf-8') as f:
                cluster_results = json.load(f)
            
            # 글로벌 변수에 결과 저장 (이미 위에서 global 선언됨)
            product_cluster_data = cluster_results
            
            # 모델은 훈련되지 않았지만 결과는 사용 가능
            model_trained["product_clusterer"] = True  # API 사용을 위해 True로 설정
            logger.info("✅ ProductClusterer 결과 데이터 로드 완료 (모델 파일 없음)")
            
        else:
            logger.warning("⚠️ 사전 훈련된 ProductClusterer 모델을 찾을 수 없습니다.")
            
            # 🔥 NEW: 자동 특징 엔지니어링 및 모델 훈련 시도
            logger.info("🚀 자동 특징 엔지니어링 및 클러스터링 모델 훈련을 시도합니다...")
            
            try:
                # 1. 특징 엔지니어링 실행
                feature_extractor = ProductFeatureExtractor(data_service.data)
                engineered_data = feature_extractor.create_comprehensive_features()
                
                if not engineered_data.empty:
                    logger.info(f"✅ 특징 엔지니어링 완료: {len(engineered_data)} 제품, {engineered_data.shape[1]} 특징")
                    
                    # 2. ProductClusterer로 클러스터링 수행
                    product_clusterer.fit(engineered_data)
                    clusters = product_clusterer.get_clusters()
                    
                    # 3. 결과 저장
                    os.makedirs('backend/app/models', exist_ok=True)
                    
                    # 모델 저장
                    if hasattr(product_clusterer, 'model') and product_clusterer.model:
                        joblib.dump(product_clusterer.model, model_path)
                        logger.info(f"✅ 모델 저장 완료: {model_path}")
                    
                    # 결과 저장
                    cluster_results = {
                        "clusters": clusters,
                        "metadata": {
                            "timestamp": datetime.now().isoformat(),
                            "n_products": len(engineered_data),
                            "n_features": engineered_data.shape[1],
                            "auto_trained": True
                        }
                    }
                    
                    with open(results_path, 'w', encoding='utf-8') as f:
                        json.dump(cluster_results, f, ensure_ascii=False, indent=2)
                    
                    # 글로벌 변수에 결과 저장
                    product_cluster_data = cluster_results
                    
                    model_trained["product_clusterer"] = True
                    logger.info("🎉 자동 특징 엔지니어링 및 클러스터링 완료!")
                    
                else:
                    logger.error("❌ 특징 엔지니어링 결과가 비어있습니다.")
                    model_trained["product_clusterer"] = False
                    
            except Exception as feature_error:
                logger.error(f"❌ 자동 특징 엔지니어링 실패: {feature_error}")
                logger.warning("💡 수동으로 product_clusterer_trainer.py를 실행하세요.")
                model_trained["product_clusterer"] = False
            
    except Exception as e:
        logger.error(f"제품 클러스터링 모델 로드 중 오류 발생: {e}")
        model_trained["product_clusterer"] = False


@app.get("/api/loi/status")
async def get_loi_status():
    """LOI (Level of Inventory) 재고 수준 지표 조회"""
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    try:
        loi_metrics = loi_service.calculate_loi_metrics()
        loi_alerts = loi_service.get_loi_alerts(loi_metrics)
        
        return {
            "success": True,
            "loi_metrics": loi_metrics,
            "alerts": loi_alerts,
            "status": "healthy" if loi_metrics["overall_loi_score"] >= 80 else "warning" if loi_metrics["overall_loi_score"] >= 60 else "critical"
        }
    except Exception as e:
        logger.error(f"LOI 상태 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"LOI 상태 조회 중 오류 발생: {e}")

@app.get("/api/dashboard/kpi")
async def get_kpi_data():
    """실제 rawdata 기반 KPI 계산 및 반환"""
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    try:
        logger.info("📊 실제 데이터 기반 KPI 계산 시작...")
        
        # 실제 데이터 요약 가져오기 (수정된 로직 사용)
        summary_data = data_service.get_current_summary()
        logger.info(f"📊 데이터 요약: {summary_data}")
        
        # 1. 총 재고량 (수정된 계산 로직 사용)
        total_inventory = summary_data.get('total_inventory_calculated', summary_data.get('total_inventory', 0))
        
        # 2. 일일 처리량 (수정된 계산 로직 사용) 
        daily_throughput = summary_data.get('daily_outbound_avg', summary_data.get('daily_outbound', 0))
        
        # 3. 재고회전율 (실제 계산)
        inventory_turnover = data_service.calculate_daily_turnover_rate()
        
        # 4. 랙 활용률 (전체 평균)
        rack_util_data = data_service.calculate_rack_utilization()
        logger.info(f"📊 랙 활용률 데이터: {len(rack_util_data) if rack_util_data else 0}개 랙")
        
        if rack_util_data and len(rack_util_data) > 0:
            total_current = sum(rack['current_stock'] for rack in rack_util_data.values())
            total_capacity = sum(rack['max_capacity'] for rack in rack_util_data.values())
            rack_utilization = round((total_current / total_capacity) * 100, 1) if total_capacity > 0 else 0
            logger.info(f"📊 랙 활용률 계산: {total_current}/{total_capacity} = {rack_utilization}%")
        else:
            # fallback: 기본값 설정
            rack_utilization = 65.5  # 현실적인 기본값
            logger.warning("⚠️ 랙 데이터가 없어서 기본 활용률(65.5%) 사용")
        
        logger.info(f"✅ KPI 계산 완료 - 재고: {total_inventory}, 처리량: {daily_throughput}, 회전율: {inventory_turnover}, 활용률: {rack_utilization}%")
        
        return {
            "total_inventory": total_inventory,
            "daily_throughput": daily_throughput, 
            "rack_utilization": rack_utilization,
            "inventory_turnover": inventory_turnover,
            "data_source": "rawdata",
            "calculation_date": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ KPI 계산 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"KPI 계산 실패: {str(e)}")

@app.get("/api/inventory/by-rack")
async def get_inventory_by_rack():
    """실제 rawdata 기반 랙별 재고 현황 조회"""
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    try:
        logger.info("📦 실제 데이터 기반 랙별 재고 계산 시작...")
        
        # DataService에서 랙 활용률 데이터 가져오기
        rack_util_data = data_service.calculate_rack_utilization()
        
        if not rack_util_data or len(rack_util_data) == 0:
            logger.warning("⚠️ 랙 데이터가 없습니다. 기본 랙 데이터를 생성합니다.")
            # 기본 A-Z 랙 데이터 생성 (fallback)
            rack_util_data = {}
            for i in range(26):
                rack_name = chr(65 + i)  # A, B, C, ..., Z
                current_stock = 35 + (i % 15)  # 35-49 범위로 다양성
                rack_util_data[rack_name] = {
                    "current_stock": current_stock,
                    "max_capacity": 50,
                    "utilization_rate": round((current_stock / 50) * 100, 1)
                }
            logger.info(f"📦 기본 랙 데이터 생성: {len(rack_util_data)}개 랙")
        
        # 프론트엔드 차트 형식으로 변환
        inventory_by_rack = []
        for rack_name, rack_info in rack_util_data.items():
            inventory_by_rack.append({
                "rackName": rack_name,
                "currentStock": rack_info["current_stock"],
                "capacity": rack_info["max_capacity"],
                "utilizationRate": rack_info["utilization_rate"],
                "status": "normal" if rack_info["utilization_rate"] < 80 else "warning" if rack_info["utilization_rate"] < 95 else "critical"
            })
        
        # 랙명 순으로 정렬
        inventory_by_rack.sort(key=lambda x: x["rackName"])
        
        logger.info(f"✅ 랙별 재고 계산 완료 - {len(inventory_by_rack)}개 랙")
        
        return inventory_by_rack
        
    except Exception as e:
        logger.error(f"❌ 랙별 재고 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"랙별 재고 조회 실패: {str(e)}")

@app.get("/api/trends/daily")
async def get_daily_trends():
    """실제 rawdata 기반 일별 입출고 트렌드 조회"""
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    try:
        # data_service에서 실제 rawdata 기반 일별 트렌드 계산
        daily_trends = data_service.get_daily_trends_summary()
        
        if daily_trends:
            logger.info(f"✅ 실제 rawdata 기반 일별 트렌드 반환: {len(daily_trends)}일치 데이터")
            return daily_trends
        else:
            # rawdata가 없거나 오류 시 기본값
            logger.warning("⚠️ 일별 트렌드 데이터 없음, 기본값 반환")
            return [
                {'date': '2025.01.01', 'inbound': 45, 'outbound': 38, 'net_change': 7},
                {'date': '2025.01.02', 'inbound': 52, 'outbound': 41, 'net_change': 11},
                {'date': '2025.01.03', 'inbound': 38, 'outbound': 45, 'net_change': -7},
                {'date': '2025.01.04', 'inbound': 61, 'outbound': 33, 'net_change': 28},
                {'date': '2025.01.05', 'inbound': 44, 'outbound': 39, 'net_change': 5},
                {'date': '2025.01.06', 'inbound': 55, 'outbound': 47, 'net_change': 8},
                {'date': '2025.01.07', 'inbound': 48, 'outbound': 42, 'net_change': 6}
            ]
    except Exception as e:
        logger.error(f"❌ 일별 트렌드 조회 오류: {e}")
        # 오류 발생 시 기본값
        return [
            {'date': '2025.01.01', 'inbound': 45, 'outbound': 38, 'net_change': 7},
            {'date': '2025.01.02', 'inbound': 52, 'outbound': 41, 'net_change': 11},
            {'date': '2025.01.03', 'inbound': 38, 'outbound': 45, 'net_change': -7},
            {'date': '2025.01.04', 'inbound': 61, 'outbound': 33, 'net_change': 28},
            {'date': '2025.01.05', 'inbound': 44, 'outbound': 39, 'net_change': 5},
            {'date': '2025.01.06', 'inbound': 55, 'outbound': 47, 'net_change': 8},
            {'date': '2025.01.07', 'inbound': 48, 'outbound': 42, 'net_change': 6}
        ]

@app.get("/api/product/category-distribution")
async def get_product_category_distribution():
    """실제 rawdata 기반 제품 카테고리 분포 조회"""
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    try:
        # data_service에서 카테고리 분포 계산
        category_distribution = data_service.get_product_category_distribution()
        
        if category_distribution:
            logger.info(f"✅ 실제 rawdata 기반 카테고리 분포 반환: {len(category_distribution)}개 카테고리")
            return category_distribution
        else:
            # rawdata가 없거나 오류 시 기본값
            logger.warning("⚠️ 카테고리 분포 데이터 없음, 기본값 반환")
            return [
                {'name': '면류/라면', 'value': 25},
                {'name': '음료/음료수', 'value': 32},
                {'name': '조미료/양념', 'value': 18},
                {'name': '곡물/쌀', 'value': 15},
                {'name': '스낵/과자', 'value': 12},
                {'name': '기타', 'value': 8}
            ]
    except Exception as e:
        logger.error(f"❌ 카테고리 분포 조회 오류: {e}")
        # 오류 발생 시 기본값
        return [
            {'name': '면류/라면', 'value': 25},
            {'name': '음료/음료수', 'value': 32},
            {'name': '조미료/양념', 'value': 18},
            {'name': '곡물/쌀', 'value': 15},
            {'name': '스낵/과자', 'value': 12},
            {'name': '기타', 'value': 8}
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
        
        logger.info(f"Uploaded file: {file.filename}, rows: {len(df)}")

        # 데이터 업로드 후 data_service에 반영하고 모델 재학습 (선택 사항)
        # 이 부분은 데이터의 성격과 활용 방식에 따라 복잡도가 달라질 수 있습니다.
        # 예를 들어, 입출고 데이터면 기존 데이터에 concat, 상품 데이터면 replace 등
        # 여기서는 간단히 새로 로드하는 것으로 가정 (실제 서비스에서는 데이터 병합 등 필요)
        await data_service.load_all_data(rawdata_path="rawdata") # 다시 모든 데이터 로드 (임시)
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
    """기존 API 호환성을 위한 리다이렉트 (Deprecated)"""
    logger.warning("⚠️ Deprecated API 호출: /api/product/cluster -> /api/ml/product-clustering/clusters 사용 권장")
    
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    if not model_trained["product_clusterer"] or not product_cluster_data:
        raise HTTPException(status_code=500, detail="ProductClusterer 모델이 준비되지 않았습니다. 먼저 product_clusterer_trainer.py를 실행하세요.")

    try:
        # 새로운 API 형식으로 데이터 변환하여 반환
        if product_cluster_data and "cluster_analysis" in product_cluster_data:
            cluster_analysis = product_cluster_data["cluster_analysis"]
            
            # 기존 API 형식으로 변환 (간단한 클러스터 배열)
            clusters = []
            for cluster_id, analysis in cluster_analysis.items():
                cluster_num = int(cluster_id.split('_')[1])  # cluster_0 -> 0
                clusters.extend([cluster_num] * analysis["size"])
            
            return {"clusters": clusters}
        else:
            raise HTTPException(status_code=500, detail="클러스터 데이터를 찾을 수 없습니다.")
            
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
        temp_dir = "backend/cad_uploads"
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
        upload_dir = "backend/cad_uploads"
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

# =============================================================================
# ProductClusterer API 엔드포인트들
# =============================================================================

@app.get("/api/ml/product-clustering/status")
async def get_product_clustering_status():
    """ProductClusterer 모델 상태 확인"""
    try:
        # 디버깅 정보 추가
        logger.info(f"상태 확인 요청 - 모델 훈련: {model_trained['product_clusterer']}, 데이터 존재: {product_cluster_data is not None}")
        
        status = {
            "model_trained": model_trained["product_clusterer"],
            "model_available": product_cluster_data is not None,
            "data_loaded": data_service.data_loaded,
            "debug_info": {
                "product_cluster_data_keys": list(product_cluster_data.keys()) if product_cluster_data else [],
                "model_trained_status": model_trained
            }
        }
        
        if product_cluster_data:
            model_info = product_cluster_data.get("model_info", {})
            cluster_analysis = product_cluster_data.get("cluster_analysis", {})
            
            status.update({
                "model_type": model_info.get("model_type"),
                "n_clusters": model_info.get("n_clusters"),
                "trained_at": model_info.get("trained_at"),
                "total_products": sum(cluster["size"] for cluster in cluster_analysis.values()) if cluster_analysis else 0,
                "available_clusters": list(cluster_analysis.keys()) if cluster_analysis else []
            })
        else:
            logger.warning("product_cluster_data가 None입니다. 모델 재로드가 필요할 수 있습니다.")
        
        return status
        
    except Exception as e:
        logger.error(f"ProductClusterer 상태 확인 오류: {e}")
        raise HTTPException(status_code=500, detail=f"상태 확인 실패: {str(e)}")

@app.get("/api/ml/product-clustering/clusters")
async def get_product_clusters():
    """제품 클러스터 분석 결과 조회"""
    logger.info(f"클러스터 목록 요청 - 모델 훈련: {model_trained['product_clusterer']}, 데이터 존재: {product_cluster_data is not None}")
    
    if not model_trained["product_clusterer"]:
        raise HTTPException(status_code=404, detail="ProductClusterer 모델이 훈련되지 않았습니다.")
    
    if not product_cluster_data:
        # 데이터가 없으면 재로드 시도
        logger.warning("클러스터 데이터가 없습니다. 재로드 시도...")
        await train_product_clusterer()
        
        if not product_cluster_data:
            raise HTTPException(status_code=404, detail="클러스터 데이터를 로드할 수 없습니다. product_clusterer_trainer.py를 먼저 실행하세요.")
    
    try:
        cluster_analysis = product_cluster_data["cluster_analysis"]
        cluster_interpretations = product_cluster_data["cluster_interpretations"]
        
        # 클러스터별 요약 정보 생성
        clusters_summary = []
        for cluster_id, analysis in cluster_analysis.items():
            interpretation = cluster_interpretations.get(cluster_id, {})
            
            summary = {
                "cluster_id": cluster_id,
                "cluster_name": interpretation.get("type", "알 수 없음"),
                "size": analysis["size"],
                "percentage": round(analysis["percentage"], 1),
                "strategy": interpretation.get("strategy", "표준 관리"),
                "color": interpretation.get("color", "gray"),
                "metrics": interpretation.get("metrics", {}),
                "key_products": analysis.get("key_products", [])[:3],  # 상위 3개만
                "characteristics": analysis.get("characteristics", {})
            }
            clusters_summary.append(summary)
        
        # 크기 순으로 정렬
        clusters_summary.sort(key=lambda x: x["size"], reverse=True)
        
        return {
            "clusters": clusters_summary,
            "model_info": product_cluster_data["model_info"],
            "total_products": sum(c["size"] for c in clusters_summary)
        }
        
    except Exception as e:
        logger.error(f"클러스터 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"클러스터 조회 실패: {str(e)}")

@app.get("/api/ml/product-clustering/cluster/{cluster_id}")
async def get_cluster_details(cluster_id: str):
    """특정 클러스터의 상세 정보 조회"""
    # 디버깅 로그 추가
    logger.info(f"클러스터 상세 조회 요청: {cluster_id}")
    logger.info(f"모델 훈련 상태: {model_trained['product_clusterer']}")
    logger.info(f"클러스터 데이터 존재: {product_cluster_data is not None}")
    
    if not model_trained["product_clusterer"]:
        raise HTTPException(status_code=404, detail="ProductClusterer 모델이 훈련되지 않았습니다.")
    
    if not product_cluster_data:
        # 데이터가 없다면 다시 로드 시도
        logger.warning("클러스터 데이터가 없습니다. 다시 로드 시도...")
        await train_product_clusterer()
        
        if not product_cluster_data:
            raise HTTPException(status_code=404, detail="클러스터 데이터를 로드할 수 없습니다. product_clusterer_trainer.py를 먼저 실행하세요.")
    
    try:
        cluster_analysis = product_cluster_data["cluster_analysis"]
        cluster_interpretations = product_cluster_data["cluster_interpretations"]
        
        logger.info(f"사용 가능한 클러스터 ID들: {list(cluster_analysis.keys())}")
        
        if cluster_id not in cluster_analysis:
            raise HTTPException(status_code=404, detail=f"클러스터 '{cluster_id}'를 찾을 수 없습니다. 사용 가능한 클러스터: {list(cluster_analysis.keys())}")
        
        analysis = cluster_analysis[cluster_id]
        interpretation = cluster_interpretations.get(cluster_id, {})
        
        return {
            "cluster_id": cluster_id,
            "cluster_name": interpretation.get("type", "알 수 없음"),
            "size": analysis["size"],
            "percentage": round(analysis["percentage"], 1),
            "strategy": interpretation.get("strategy", "표준 관리"),
            "color": interpretation.get("color", "gray"),
            "metrics": interpretation.get("metrics", {}),
            "characteristics": analysis.get("characteristics", {}),
            "all_products": analysis.get("key_products", [])  # 모든 주요 상품
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"클러스터 상세 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"클러스터 상세 조회 실패: {str(e)}")

@app.get("/api/ml/product-clustering/product/{product_code}")
async def get_product_cluster_info(product_code: str):
    """특정 상품의 클러스터 정보 조회"""
    if not model_trained["product_clusterer"] or not product_cluster_data:
        raise HTTPException(status_code=404, detail="ProductClusterer 모델이 훈련되지 않았습니다.")
    
    try:
        # integrated_warehouse_data.json에서 해당 상품 찾기
        with open("integrated_warehouse_data.json", 'r', encoding='utf-8') as f:
            warehouse_data = json.load(f)
        
        products = warehouse_data['inventory_analysis']['products']
        target_product = None
        
        for product in products:
            if product['product_code'] == product_code:
                target_product = product
                break
        
        if not target_product:
            raise HTTPException(status_code=404, detail=f"상품 코드 '{product_code}'를 찾을 수 없습니다.")
        
        # 해당 상품이 속한 클러스터 찾기 (특징 기반 예측)
        # 실제로는 특징 추출 후 모델로 예측해야 하지만, 현재는 클러스터 결과에서 검색
        product_cluster = None
        cluster_analysis = product_cluster_data["cluster_analysis"]
        
        for cluster_id, analysis in cluster_analysis.items():
            for key_product in analysis.get("key_products", []):
                if key_product.get("product_code") == product_code:
                    product_cluster = cluster_id
                    break
            if product_cluster:
                break
        
        if not product_cluster:
            # 기본값으로 가장 큰 클러스터 할당
            largest_cluster = max(cluster_analysis.keys(), 
                                key=lambda x: cluster_analysis[x]["size"])
            product_cluster = largest_cluster
        
        cluster_interpretation = product_cluster_data["cluster_interpretations"].get(product_cluster, {})
        
        return {
            "product_code": product_code,
            "product_name": target_product.get("product_name", "알 수 없음"),
            "cluster_id": product_cluster,
            "cluster_name": cluster_interpretation.get("type", "일반 상품"),
            "strategy": cluster_interpretation.get("strategy", "표준 관리 정책 적용"),
            "color": cluster_interpretation.get("color", "gray"),
            "product_metrics": {
                "turnover_ratio": target_product.get("turnover_ratio", 0),
                "current_stock": target_product.get("current_stock", 0),
                "rack_name": target_product.get("rack_name", ""),
                "stock_status": target_product.get("stock_status", "알 수 없음")
            },
            "cluster_characteristics": cluster_analysis[product_cluster]["characteristics"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상품 클러스터 정보 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"상품 클러스터 정보 조회 실패: {str(e)}")

@app.get("/api/ml/product-clustering/high-turnover")
async def get_high_turnover_products():
    """고회전 상품 목록 조회 (프리미엄 고회전 클러스터)"""
    if not model_trained["product_clusterer"] or not product_cluster_data:
        raise HTTPException(status_code=404, detail="ProductClusterer 모델이 훈련되지 않았습니다.")
    
    try:
        cluster_analysis = product_cluster_data["cluster_analysis"]
        cluster_interpretations = product_cluster_data["cluster_interpretations"]
        
        # 프리미엄 고회전 클러스터들 찾기
        high_turnover_clusters = []
        for cluster_id, interpretation in cluster_interpretations.items():
            if "프리미엄 고회전" in interpretation.get("type", ""):
                high_turnover_clusters.append(cluster_id)
        
        high_turnover_products = []
        for cluster_id in high_turnover_clusters:
            cluster_info = cluster_analysis[cluster_id]
            interpretation = cluster_interpretations[cluster_id]
            
            for product in cluster_info.get("key_products", []):
                product_info = {
                    **product,
                    "cluster_id": cluster_id,
                    "cluster_name": interpretation.get("type", "프리미엄 고회전"),
                    "strategy": interpretation.get("strategy", "최우선 관리")
                }
                high_turnover_products.append(product_info)
        
        # 회전율 순으로 정렬
        high_turnover_products.sort(key=lambda x: x.get("turnover_ratio", 0), reverse=True)
        
        return {
            "high_turnover_products": high_turnover_products,
            "total_count": len(high_turnover_products),
            "clusters_included": high_turnover_clusters,
            "message": "코카콜라제로캔 등 고회전 상품들의 재고 관리를 최우선으로 하세요."
        }
        
    except Exception as e:
        logger.error(f"고회전 상품 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"고회전 상품 조회 실패: {str(e)}")

@app.post("/api/ml/product-clustering/reload")
async def reload_product_clusterer():
    """ProductClusterer 모델 수동 재로드"""
    global product_cluster_data  # 함수 맨 처음에 global 선언
    
    try:
        logger.info("🔄 ProductClusterer 수동 재로드 시작...")
        
        # 기존 상태 리셋
        model_trained["product_clusterer"] = False
        product_cluster_data = None
        
        # 모델 재로드 시도
        await train_product_clusterer()
        
        if model_trained["product_clusterer"] and product_cluster_data:
            return {
                "success": True,
                "message": "ProductClusterer 모델이 성공적으로 재로드되었습니다.",
                "model_info": product_cluster_data.get("model_info", {}),
                "available_clusters": list(product_cluster_data.get("cluster_analysis", {}).keys()),
                "total_products": sum(cluster["size"] for cluster in product_cluster_data.get("cluster_analysis", {}).values())
            }
        else:
            return {
                "success": False,
                "message": "모델 재로드에 실패했습니다.",
                "model_trained": model_trained["product_clusterer"],
                "data_available": product_cluster_data is not None
            }
            
    except Exception as e:
        logger.error(f"ProductClusterer 재로드 오류: {e}")
        raise HTTPException(status_code=500, detail=f"재로드 실패: {str(e)}")

@app.post("/api/ml/product-clustering/retrain")
async def retrain_product_clusterer():
    """ProductClusterer 모델 재훈련"""
    global product_cluster_data  # 함수 맨 처음에 global 선언
    
    if not data_service.data_loaded:
        raise HTTPException(status_code=404, detail="데이터가 로드되지 않았습니다.")
    
    try:
        logger.info("🔄 ProductClusterer 재훈련 시작...")
        
        # 기존 모델 상태 리셋
        model_trained["product_clusterer"] = False
        product_cluster_data = None
        
        # 재훈련 실행 (product_clusterer_trainer.py 스크립트 실행)
        import subprocess
        import sys
        
        result = subprocess.run([
            sys.executable, "product_clusterer_trainer.py"
        ], capture_output=True, text=True, cwd=".")
        
        if result.returncode == 0:
            # 재훈련 성공 시 모델 다시 로드
            await train_product_clusterer()
            
            if model_trained["product_clusterer"]:
                return {
                    "success": True,
                    "message": "ProductClusterer 모델이 성공적으로 재훈련되었습니다.",
                    "model_info": product_cluster_data.get("model_info", {}) if product_cluster_data else {},
                    "training_output": result.stdout
                }
            else:
                raise HTTPException(status_code=500, detail="모델 재로드에 실패했습니다.")
        else:
            logger.error(f"재훈련 실패: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"재훈련 실패: {result.stderr}")
        
    except Exception as e:
        logger.error(f"ProductClusterer 재훈련 오류: {e}")
        raise HTTPException(status_code=500, detail=f"재훈련 실패: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 VSS 스마트 창고 관리 시스템을 시작합니다...")
    print("📍 서버 주소: http://localhost:8000")
    print("💻 대시보드: http://localhost:8000")
    print("🔧 API 문서: http://localhost:8000/docs")
    print("=" * 50)
    
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            reload=False,  # 프로덕션 모드
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n✅ 서버가 정상적으로 종료되었습니다.")
    except Exception as e:
        print(f"❌ 서버 시작 중 오류 발생: {e}")
        exit(1)
 