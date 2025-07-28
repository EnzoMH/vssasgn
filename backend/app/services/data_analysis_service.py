import pandas as pd
from typing import Dict, Any, List, Optional

class DataAnalysisService:
    def __init__(self, data_service):
        self.data_service = data_service

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

    def get_daily_movement_summary(self) -> List[Dict[str, Any]]:
        inbound_df = self.data_service.inbound_data
        outbound_df = self.data_service.outbound_data

        if inbound_df.empty and outbound_df.empty:
            return []

        # 날짜 컬럼 통합 및 일별 집계
        # 'Date' 컬럼을 가정 (실제 데이터에 따라 유동적으로 변경 필요)
        inbound_daily = pd.DataFrame()
        if 'Date' in inbound_df.columns:
            inbound_daily = inbound_df.groupby(pd.to_datetime(inbound_df['Date']).dt.date).size().reset_index(name='inbound_count')
            inbound_daily.columns = ['date', 'inbound_count']
        
        outbound_daily = pd.DataFrame()
        if 'Date' in outbound_df.columns:
            outbound_daily = outbound_df.groupby(pd.to_datetime(outbound_df['Date']).dt.date).size().reset_index(name='outbound_count')
            outbound_daily.columns = ['date', 'outbound_count']

        merged_df = pd.merge(inbound_daily, outbound_daily, on='date', how='outer').fillna(0)
        merged_df['date'] = merged_df['date'].astype(str)
        merged_df = merged_df.sort_values(by='date')
        return merged_df.to_dict(orient='records')
    
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