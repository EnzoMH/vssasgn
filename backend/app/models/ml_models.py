from xgboost import XGBRegressor
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest # IsolationForest 추가
import pandas as pd

class DemandPredictor:
    def __init__(self):
        self.model = XGBRegressor()

    def train(self, X: pd.DataFrame, y: pd.Series):
        self.model.fit(X, y)

    def predict_daily_demand(self, features: pd.DataFrame):
        # 다음날 제품별 출고량 예측
        return self.model.predict(features)

class ProductClusterer:
    def __init__(self, n_clusters: int = 4):
        self.model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10) # n_init 추가
        self.feature_scaler = None  # 훈련된 모델의 스케일러
        self.label_encoders = None  # 훈련된 모델의 인코더들

    def train(self, features: pd.DataFrame):
        self.model.fit(features)

    def cluster_products(self, features: pd.DataFrame):
        # 제품을 회전율별로 클러스터링
        # 주의: 훈련된 모델을 사용할 때는 특징이 일치해야 함
        if hasattr(self.model, 'feature_names_in_'):
            # 새로운 특징이 있다면 에러 발생
            missing_features = set(self.model.feature_names_in_) - set(features.columns)
            if missing_features:
                raise ValueError(f"훈련된 모델에 필요한 특징이 없습니다: {missing_features}")
        
        return self.model.predict(features)
    
    def predict_single_product(self, product_features: dict):
        """단일 상품에 대한 클러스터 예측 (실제 특징 사용)"""
        # 실제 구현에서는 ml_feature_engineering.py의 특징 추출 로직 사용
        # 현재는 간단한 매핑으로 대체
        if not hasattr(self.model, 'n_clusters'):
            raise ValueError("모델이 훈련되지 않았습니다.")
        
        # 임시로 회전율 기반 클러스터 할당
        turnover = product_features.get('turnover_ratio', 1.0)
        if turnover >= 1.8:
            return 0  # 프리미엄 고회전
        elif turnover >= 1.5:
            return 2  # 프리미엄 고회전 (두 번째 그룹)
        else:
            return 1  # 주력 상품
    
    def get_cluster_info(self):
        """현재 모델의 클러스터 정보 반환"""
        if hasattr(self.model, 'n_clusters'):
            return {
                "n_clusters": self.model.n_clusters,
                "cluster_centers": self.model.cluster_centers_.tolist() if hasattr(self.model, 'cluster_centers_') else None,
                "model_type": "KMeans"
            }
        return None

class AnomalyDetector:
    def __init__(self, contamination: float = 0.05):
        # contamination은 이상치 비율 (예상치)
        self.model = IsolationForest(contamination=contamination, random_state=42)

    def train(self, X: pd.DataFrame):
        # X는 이상 징후를 탐지할 특징 데이터 (예: 일별 입출고량, 재고 변동 등)
        self.model.fit(X)

    def detect_anomalies(self, X: pd.DataFrame) -> pd.Series:
        # -1은 이상치, 1은 정상
        return self.model.predict(X) 