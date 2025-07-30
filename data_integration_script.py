#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSS 스마트 창고 관리 시스템
Raw Data 통합 분석 및 전처리 스크립트
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
import warnings
warnings.filterwarnings('ignore')

class WarehouseDataIntegrator:
    def __init__(self, rawdata_path: str = "rawdata"):
        self.rawdata_path = rawdata_path
        self.inbound_data = pd.DataFrame()
        self.outbound_data = pd.DataFrame() 
        self.product_master = pd.DataFrame()
        self.analysis_results = {}
        
    def load_all_csv_files(self):
        """모든 CSV 파일을 로드하고 기본 분석 수행"""
        print("🔍 CSV 파일 로딩 및 분석 시작...")
        
        # 입고 데이터 통합
        inbound_files = [f for f in os.listdir(self.rawdata_path) 
                        if f.startswith('InboundData_') and f.endswith('.csv')]
        
        inbound_dfs = []
        for file in sorted(inbound_files):
            file_path = os.path.join(self.rawdata_path, file)
            df = pd.read_csv(file_path)
            # 빈 컬럼 제거
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            df = df.dropna(how='all', axis=1)
            df['source_file'] = file
            inbound_dfs.append(df)
            print(f"  📦 {file}: {len(df)} 건")
            
        if inbound_dfs:
            self.inbound_data = pd.concat(inbound_dfs, ignore_index=True)
            # 날짜 변환
            self.inbound_data['Date'] = pd.to_datetime(self.inbound_data['Date'], errors='coerce')
            print(f"✅ 총 입고 데이터: {len(self.inbound_data)} 건")
        
        # 출고 데이터 통합
        outbound_files = [f for f in os.listdir(self.rawdata_path) 
                         if f.startswith('OutboundData_') and f.endswith('.csv')]
        
        outbound_dfs = []
        for file in sorted(outbound_files):
            file_path = os.path.join(self.rawdata_path, file)
            df = pd.read_csv(file_path)
            # 빈 컬럼 제거
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            df = df.dropna(how='all', axis=1)
            df['source_file'] = file
            outbound_dfs.append(df)
            print(f"  🚚 {file}: {len(df)} 건")
            
        if outbound_dfs:
            self.outbound_data = pd.concat(outbound_dfs, ignore_index=True)
            # 날짜 변환
            self.outbound_data['Date'] = pd.to_datetime(self.outbound_data['Date'], errors='coerce')
            print(f"✅ 총 출고 데이터: {len(self.outbound_data)} 건")
        
        # 상품 마스터 데이터
        product_file = os.path.join(self.rawdata_path, 'product_data.csv')
        if os.path.exists(product_file):
            self.product_master = pd.read_csv(product_file)
            print(f"✅ 상품 마스터: {len(self.product_master)} 건")
    
    def validate_data_quality(self):
        """데이터 품질 검증"""
        print("\n🔍 데이터 품질 검증 중...")
        
        validation_results = {
            "product_code_matching": {},
            "date_continuity": {},
            "data_completeness": {},
            "anomaly_detection": {}
        }
        
        # 1. ProductCode 매칭 검증
        if not self.product_master.empty:
            master_codes = set(self.product_master['ProductCode'].astype(str))
            inbound_codes = set(self.inbound_data['ProductCode'].astype(str)) if not self.inbound_data.empty else set()
            outbound_codes = set(self.outbound_data['ProductCode'].astype(str)) if not self.outbound_data.empty else set()
            
            # 매칭률 계산
            inbound_match_rate = len(inbound_codes & master_codes) / len(inbound_codes) if inbound_codes else 0
            outbound_match_rate = len(outbound_codes & master_codes) / len(outbound_codes) if outbound_codes else 0
            
            validation_results["product_code_matching"] = {
                "master_products": len(master_codes),
                "inbound_products": len(inbound_codes),
                "outbound_products": len(outbound_codes),
                "inbound_match_rate": round(inbound_match_rate * 100, 2),
                "outbound_match_rate": round(outbound_match_rate * 100, 2),
                "unmatched_inbound": list(inbound_codes - master_codes)[:5],
                "unmatched_outbound": list(outbound_codes - master_codes)[:5]
            }
        
        # 2. 날짜 연속성 검증
        if not self.inbound_data.empty:
            inbound_dates = self.inbound_data['Date'].dropna().dt.date.unique()
            outbound_dates = self.outbound_data['Date'].dropna().dt.date.unique() if not self.outbound_data.empty else np.array([])
            
            validation_results["date_continuity"] = {
                "inbound_date_range": f"{min(inbound_dates)} ~ {max(inbound_dates)}" if len(inbound_dates) > 0 else "없음",
                "outbound_date_range": f"{min(outbound_dates)} ~ {max(outbound_dates)}" if len(outbound_dates) > 0 else "없음",
                "inbound_unique_dates": len(inbound_dates),
                "outbound_unique_dates": len(outbound_dates),
                "date_gaps": self._find_date_gaps(inbound_dates)
            }
        
        # 3. 데이터 완성도 검증
        validation_results["data_completeness"] = {
            "inbound_missing_values": self.inbound_data.isnull().sum().to_dict() if not self.inbound_data.empty else {},
            "outbound_missing_values": self.outbound_data.isnull().sum().to_dict() if not self.outbound_data.empty else {},
            "product_missing_values": self.product_master.isnull().sum().to_dict() if not self.product_master.empty else {}
        }
        
        self.analysis_results["validation"] = validation_results
        print("✅ 데이터 품질 검증 완료")
        
    def _find_date_gaps(self, dates):
        """날짜 연속성에서 빠진 날짜 찾기"""
        if len(dates) < 2:
            return []
        
        sorted_dates = sorted(dates)
        gaps = []
        for i in range(len(sorted_dates) - 1):
            current = sorted_dates[i]
            next_date = sorted_dates[i + 1]
            diff = (next_date - current).days
            if diff > 1:
                gaps.append(f"{current} ~ {next_date} ({diff-1}일 간격)")
        return gaps[:3]  # 최대 3개까지만
    
    def calculate_inventory(self):
        """실제 재고 계산"""
        print("\n🧮 재고 계산 중...")
        
        if self.product_master.empty:
            print("❌ 상품 마스터 데이터가 없어 재고 계산 불가")
            return
        
        inventory_results = []
        
        for _, product in self.product_master.iterrows():
            product_code = str(product['ProductCode'])
            
            # 초기 재고
            initial_stock = product.get('Start Pallete Qty', 0)
            
            # 입고량 계산
            inbound_qty = 0
            if not self.inbound_data.empty:
                product_inbound = self.inbound_data[
                    self.inbound_data['ProductCode'].astype(str) == product_code
                ]
                inbound_qty = product_inbound['PalleteQty'].sum() if not product_inbound.empty else 0
            
            # 출고량 계산
            outbound_qty = 0
            if not self.outbound_data.empty:
                product_outbound = self.outbound_data[
                    self.outbound_data['ProductCode'].astype(str) == product_code
                ]
                outbound_qty = product_outbound['PalleteQty'].sum() if not product_outbound.empty else 0
            
            # 현재 재고 = 초기재고 + 입고 - 출고
            current_stock = initial_stock + inbound_qty - outbound_qty
            
            # 일별 입출고 내역
            daily_movements = self._get_daily_movements(product_code)
            
            inventory_data = {
                "product_code": product_code,
                "product_name": product.get('ProductName', ''),
                "unit": product.get('Unit', ''),
                "rack_name": product.get('Rack Name', ''),
                "initial_stock": int(initial_stock),
                "total_inbound": int(inbound_qty),
                "total_outbound": int(outbound_qty),
                "current_stock": int(current_stock),
                "stock_status": "충분" if current_stock > 5 else "부족" if current_stock > 0 else "재고없음",
                "turnover_ratio": round(outbound_qty / initial_stock, 2) if initial_stock > 0 else 0,
                "daily_movements": daily_movements
            }
            
            inventory_results.append(inventory_data)
        
        # 랙별 집계
        rack_summary = self._calculate_rack_summary(inventory_results)
        
        self.analysis_results["inventory"] = {
            "products": inventory_results,
            "rack_summary": rack_summary,
            "summary_stats": self._calculate_summary_stats(inventory_results)
        }
        
        print(f"✅ {len(inventory_results)}개 상품 재고 계산 완료")
    
    def _get_daily_movements(self, product_code: str):
        """상품별 일별 입출고 내역"""
        movements = []
        
        # 날짜 범위 설정
        all_dates = set()
        if not self.inbound_data.empty:
            inbound_dates = self.inbound_data['Date'].dropna().dt.date
            all_dates.update(inbound_dates)
        if not self.outbound_data.empty:
            outbound_dates = self.outbound_data['Date'].dropna().dt.date
            all_dates.update(outbound_dates)
        
        for date in sorted(all_dates):
            # 해당 날짜 입고량
            inbound_qty = 0
            if not self.inbound_data.empty:
                day_inbound = self.inbound_data[
                    (self.inbound_data['ProductCode'].astype(str) == product_code) &
                    (self.inbound_data['Date'].dt.date == date)
                ]
                inbound_qty = day_inbound['PalleteQty'].sum() if not day_inbound.empty else 0
            
            # 해당 날짜 출고량
            outbound_qty = 0
            if not self.outbound_data.empty:
                day_outbound = self.outbound_data[
                    (self.outbound_data['ProductCode'].astype(str) == product_code) &
                    (self.outbound_data['Date'].dt.date == date)
                ]
                outbound_qty = day_outbound['PalleteQty'].sum() if not day_outbound.empty else 0
            
            if inbound_qty > 0 or outbound_qty > 0:  # 움직임이 있는 날만 기록
                movements.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "inbound": int(inbound_qty),
                    "outbound": int(outbound_qty),
                    "net_change": int(inbound_qty - outbound_qty)
                })
        
        return movements[:7]  # 최대 7일치만
    
    def _calculate_rack_summary(self, inventory_results):
        """랙별 집계 계산"""
        rack_data = {}
        
        for item in inventory_results:
            rack_name = item['rack_name']
            if rack_name not in rack_data:
                rack_data[rack_name] = {
                    "rack_name": rack_name,
                    "product_count": 0,
                    "total_initial_stock": 0,
                    "total_current_stock": 0,
                    "total_inbound": 0,
                    "total_outbound": 0,
                    "low_stock_products": []
                }
            
            rack_data[rack_name]["product_count"] += 1
            rack_data[rack_name]["total_initial_stock"] += item["initial_stock"]
            rack_data[rack_name]["total_current_stock"] += item["current_stock"]
            rack_data[rack_name]["total_inbound"] += item["total_inbound"]
            rack_data[rack_name]["total_outbound"] += item["total_outbound"]
            
            if item["current_stock"] <= 5:
                rack_data[rack_name]["low_stock_products"].append({
                    "product_code": item["product_code"],
                    "product_name": item["product_name"][:30] + "..." if len(item["product_name"]) > 30 else item["product_name"],
                    "current_stock": item["current_stock"]
                })
        
        # 이용률 계산 (현재재고/초기재고)
        for rack in rack_data.values():
            if rack["total_initial_stock"] > 0:
                rack["utilization_rate"] = round(rack["total_current_stock"] / rack["total_initial_stock"] * 100, 2)
            else:
                rack["utilization_rate"] = 0
        
        return list(rack_data.values())
    
    def _calculate_summary_stats(self, inventory_results):
        """전체 요약 통계"""
        total_products = len(inventory_results)
        total_current_stock = sum(item["current_stock"] for item in inventory_results)
        total_inbound = sum(item["total_inbound"] for item in inventory_results)
        total_outbound = sum(item["total_outbound"] for item in inventory_results)
        
        low_stock_count = len([item for item in inventory_results if item["current_stock"] <= 5])
        out_of_stock_count = len([item for item in inventory_results if item["current_stock"] <= 0])
        
        high_turnover_products = sorted(
            [item for item in inventory_results if item["turnover_ratio"] > 0.5],
            key=lambda x: x["turnover_ratio"],
            reverse=True
        )[:5]
        
        return {
            "total_products": total_products,
            "total_current_stock": total_current_stock,
            "total_inbound": total_inbound,
            "total_outbound": total_outbound,
            "net_change": total_inbound - total_outbound,
            "low_stock_count": low_stock_count,
            "out_of_stock_count": out_of_stock_count,
            "low_stock_rate": round(low_stock_count / total_products * 100, 2) if total_products > 0 else 0,
            "high_turnover_products": high_turnover_products
        }
    
    def generate_integrated_json(self, output_file: str = "integrated_warehouse_data.json"):
        """통합 JSON 파일 생성"""
        print(f"\n📝 통합 JSON 파일 생성: {output_file}")
        
        # 메타데이터
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "data_period": self._get_data_period(),
            "total_files_processed": len([f for f in os.listdir(self.rawdata_path) if f.endswith('.csv')]),
            "data_quality_score": self._calculate_data_quality_score()
        }
        
        # 통합 데이터 구조
        integrated_data = {
            "metadata": metadata,
            "raw_data_summary": {
                "inbound_records": len(self.inbound_data),
                "outbound_records": len(self.outbound_data),
                "product_master_records": len(self.product_master)
            },
            "data_validation": self.analysis_results.get("validation", {}),
            "inventory_analysis": self.analysis_results.get("inventory", {}),
            "recommendations": self._generate_recommendations()
        }
        
        # JSON 파일 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(integrated_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"✅ JSON 파일 생성 완료: {output_file}")
        return output_file
    
    def _get_data_period(self):
        """데이터 기간 계산"""
        all_dates = []
        if not self.inbound_data.empty:
            all_dates.extend(self.inbound_data['Date'].dropna().dt.date)
        if not self.outbound_data.empty:
            all_dates.extend(self.outbound_data['Date'].dropna().dt.date)
        
        if all_dates:
            return f"{min(all_dates)} ~ {max(all_dates)}"
        return "데이터 없음"
    
    def _calculate_data_quality_score(self):
        """데이터 품질 점수 계산 (0-100)"""
        score = 100
        
        validation = self.analysis_results.get("validation", {})
        
        # ProductCode 매칭률 반영
        matching = validation.get("product_code_matching", {})
        inbound_match = matching.get("inbound_match_rate", 100)
        outbound_match = matching.get("outbound_match_rate", 100)
        score -= (100 - inbound_match) * 0.3
        score -= (100 - outbound_match) * 0.3
        
        # 데이터 완성도 반영 (결측치가 많으면 감점)
        completeness = validation.get("data_completeness", {})
        # 간단한 완성도 체크 (실제로는 더 복잡한 로직 필요)
        
        return max(0, min(100, round(score, 1)))
    
    def _generate_recommendations(self):
        """개선 권장사항 생성"""
        recommendations = []
        
        validation = self.analysis_results.get("validation", {})
        inventory = self.analysis_results.get("inventory", {})
        
        # ProductCode 매칭 문제
        matching = validation.get("product_code_matching", {})
        if matching.get("inbound_match_rate", 100) < 95:
            recommendations.append({
                "category": "데이터 품질",
                "priority": "높음",
                "issue": "입고 데이터의 상품코드 매칭률이 낮음",
                "recommendation": "상품 마스터와 입고 데이터의 ProductCode 정합성 확인 필요"
            })
        
        # 재고 부족 상품
        summary_stats = inventory.get("summary_stats", {})
        if summary_stats.get("low_stock_count", 0) > 0:
            recommendations.append({
                "category": "재고 관리",
                "priority": "중간",
                "issue": f"{summary_stats['low_stock_count']}개 상품이 재고 부족 상태",
                "recommendation": "재고 부족 상품의 우선 보충 계획 수립 필요"
            })
        
        # 높은 회전율 상품
        high_turnover = summary_stats.get("high_turnover_products", [])
        if len(high_turnover) > 0:
            recommendations.append({
                "category": "수요 예측",
                "priority": "낮음",
                "issue": f"{len(high_turnover)}개 상품이 높은 회전율을 보임",
                "recommendation": "고회전율 상품의 안전재고 수준 재검토 권장"
            })
        
        return recommendations
    
    def run_full_analysis(self):
        """전체 분석 프로세스 실행"""
        print("🚀 VSS 창고 데이터 통합 분석 시작\n")
        
        # 1. 데이터 로딩
        self.load_all_csv_files()
        
        # 2. 데이터 품질 검증
        self.validate_data_quality()
        
        # 3. 재고 계산
        self.calculate_inventory()
        
        # 4. JSON 생성
        json_file = self.generate_integrated_json()
        
        print(f"\n🎉 분석 완료!")
        print(f"📊 분석 결과: {json_file}")
        print(f"📈 다음 단계: Gemini AI 인사이트 분석")
        
        return json_file, self.analysis_results

if __name__ == "__main__":
    integrator = WarehouseDataIntegrator()
    json_file, results = integrator.run_full_analysis()