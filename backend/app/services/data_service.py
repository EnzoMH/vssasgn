import pandas as pd
import os
from typing import Dict, List

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
                    all_inbound_dfs.append(df)
                elif "OutboundData" in filename and filename.endswith(".csv"):
                    df = pd.read_csv(file_path)
                    all_outbound_dfs.append(df)
                elif "입고데이터" in filename and filename.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file_path)
                    all_inbound_dfs.append(df)
                elif "출고데이터" in filename and filename.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file_path)
                    all_outbound_dfs.append(df)
                elif "product_data" in filename and filename.endswith(".csv"):
                    self.product_master = pd.read_csv(file_path)
                    print(f"상품 마스터 데이터 로드 완료: {filename}")
                elif "상품데이터" in filename and filename.endswith(('.xlsx', '.xls')):
                    self.product_master = pd.read_excel(file_path)
                    print(f"상품 마스터 데이터 로드 완료: {filename}")

            except Exception as e:
                print(f"파일 로드 중 오류 발생 {filename}: {e}")
                continue

        if all_inbound_dfs:
            self.inbound_data = pd.concat(all_inbound_dfs, ignore_index=True)
            print(f"총 입고 데이터 로드 완료: {len(self.inbound_data)} 건")
        if all_outbound_dfs:
            self.outbound_data = pd.concat(all_outbound_dfs, ignore_index=True)
            print(f"총 출고 데이터 로드 완료: {len(self.outbound_data)} 건")

        self.data_loaded = True
        print("모든 데이터 로딩 완료.")

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