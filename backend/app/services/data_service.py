import pandas as pd
import os
import logging
from typing import Dict, List

# Logger 설정
logger = logging.getLogger(__name__)

class DataService:
    def __init__(self):
        self.inbound_data: pd.DataFrame = pd.DataFrame()
        self.outbound_data: pd.DataFrame = pd.DataFrame()
        self.product_master: pd.DataFrame = pd.DataFrame()
        self.data_loaded = False # 데이터 로드 여부 플래그

    async def load_all_data(self, rawdata_path: str = "rawdata"):
        if self.data_loaded:
            print("데이터가 이미 로드되었습니다.")
            return

        print(f"데이터 로딩 시작 from {rawdata_path}...")
        all_inbound_dfs = []
        all_outbound_dfs = []

        for filename in os.listdir(rawdata_path):
            file_path = os.path.join(rawdata_path, filename)
            try:
                if "InboundData" in filename and filename.endswith(".csv"):
                    df = pd.read_csv(file_path)
                    # CSV는 'Date' 컬럼 사용 가정
                    all_inbound_dfs.append(df)
                elif "OutboundData" in filename and filename.endswith(".csv"):
                    df = pd.read_csv(file_path)
                    # CSV는 'Date' 컬럼 사용 가정
                    all_outbound_dfs.append(df)
                elif "입고데이터" in filename and filename.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file_path)
                    # Excel은 '거래일자' 컬럼을 'Date'로 변경
                    if '거래일자' in df.columns: df.rename(columns={'거래일자': 'Date'}, inplace=True)
                    all_inbound_dfs.append(df)
                elif "출고데이터" in filename and filename.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file_path)
                    # Excel은 '거래일자' 컬럼을 'Date'로 변경
                    if '거래일자' in df.columns: df.rename(columns={'거래일자': 'Date'}, inplace=True)
                    all_outbound_dfs.append(df)
                elif "product_data" in filename and filename.endswith(".csv"):
                    self.product_master = pd.read_csv(file_path)
                    print(f"상품 마스터 데이터 로드 완료: {filename}")
                elif "상품데이터" in filename and filename.endswith(('.xlsx', '.xls')):
                    self.product_master = pd.read_excel(file_path)
                    
                    found_stock_column = False
                    # 다양한 재고 관련 컬럼명 우선 확인
                    stock_column_candidates = ['현재고', '재고수량', '재고', 'Current Stock', 'Stock Quantity', 'Start Pallete Qty']
                    for candidate in stock_column_candidates:
                        if candidate in self.product_master.columns:
                            if candidate != '현재고': # 이미 '현재고'인 경우는 rename 불필요
                                self.product_master.rename(columns={candidate: '현재고'}, inplace=True)
                            found_stock_column = True
                            break
                    
                    if not found_stock_column:
                        print(f"경고: {filename}에서 '현재고'를 나타내는 적절한 컬럼을 찾을 수 없습니다. '현재고' 컬럼이 없을 수 있습니다.")
                        # 만약 어떤 재고 컬럼도 찾지 못했다면 '현재고' 컬럼을 NaN으로 초기화하거나 0으로 설정
                        if '현재고' not in self.product_master.columns:
                            self.product_master['현재고'] = 0 # 기본값 설정 또는 NaN
                    
                    # '랙위치' 컬럼도 통일 (예시)
                    if 'Rack Name' in self.product_master.columns and '랙위치' not in self.product_master.columns:
                        self.product_master.rename(columns={'Rack Name': '랙위치'}, inplace=True)
                    if 'ProductCode' in self.product_master.columns and '상품코드' not in self.product_master.columns:
                        self.product_master.rename(columns={'ProductCode': '상품코드'}, inplace=True)

                    print(f"상품 마스터 데이터 로드 완료: {filename}")

            except Exception as e:
                print(f"파일 로드 중 오류 발생 {filename}: {e}")
                continue

        if all_inbound_dfs:
            self.inbound_data = pd.concat(all_inbound_dfs, ignore_index=True)
            # 'Date' 컬럼이 datetime 형식인지 확인 및 변환
            if 'Date' in self.inbound_data.columns:
                self.inbound_data['Date'] = pd.to_datetime(self.inbound_data['Date'], errors='coerce')
                # 유효하지 않은 Date 값 (NaT)을 가진 행 제거
                original_rows = len(self.inbound_data)
                self.inbound_data.dropna(subset=['Date'], inplace=True)
                if len(self.inbound_data) < original_rows:
                    print(f"입고 데이터에서 {original_rows - len(self.inbound_data)} 개의 유효하지 않은 'Date' 값을 가진 행을 제거했습니다.")
            # 'Unnamed:' 으로 시작하는 컬럼 제거
            self.inbound_data = self.inbound_data.loc[:, ~self.inbound_data.columns.str.startswith('Unnamed:')]
            print(f"총 입고 데이터 로드 완료: {len(self.inbound_data)} 건")
        if all_outbound_dfs:
            self.outbound_data = pd.concat(all_outbound_dfs, ignore_index=True)
            # 'Date' 컬럼이 datetime 형식인지 확인 및 변환
            if 'Date' in self.outbound_data.columns:
                self.outbound_data['Date'] = pd.to_datetime(self.outbound_data['Date'], errors='coerce')
                # 유효하지 않은 Date 값 (NaT)을 가진 행 제거
                original_rows = len(self.outbound_data)
                self.outbound_data.dropna(subset=['Date'], inplace=True)
                if len(self.outbound_data) < original_rows:
                    print(f"출고 데이터에서 {original_rows - len(self.outbound_data)} 개의 유효하지 않은 'Date' 값을 가진 행을 제거했습니다.")
            # 'Unnamed:' 으로 시작하는 컬럼 제거
            self.outbound_data = self.outbound_data.loc[:, ~self.outbound_data.columns.str.startswith('Unnamed:')]
            print(f"총 출고 데이터 로드 완료: {len(self.outbound_data)} 건")

        if not self.product_master.empty:
            # ProductCode와 ProductName 불일치 확인 (간단한 경고)
            if '상품코드' in self.product_master.columns and 'ProductName' in self.product_master.columns:
                unique_codes = self.product_master['상품코드'].nunique()
                unique_names = self.product_master['ProductName'].nunique()
                if unique_codes != unique_names:
                    print(f"경고: 상품 마스터 데이터에서 상품코드({unique_codes}개)와 상품명({unique_names}개)의 개수가 일치하지 않습니다. 데이터 정합성 확인이 필요합니다.")

            # 현재고가 모두 10으로 고정된 경우 경고
            if '현재고' in self.product_master.columns and (self.product_master['현재고'] == 10).all():
                print("경고: 상품 마스터 데이터의 '현재고' 컬럼 값이 모두 10으로 설정되어 있습니다. 실제 재고 데이터와 다를 수 있으니 확인이 필요합니다.")
                print("현재고 데이터를 정확히 반영하려면 원본 파일(예: rawdata/상품데이터.xlsx 또는 product_data.csv)을 수정해야 합니다.")

        self.data_loaded = True
        print("모든 데이터 로딩 완료.")

    def get_current_summary(self):
        """현재 창고 상태 요약 정보 반환"""
        if not self.data_loaded:
            return {
                "error": "데이터가 로드되지 않았습니다",
                "total_products": 0,
                "total_inventory": 0,
                "daily_inbound": 0,
                "daily_outbound": 0
            }
        
        try:
            summary = {
                "total_products": len(self.product_master) if self.product_master is not None else 0,
                "total_inventory": int(self.product_master['현재고'].sum()) if '현재고' in self.product_master.columns else 0,
                "daily_inbound": len(self.inbound_data) if self.inbound_data is not None else 0,
                "daily_outbound": len(self.outbound_data) if self.outbound_data is not None else 0,
                "available_racks": list(self.product_master['랙위치'].unique()) if '랙위치' in self.product_master.columns else []
            }
            return summary
        except Exception as e:
            print(f"요약 정보 생성 중 오류: {e}")
            return {"error": str(e)}
    
    def calculate_daily_turnover_rate(self):
        """일별 재고회전율 계산 (7일 평균)"""
        if not self.data_loaded:
            return 0.0
            
        try:
            # 총 출고량 (7일간)
            total_outbound = len(self.outbound_data) if self.outbound_data is not None else 0
            # 평균 재고량
            avg_inventory = float(self.product_master['현재고'].sum()) if '현재고' in self.product_master.columns else 1
            
            # 일평균 출고량 / 평균 재고량 = 일별 회전율
            daily_turnover = (total_outbound / 7) / avg_inventory if avg_inventory > 0 else 0
            return round(daily_turnover, 3)
        except Exception as e:
            print(f"회전율 계산 중 오류: {e}")
            return 0.0
    
    def calculate_rack_utilization(self):
        """랙별 활용률 계산 (현실적인 최대용량 기준)"""
        if not self.data_loaded or '랙위치' not in self.product_master.columns:
            return {}
            
        try:
            # 랙별 현재 재고량 집계
            rack_inventory = self.product_master.groupby('랙위치')['현재고'].sum()
            
            # 현실적인 최대용량 설정 (A-Z 각각 60개 용량)
            rack_utilization = {}
            for rack in rack_inventory.index:
                current_stock = int(rack_inventory[rack])
                max_capacity = 60  # 알파벳 랙당 최대 60개 (50개 + 10개 여유분)
                utilization_rate = (current_stock / max_capacity) * 100
                
                rack_utilization[rack] = {
                    "current_stock": current_stock,
                    "max_capacity": max_capacity,
                    "utilization_rate": round(utilization_rate, 1)
                }
            
            return rack_utilization
        except Exception as e:
            print(f"랙 활용률 계산 중 오류: {e}")
            return {}

    def get_relevant_data(self, intent: str):
        if not self.data_loaded:
            print("경고: 데이터가 아직 로드되지 않았습니다. load_all_data()를 먼저 호출하세요.")
            return {"context": "데이터 없음"}

        if intent == "inventory":
            return {"inbound": self.inbound_data.to_dict(orient='records'),
                    "outbound": self.outbound_data.to_dict(orient='records'),
                    "product_master": self.product_master.to_dict(orient='records'),
                    "description": "랙별 재고 현황을 분석하기 위한 입출고 및 상품 마스터 데이터입니다."}
        elif intent == "outbound":
            return {"outbound": self.outbound_data.to_dict(orient='records'),
                    "product_master": self.product_master.to_dict(orient='records'),
                    "description": "출고량 추이 및 제품별 출고 분석을 위한 데이터입니다."}
        elif intent == "prediction":
            # 예측에 필요한 데이터 (예: 과거 입출고, 상품 정보)를 가공하여 반환
            return {"inbound": self.inbound_data.to_dict(orient='records'),
                    "outbound": self.outbound_data.to_dict(orient='records'),
                    "product_master": self.product_master.to_dict(orient='records'),
                    "description": "수요 예측 모델 학습 및 추론에 사용될 데이터입니다."}
        else:
            return {"inbound": self.inbound_data.to_dict(orient='records'),
                    "outbound": self.outbound_data.to_dict(orient='records'),
                    "product_master": self.product_master.to_dict(orient='records'),
                    "description": "일반적인 질문에 답하기 위한 모든 기본 창고 데이터입니다."}
    
    def get_product_category_distribution(self):
        """실제 rawdata 기반 제품 카테고리 분포 계산"""
        if not self.data_loaded or self.product_master.empty:
            return None
            
        try:
            # 제품명 기반 카테고리 분류
            categories = {
                '면류/라면': 0,
                '음료/음료수': 0, 
                '조미료/양념': 0,
                '곡물/쌀': 0,
                '스낵/과자': 0,
                '기타': 0
            }
            
            for _, product in self.product_master.iterrows():
                product_name = str(product.get('ProductName', '')).lower()
                
                # 카테고리 분류 로직
                if any(keyword in product_name for keyword in ['라면', '면', '우동', '국수', '탕면', '사발면', '컵라면']):
                    categories['면류/라면'] += 1
                elif any(keyword in product_name for keyword in ['콜라', '사이다', '주스', '생수', '음료', '커피', '차', '탄산', '드링크']):
                    categories['음료/음료수'] += 1
                elif any(keyword in product_name for keyword in ['간장', '된장', '쌈장', '고추장', '설탕', '엿', '가루', '소스', '양념', '조미료', '케찹']):
                    categories['조미료/양념'] += 1
                elif any(keyword in product_name for keyword in ['쌀', '밀가루', '전분', '시리얼']):
                    categories['곡물/쌀'] += 1
                elif any(keyword in product_name for keyword in ['깡', '스낵', '과자', '바', '크런치']):
                    categories['스낵/과자'] += 1
                else:
                    categories['기타'] += 1
            
            # 차트용 데이터 형식으로 변환
            result = []
            for category, count in categories.items():
                if count > 0:  # 0개인 카테고리는 제외
                    result.append({
                        'name': category,
                        'value': count
                    })
            
            # 개수 기준 내림차순 정렬
            result.sort(key=lambda x: x['value'], reverse=True)
            
            return result
            
        except Exception as e:
            logger.error(f"카테고리 분포 계산 오류: {e}")
            return None
    
    def get_daily_trends_summary(self):
        """실제 rawdata 기반 일별 입출고 트렌드 계산"""
        if not self.data_loaded:
            return None
            
        try:
            import pandas as pd
            from datetime import datetime
            
            # 날짜별 입고/출고량 집계
            daily_trends = []
            
            # 2025.01.01 ~ 2025.01.07 데이터 처리
            for day in range(1, 8):
                date_str = f"2025.01.{day:02d}"
                
                # 입고 데이터 집계
                inbound_day = self.inbound_data[self.inbound_data['Date'].str.contains(f"2025.01.{day:02d}", na=False)]
                total_inbound = inbound_day['PalleteQty'].sum() if not inbound_day.empty else 0
                
                # 출고 데이터 집계
                outbound_day = self.outbound_data[self.outbound_data['Date'].str.contains(f"2025.01.{day:02d}", na=False)]
                total_outbound = outbound_day['PalleteQty'].sum() if not outbound_day.empty else 0
                
                daily_trends.append({
                    'date': date_str,
                    'inbound': int(total_inbound),
                    'outbound': int(total_outbound),
                    'net_change': int(total_inbound - total_outbound)
                })
            
            return daily_trends
            
        except Exception as e:
            logger.error(f"일별 트렌드 계산 오류: {e}")
            return None 