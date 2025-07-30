#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSS ProductClusterer 모델 훈련
Phase 1.2: K-Means 클러스터링 모델 훈련 및 최적화
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, calinski_harabasz_score
from sklearn.decomposition import PCA
import json
import joblib
from ml_feature_engineering import ProductFeatureExtractor
import warnings
warnings.filterwarnings('ignore')

class ProductClustererTrainer:
    def __init__(self):
        self.extractor = ProductFeatureExtractor()
        self.features_data = None
        self.best_model = None
        self.best_n_clusters = None
        self.cluster_results = None
        
    def find_optimal_clusters(self, X, max_clusters=8):
        """최적 클러스터 수 찾기 (Elbow Method + Silhouette Score)"""
        print("🔍 최적 클러스터 수 탐색 중...")
        
        K_range = range(2, max_clusters + 1)
        inertias = []
        silhouette_scores = []
        calinski_scores = []
        
        for k in K_range:
            # K-Means 모델 훈련
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(X)
            
            # 평가 지표 계산
            inertias.append(kmeans.inertia_)
            silhouette_scores.append(silhouette_score(X, cluster_labels))
            calinski_scores.append(calinski_harabasz_score(X, cluster_labels))
            
            print(f"   K={k}: Silhouette={silhouette_scores[-1]:.3f}, Calinski={calinski_scores[-1]:.1f}")
        
        # 최적 클러스터 수 결정 (Silhouette Score 기준)
        best_idx = np.argmax(silhouette_scores)
        best_k = K_range[best_idx]
        
        print(f"✅ 최적 클러스터 수: {best_k} (Silhouette Score: {silhouette_scores[best_idx]:.3f})")
        
        return best_k, {
            'K_range': list(K_range),
            'inertias': inertias,
            'silhouette_scores': silhouette_scores,
            'calinski_scores': calinski_scores
        }
    
    def train_kmeans_model(self, X, n_clusters):
        """K-Means 모델 훈련"""
        print(f"\n🎯 K-Means 모델 훈련 중 (K={n_clusters})...")
        
        # 모델 훈련
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(X)
        
        # 성능 평가
        silhouette_avg = silhouette_score(X, cluster_labels)
        calinski_score = calinski_harabasz_score(X, cluster_labels)
        
        print(f"✅ 모델 훈련 완료")
        print(f"   - Silhouette Score: {silhouette_avg:.3f}")
        print(f"   - Calinski-Harabasz Score: {calinski_score:.1f}")
        print(f"   - Inertia: {kmeans.inertia_:.1f}")
        
        return kmeans, cluster_labels
    
    def analyze_clusters(self, df, cluster_labels, feature_names):
        """클러스터 분석 및 해석"""
        print("\n🔍 클러스터 분석 중...")
        
        # 클러스터 라벨 추가
        df_with_clusters = df.copy()
        df_with_clusters['cluster'] = cluster_labels
        
        cluster_analysis = {}
        
        for cluster_id in range(len(np.unique(cluster_labels))):
            cluster_data = df_with_clusters[df_with_clusters['cluster'] == cluster_id]
            
            # 기본 통계
            analysis = {
                'size': len(cluster_data),
                'percentage': len(cluster_data) / len(df) * 100,
                'key_products': [],
                'characteristics': {}
            }
            
            # 주요 특징 계산
            for feature in ['turnover_ratio', 'business_importance', 'daily_variance']:
                if feature in df.columns:
                    analysis['characteristics'][feature] = {
                        'mean': cluster_data[feature].mean(),
                        'std': cluster_data[feature].std(),
                        'median': cluster_data[feature].median()
                    }
            
            # 대표 상품 (business_importance 상위 3개)
            if 'business_importance' in df.columns:
                top_products = cluster_data.nlargest(3, 'business_importance')
                for _, product in top_products.iterrows():
                    analysis['key_products'].append({
                        'product_code': product.get('product_code', 'Unknown'),
                        'product_name': product.get('product_name', 'Unknown')[:30] + '...',
                        'turnover_ratio': product.get('turnover_ratio', 0),
                        'business_importance': product.get('business_importance', 0)
                    })
            
            cluster_analysis[f"cluster_{cluster_id}"] = analysis
            
            print(f"   Cluster {cluster_id}: {analysis['size']}개 상품 ({analysis['percentage']:.1f}%)")
        
        return cluster_analysis
    
    def interpret_clusters(self, cluster_analysis):
        """클러스터에 비즈니스 의미 부여"""
        print("\n🧠 클러스터 해석 중...")
        
        interpretations = {}
        
        for cluster_id, analysis in cluster_analysis.items():
            characteristics = analysis['characteristics']
            
            # 회전율과 중요도 기준으로 해석
            turnover_mean = characteristics.get('turnover_ratio', {}).get('mean', 0)
            importance_mean = characteristics.get('business_importance', {}).get('mean', 0)
            variance_mean = characteristics.get('daily_variance', {}).get('mean', 0)
            
            # 클러스터 유형 결정
            if turnover_mean > 1.5 and importance_mean > 0.7:
                cluster_type = "프리미엄 고회전"
                strategy = "최우선 관리, 안전재고 확보"
                color = "red"
            elif turnover_mean > 1.0 and importance_mean > 0.5:
                cluster_type = "주력 상품"
                strategy = "정기 모니터링, 수요 예측 강화"
                color = "orange"
            elif turnover_mean < 0.5 and importance_mean < 0.3:
                cluster_type = "저활동 상품"
                strategy = "재고 최소화, 공간 효율화"
                color = "blue"
            else:
                cluster_type = "일반 상품"
                strategy = "표준 관리 정책 적용"
                color = "green"
            
            interpretations[cluster_id] = {
                'type': cluster_type,
                'strategy': strategy,
                'color': color,
                'metrics': {
                    'avg_turnover': round(turnover_mean, 2),
                    'avg_importance': round(importance_mean, 2),
                    'avg_variance': round(variance_mean, 2)
                }
            }
            
            print(f"   {cluster_id}: {cluster_type} (회전율: {turnover_mean:.2f})")
        
        return interpretations
    
    def save_model_and_results(self, model, results, interpretations):
        """모델과 결과 저장"""
        print("\n💾 모델 및 결과 저장 중...")
        
        # 모델 저장
        joblib.dump(model, 'trained_product_clusterer.pkl')
        
        # 결과 저장
        final_results = {
            'model_info': {
                'model_type': 'KMeans',
                'n_clusters': model.n_clusters,
                'random_state': model.random_state,
                'trained_at': pd.Timestamp.now().isoformat()
            },
            'cluster_analysis': results,
            'cluster_interpretations': interpretations,
            'model_performance': {
                'inertia': model.inertia_,
                'feature_count': len(self.features_data['feature_names'])
            }
        }
        
        with open('product_cluster_results.json', 'w', encoding='utf-8') as f:
            json.dump(final_results, f, ensure_ascii=False, indent=2, default=str)
        
        print("✅ 저장 완료:")
        print("   - trained_product_clusterer.pkl")
        print("   - product_cluster_results.json")
    
    def train_complete_pipeline(self):
        """전체 훈련 파이프라인 실행"""
        print("🚀 ProductClusterer 훈련 파이프라인 시작\n")
        
        # 1. 특징 추출
        print("Phase 1: 특징 추출")
        self.features_data = self.extractor.run_feature_extraction()
        
        X = self.features_data['clustering_features']
        df_full = self.features_data['full_features']
        feature_names = self.features_data['feature_names']
        
        # 2. 최적 클러스터 수 찾기
        print(f"\nPhase 2: 최적 클러스터 수 탐색 (데이터: {X.shape})")
        self.best_n_clusters, optimization_results = self.find_optimal_clusters(X, max_clusters=8)
        
        # 3. 최종 모델 훈련
        print(f"\nPhase 3: 최종 모델 훈련")
        self.best_model, cluster_labels = self.train_kmeans_model(X, self.best_n_clusters)
        
        # 4. 클러스터 분석
        print(f"\nPhase 4: 클러스터 분석")
        cluster_analysis = self.analyze_clusters(df_full, cluster_labels, feature_names)
        
        # 5. 클러스터 해석
        print(f"\nPhase 5: 비즈니스 해석")
        interpretations = self.interpret_clusters(cluster_analysis)
        
        # 6. 결과 저장
        print(f"\nPhase 6: 결과 저장")
        self.save_model_and_results(self.best_model, cluster_analysis, interpretations)
        
        # 7. 요약 출력
        print(f"\n🎉 ProductClusterer 훈련 완료!")
        print(f"   - 최적 클러스터 수: {self.best_n_clusters}")
        print(f"   - 훈련 상품 수: {len(df_full)}")
        print(f"   - 사용 특징 수: {len(feature_names)}")
        
        print(f"\n📊 클러스터별 요약:")
        for cluster_id, interp in interpretations.items():
            size = cluster_analysis[cluster_id]['size']
            percentage = cluster_analysis[cluster_id]['percentage']
            print(f"   {cluster_id}: {interp['type']} ({size}개, {percentage:.1f}%)")
        
        return {
            'model': self.best_model,
            'cluster_analysis': cluster_analysis,
            'interpretations': interpretations,
            'optimization_results': optimization_results,
            'features_data': self.features_data
        }

if __name__ == "__main__":
    # 훈련 실행
    trainer = ProductClustererTrainer()
    results = trainer.train_complete_pipeline()
    
    print(f"\n🎯 다음 단계: main.py에 API 엔드포인트 연동")
    print(f"   - 모델 파일: trained_product_clusterer.pkl")
    print(f"   - 결과 파일: product_cluster_results.json")