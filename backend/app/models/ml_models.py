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

    def train(self, features: pd.DataFrame):
        self.model.fit(features)

    def cluster_products(self, features: pd.DataFrame):
        # 제품을 회전율별로 클러스터링
        return self.model.predict(features)

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