from xgboost import XGBRegressor
from sklearn.cluster import KMeans
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