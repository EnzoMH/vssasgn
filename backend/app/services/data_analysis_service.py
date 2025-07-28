import pandas as pd
from typing import Dict, Any, List, Optional
from backend.app.models.ml_models import AnomalyDetector # AnomalyDetector 임포트

class DataAnalysisService:
    def __init__(self, data_service, anomaly_detector: AnomalyDetector = None):
        self.data_service = data_service
        self.anomaly_detector = anomaly_detector # AnomalyDetector 인스턴스 저장

    def get_descriptive_stats(self, df_name: str) -> Dict[str, Any]:
        df = getattr(self.data_service, df_name, pd.DataFrame())
        if df.empty:
            return {"message": f"데이터셋 '{df_name}'이 비어 있습니다."}
        
        stats = {
            "shape": df.shape,
            "columns": df.columns.tolist(),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "missing_values": df.isnull().sum().to_dict(),
            "unique_values_count": {col: df[col].nunique() for col in df.columns},
            "description": df.describe(include='all').to_dict()
        }
        return stats

    def get_daily_movement_summary(self) -> pd.DataFrame:
        inbound_df = self.data_service.inbound_data
        outbound_df = self.data_service.outbound_data

        if inbound_df.empty and outbound_df.empty:
            return pd.DataFrame() # 빈 데이터프레임 반환

        # 날짜 컬럼 통합 및 일별 집계
        def preprocess_df_for_daily_movement(df):
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df['date'] = df['Date'].dt.date # 날짜만 추출
            return df

        inbound_daily = pd.DataFrame()
        if not inbound_df.empty:
            inbound_processed = preprocess_df_for_daily_movement(inbound_df.copy())
            inbound_daily = inbound_processed.groupby('date').size().reset_index(name='inbound') # 컬럼명 'inbound'로 통일
        
        outbound_daily = pd.DataFrame()
        if not outbound_df.empty:
            outbound_processed = preprocess_df_for_daily_movement(outbound_df.copy())
            outbound_daily = outbound_processed.groupby('date').size().reset_index(name='outbound') # 컬럼명 'outbound'로 통일

        merged_df = pd.merge(inbound_daily, outbound_daily, on='date', how='outer').fillna(0)
        # 'inbound'와 'outbound' 컬럼이 존재하도록 확인
        if 'inbound' not in merged_df.columns: merged_df['inbound'] = 0
        if 'outbound' not in merged_df.columns: merged_df['outbound'] = 0

        merged_df['date'] = merged_df['date'].astype(str)
        merged_df = merged_df.sort_values(by='date')
        return merged_df
    
    async def detect_anomalies_data(self) -> Dict[str, Any]:
        if not self.data_service.data_loaded:
            return {"anomalies": [], "message": "데이터가 로드되지 않았습니다."}
        
        if not self.anomaly_detector:
            return {"anomalies": [], "message": "이상 탐지 모델이 초기화되지 않았습니다."}

        daily_movement_summary = self.get_daily_movement_summary()
        if daily_movement_summary.empty:
            return {"anomalies": [], "message": "이상 탐지 분석을 위한 데이터가 없습니다."}
        
        # 'inbound'와 'outbound' 컬럼이 있는지 확인
        required_features = ['inbound', 'outbound']
        if not all(feature in daily_movement_summary.columns for feature in required_features):
            return {"anomalies": [], "message": "이상 탐지를 위한 필수 컬럼(inbound, outbound)이 데이터에 없습니다."}

        features = daily_movement_summary[required_features].copy()

        # 모델 학습 (만약 이미 학습되었다면 건너뛸 수 있도록 AnomalyDetector 내부에서 처리)
        # 여기서는 DataAnalysisService에서 직접 학습을 트리거
        try:
            self.anomaly_detector.train(features)
        except Exception as e:
            return {"anomalies": [], "message": f"이상 탐지 모델 학습 중 오류 발생: {e}"}

        anomalies_scores = self.anomaly_detector.detect_anomalies(features)

        # 이상치로 분류된 데이터만 필터링
        anomaly_dates = daily_movement_summary[anomalies_scores == -1]['date'].tolist()

        if anomaly_dates:
            return {"anomalies": anomaly_dates, "message": f"{len(anomaly_dates)}개의 이상 징후가 감지되었습니다."}
        else:
            return {"anomalies": [], "message": "이상 징후가 감지되지 않았습니다."}

    def get_product_insights(self) -> List[Dict[str, Any]]:
        product_df = self.data_service.product_master
        inbound_df = self.data_service.inbound_data
        outbound_df = self.data_service.outbound_data

        if product_df.empty:
            return []
        
        # 상품별 입출고량 계산 (예시)
        # '상품코드' 또는 '제품명'으로 통합해야 함
        product_insights = product_df.copy()
        
        # 임의로 '상품코드' 컬럼 가정
        if '상품코드' in inbound_df.columns and '수량' in inbound_df.columns:
            inbound_summary = inbound_df.groupby('상품코드')['수량'].sum().reset_index(name='총입고수량')
            product_insights = pd.merge(product_insights, inbound_summary, on='상품코드', how='left').fillna(0)

        if '상품코드' in outbound_df.columns and '수량' in outbound_df.columns:
            outbound_summary = outbound_df.groupby('상품코드')['수량'].sum().reset_index(name='총출고수량')
            product_insights = pd.merge(product_insights, outbound_summary, on='상품코드', how='left').fillna(0)
        
        # 현재고와 총 입/출고 수량 정보 추가 (가정에 따라 컬럼명 다를 수 있음)
        # product_insights['순재고변동'] = product_insights['총입고수량'] - product_insights['총출고수량']

        return product_insights.to_dict(orient='records')
    
    def get_rack_utilization_summary(self) -> List[Dict[str, Any]]:
        product_df = self.data_service.product_master

        if product_df.empty or '랙위치' not in product_df.columns or '현재고' not in product_df.columns:
            return []

        rack_summary = product_df.groupby('랙위치')['현재고'].sum().reset_index(name='현재재고량')
        # 실제 랙 용량 데이터가 없으므로 임의의 용량 추가
        rack_summary['최대용량'] = rack_summary['현재재고량'] * 1.5 + 50 # 예시
        rack_summary['활용률'] = (rack_summary['현재재고량'] / rack_summary['최대용량']).fillna(0)
        
        return rack_summary.to_dict(orient='records') 