#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
빠른 데이터 분석 및 통합 JSON 생성
"""

import pandas as pd
import json
import os
from datetime import datetime

def quick_analysis():
    print("🔍 빠른 데이터 분석 시작...")
    
    # 1. 상품 마스터 로드
    product_master = pd.read_csv("rawdata/product_data.csv")
    print(f"📦 상품 마스터: {len(product_master)} 개")
    
    # 2. 입고 데이터 통합
    inbound_files = [f for f in os.listdir("rawdata") if f.startswith("InboundData_") and f.endswith(".csv")]
    inbound_dfs = []
    
    for file in sorted(inbound_files):
        df = pd.read_csv(f"rawdata/{file}")
        # 빈 컬럼 제거
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df['source_date'] = file.replace('InboundData_', '').replace('.csv', '')
        inbound_dfs.append(df)
        print(f"  📥 {file}: {len(df)} 건")
    
    inbound_data = pd.concat(inbound_dfs, ignore_index=True) if inbound_dfs else pd.DataFrame()
    
    # 3. 출고 데이터 통합  
    outbound_files = [f for f in os.listdir("rawdata") if f.startswith("OutboundData_") and f.endswith(".csv")]
    outbound_dfs = []
    
    for file in sorted(outbound_files):
        df = pd.read_csv(f"rawdata/{file}")
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df['source_date'] = file.replace('OutboundData_', '').replace('.csv', '')
        outbound_dfs.append(df)
        print(f"  📤 {file}: {len(df)} 건")
    
    outbound_data = pd.concat(outbound_dfs, ignore_index=True) if outbound_dfs else pd.DataFrame()
    
    # 4. 기본 통계
    print(f"\n📊 기본 통계:")
    print(f"  - 총 상품: {len(product_master)}")
    print(f"  - 총 입고 건수: {len(inbound_data)}")
    print(f"  - 총 출고 건수: {len(outbound_data)}")
    print(f"  - 입고 총량: {inbound_data['PalleteQty'].sum()}")
    print(f"  - 출고 총량: {outbound_data['PalleteQty'].sum()}")
    
    # 5. ProductCode 매칭 분석
    master_codes = set(product_master['ProductCode'].astype(str))
    inbound_codes = set(inbound_data['ProductCode'].astype(str)) if not inbound_data.empty else set()
    outbound_codes = set(outbound_data['ProductCode'].astype(str)) if not outbound_data.empty else set()
    
    print(f"\n🔍 ProductCode 매칭:")
    print(f"  - 마스터 상품코드: {len(master_codes)}개")
    print(f"  - 입고 상품코드: {len(inbound_codes)}개 (매칭률: {len(inbound_codes & master_codes)/len(inbound_codes)*100:.1f}%)")
    print(f"  - 출고 상품코드: {len(outbound_codes)}개 (매칭률: {len(outbound_codes & master_codes)/len(outbound_codes)*100:.1f}%)")
    
    # 6. 랙별 분포
    rack_distribution = product_master['Rack Name'].value_counts()
    print(f"\n🏢 랙별 상품 분포:")
    for rack, count in rack_distribution.items():
        print(f"  - {rack}: {count}개")
    
    # 7. 재고 계산 (샘플)
    inventory_sample = []
    for _, product in product_master.head(10).iterrows():
        product_code = str(product['ProductCode'])
        initial_stock = product['Start Pallete Qty']
        
        # 해당 상품의 입출고량 계산
        product_inbound = inbound_data[inbound_data['ProductCode'].astype(str) == product_code]
        product_outbound = outbound_data[outbound_data['ProductCode'].astype(str) == product_code]
        
        total_inbound = product_inbound['PalleteQty'].sum() if not product_inbound.empty else 0
        total_outbound = product_outbound['PalleteQty'].sum() if not product_outbound.empty else 0
        current_stock = initial_stock + total_inbound - total_outbound
        
        inventory_sample.append({
            "product_code": product_code,
            "product_name": product['ProductName'][:50] + "..." if len(product['ProductName']) > 50 else product['ProductName'],
            "rack": product['Rack Name'],
            "initial_stock": initial_stock,
            "total_inbound": total_inbound,
            "total_outbound": total_outbound,
            "current_stock": current_stock
        })
    
    print(f"\n💾 재고 계산 샘플 (상위 10개):")
    for item in inventory_sample:
        print(f"  - {item['product_code']}: {item['initial_stock']} + {item['total_inbound']} - {item['total_outbound']} = {item['current_stock']}")
    
    # 8. 통합 JSON 생성
    integrated_data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "analysis_type": "quick_analysis",
            "data_period": "2025-01-01 ~ 2025-01-07"
        },
        "summary": {
            "total_products": len(product_master),
            "total_inbound_records": len(inbound_data),
            "total_outbound_records": len(outbound_data),
            "total_inbound_quantity": int(inbound_data['PalleteQty'].sum()) if not inbound_data.empty else 0,
            "total_outbound_quantity": int(outbound_data['PalleteQty'].sum()) if not outbound_data.empty else 0,
            "rack_distribution": rack_distribution.to_dict()
        },
        "data_quality": {
            "product_code_matching": {
                "master_codes": len(master_codes),
                "inbound_match_rate": round(len(inbound_codes & master_codes)/len(inbound_codes)*100, 2) if inbound_codes else 0,
                "outbound_match_rate": round(len(outbound_codes & master_codes)/len(outbound_codes)*100, 2) if outbound_codes else 0
            }
        },
        "inventory_sample": inventory_sample,
        "insights": {
            "most_active_rack": rack_distribution.index[0] if not rack_distribution.empty else "N/A",
            "inventory_turnover": "중간" if len(inbound_data) > 0 and len(outbound_data) > 0 else "데이터 부족",
            "data_completeness": "양호" if len(master_codes & inbound_codes) > len(master_codes) * 0.8 else "개선 필요"
        }
    }
    
    # JSON 파일 저장
    with open("quick_warehouse_analysis.json", "w", encoding="utf-8") as f:
        json.dump(integrated_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n✅ 분석 완료! quick_warehouse_analysis.json 생성됨")
    return integrated_data

if __name__ == "__main__":
    result = quick_analysis()