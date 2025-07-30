#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSS ML 모델용 특징 엔지니어링
Phase 1: ProductClusterer를 위한 상품별 특징 추출
"""

import pandas as pd
import numpy as np
import json
from typing import Dict, List, Any
import re
from sklearn.preprocessing import StandardScaler, LabelEncoder
import warnings
warnings.filterwarnings('ignore')

class ProductFeatureExtractor:
    def __init__(self, data_file: str = "integrated_warehouse_data.json"):
        self.data_file = data_file
        self.warehouse_data = None
        self.product_features = None
        self.scaler = StandardScaler()
        self.label_encoders = {}
        
    def load_warehouse_data(self):
        """통합 창고 데이터 로드"""
        print("📊 창고 데이터 로딩 중...")
        
        with open(self.data_file, 'r', encoding='utf-8') as f:
            self.warehouse_data = json.load(f)
        
        print(f"✅ 데이터 로드 완료")
        print(f"   - 상품 수: {len(self.warehouse_data['inventory_analysis']['products'])}")
        print(f"   - 랙 수: {len(self.warehouse_data['inventory_analysis']['rack_summary'])}")
        
    def extract_basic_features(self) -> pd.DataFrame:
        """기본 특징 추출: 회전율, 입출고량, 재고량, 랙위치"""
        print("\n🔍 기본 특징 추출 중...")
        
        products = self.warehouse_data['inventory_analysis']['products']
        
        basic_features = []
        for product in products:
            features = {
                'product_code': product['product_code'],
                'product_name': product['product_name'],
                'unit': product['unit'],
                'rack_name': product['rack_name'],
                
                # 기본 수치 특징
                'initial_stock': product['initial_stock'],
                'total_inbound': product['total_inbound'],
                'total_outbound': product['total_outbound'],
                'current_stock': product['current_stock'],
                'turnover_ratio': product['turnover_ratio'],
                
                # 파생 특징
                'stock_change': product['current_stock'] - product['initial_stock'],
                'inbound_outbound_ratio': product['total_inbound'] / max(product['total_outbound'], 1),
                'stock_efficiency': product['current_stock'] / max(product['initial_stock'], 1)
            }
            basic_features.append(features)
        
        df = pd.DataFrame(basic_features)
        print(f"✅ 기본 특징 추출 완료: {df.shape[1]} 개 특징")
        return df
    
    def extract_advanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """고급 특징 추출: 상품카테고리, 일별변동성, 이동평균"""
        print("\n🧠 고급 특징 추출 중...")
        
        # 1. 상품 카테고리 추출 (제품명에서)
        df['product_category'] = df['product_name'].apply(self._extract_category)
        
        # 2. 랙 그룹 (A-O: 고밀도, P-T: 중밀도, U-Z: 저밀도)
        df['rack_group'] = df['rack_name'].apply(self._categorize_rack)
        
        # 3. 단위별 그룹
        df['unit_group'] = df['unit'].apply(self._categorize_unit)
        
        # 4. 일별 변동성 계산 (daily_movements에서)
        df['daily_variance'] = df.apply(lambda row: self._calculate_daily_variance(row['product_code']), axis=1)
        
        # 5. 이동평균 (3일, 7일)
        df['inbound_ma3'] = df.apply(lambda row: self._calculate_moving_average(row['product_code'], 3, 'inbound'), axis=1)
        df['outbound_ma3'] = df.apply(lambda row: self._calculate_moving_average(row['product_code'], 3, 'outbound'), axis=1)
        
        # 6. 공급업체 그룹 (입고 데이터에서 추출)
        df['supplier_diversity'] = df['product_code'].apply(self._get_supplier_count)
        
        # 7. 비즈니스 중요도 (회전율 + 재고량 기반)
        df['business_importance'] = (df['turnover_ratio'] * 0.7 + 
                                   (df['total_outbound'] / df['total_outbound'].max()) * 0.3)
        
        print(f"✅ 고급 특징 추출 완료: {df.shape[1]} 개 특징")
        return df
    
    def _extract_category(self, product_name: str) -> str:
        """상품명에서 카테고리 추출"""
        name_lower = product_name.lower()
        
        if any(keyword in name_lower for keyword in ['면', '라면', '사리']):
            return '면류'
        elif any(keyword in name_lower for keyword in ['콜라', '사이다', '주스', '생수', '음료']):
            return '음료'
        elif any(keyword in name_lower for keyword in ['설탕', '된장', '쌀', '밀가루', '소금']):
            return '조미료'
        elif any(keyword in name_lower for keyword in ['우유', '치즈', '버터']):
            return '유제품'
        elif any(keyword in name_lower for keyword in ['고기', '생선', '닭']):
            return '육류'
        elif any(keyword in name_lower for keyword in ['야채', '과일', '채소']):
            return '농산물'
        else:
            return '기타'
    
    def _categorize_rack(self, rack_name: str) -> str:
        """랙을 밀도별로 분류"""
        if rack_name in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O']:
            return '고밀도'  # 5개 상품/랙
        elif rack_name in ['P', 'Q', 'R', 'S', 'T']:
            return '중밀도'  # 4개 상품/랙
        else:
            return '저밀도'  # 1개 상품/랙
    
    def _categorize_unit(self, unit: str) -> str:
        """단위별 분류"""
        if unit in ['BOX']:
            return '박스형'
        elif unit in ['EA']:
            return '개별형'
        elif unit in ['PAC', 'KG']:
            return '포장형'
        else:
            return '기타'
    
    def _calculate_daily_variance(self, product_code: str) -> float:
        """일별 입출고 변동성 계산"""
        try:
            products = self.warehouse_data['inventory_analysis']['products']
            product = next(p for p in products if p['product_code'] == product_code)
            
            movements = product.get('daily_movements', [])
            if len(movements) < 2:
                return 0.0
            
            net_changes = [m['net_change'] for m in movements]
            return np.std(net_changes) if len(net_changes) > 1 else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_moving_average(self, product_code: str, window: int, type_: str) -> float:
        """이동평균 계산"""
        try:
            products = self.warehouse_data['inventory_analysis']['products']
            product = next(p for p in products if p['product_code'] == product_code)
            
            movements = product.get('daily_movements', [])
            if len(movements) < window:
                return 0.0
            
            values = [m[type_] for m in movements[-window:]]
            return np.mean(values)
            
        except Exception:
            return 0.0
    
    def _get_supplier_count(self, product_code: str) -> int:
        """해당 상품의 공급업체 다양성 (임시: 랜덤)"""
        # 실제로는 입고 데이터에서 공급업체 수를 계산해야 함
        # 현재는 상품 코드 기반으로 임시 계산
        hash_val = hash(product_code) % 5
        return max(1, hash_val)  # 1-4개 공급업체
    
    def preprocess_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """특징 전처리: 인코딩, 정규화, 결측값 처리"""
        print("\n🔧 특징 전처리 중...")
        
        # 사본 생성
        processed_df = df.copy()
        
        # 1. 범주형 변수 인코딩
        categorical_features = ['product_category', 'rack_group', 'unit_group', 'rack_name', 'unit']
        
        for feature in categorical_features:
            if feature in processed_df.columns:
                le = LabelEncoder()
                processed_df[f'{feature}_encoded'] = le.fit_transform(processed_df[feature].astype(str))
                self.label_encoders[feature] = le
        
        # 2. 결측값 처리
        numeric_columns = processed_df.select_dtypes(include=[np.number]).columns
        processed_df[numeric_columns] = processed_df[numeric_columns].fillna(0)
        
        # 3. 이상값 처리 (IQR 방법)
        for col in ['turnover_ratio', 'daily_variance']:
            if col in processed_df.columns:
                Q1 = processed_df[col].quantile(0.25)
                Q3 = processed_df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                processed_df[col] = processed_df[col].clip(lower_bound, upper_bound)
        
        print(f"✅ 전처리 완료: {processed_df.shape}")
        return processed_df
    
    def get_clustering_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """클러스터링용 최종 특징 선택 및 정규화"""
        print("\n🎯 클러스터링 특징 선택 중...")
        
        # 클러스터링에 사용할 핵심 특징들
        clustering_features = [
            'turnover_ratio',           # 회전율 (가장 중요)
            'business_importance',      # 비즈니스 중요도
            'daily_variance',          # 일별 변동성
            'inbound_outbound_ratio',  # 입출고 비율
            'stock_efficiency',        # 재고 효율성
            'supplier_diversity',      # 공급업체 다양성
            'product_category_encoded', # 상품 카테고리
            'rack_group_encoded',      # 랙 그룹
            'unit_group_encoded'       # 단위 그룹
        ]
        
        # 존재하는 특징만 선택
        available_features = [f for f in clustering_features if f in df.columns]
        
        if not available_features:
            raise ValueError("클러스터링용 특징이 없습니다!")
        
        feature_df = df[available_features].copy()
        
        # 정규화
        feature_df_scaled = pd.DataFrame(
            self.scaler.fit_transform(feature_df),
            columns=feature_df.columns,
            index=feature_df.index
        )
        
        print(f"✅ 클러스터링 특징 준비 완료: {len(available_features)} 개 특징")
        print(f"   특징 목록: {available_features}")
        
        return feature_df_scaled, available_features
    
    def run_feature_extraction(self):
        """전체 특징 추출 프로세스 실행"""
        print("🚀 ProductClusterer 특징 추출 시작\n")
        
        # 1. 데이터 로드
        self.load_warehouse_data()
        
        # 2. 기본 특징 추출
        basic_df = self.extract_basic_features()
        
        # 3. 고급 특징 추출
        advanced_df = self.extract_advanced_features(basic_df)
        
        # 4. 전처리
        processed_df = self.preprocess_features(advanced_df)
        
        # 5. 클러스터링용 특징 준비
        clustering_features, feature_names = self.get_clustering_features(processed_df)
        
        # 6. 결과 저장
        self.product_features = processed_df
        
        result = {
            'full_features': processed_df,
            'clustering_features': clustering_features,
            'feature_names': feature_names,
            'scaler': self.scaler,
            'label_encoders': self.label_encoders
        }
        
        print(f"\n🎉 특징 추출 완료!")
        print(f"   - 총 상품 수: {len(processed_df)}")
        print(f"   - 전체 특징 수: {processed_df.shape[1]}")
        print(f"   - 클러스터링 특징 수: {len(feature_names)}")
        
        return result

if __name__ == "__main__":
    # 특징 추출 실행
    extractor = ProductFeatureExtractor()
    features = extractor.run_feature_extraction()
    
    # 결과 미리보기
    print("\n📊 특징 미리보기:")
    print(features['full_features'][['product_code', 'product_name', 'turnover_ratio', 'business_importance']].head(10))
    
    print("\n🎯 클러스터링 특징 미리보기:")
    print(features['clustering_features'].head())