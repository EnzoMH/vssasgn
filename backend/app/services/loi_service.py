"""
LOI (Level of Inventory) 서비스
재고 수준 지표 계산 및 분석
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class LOIService:
    """재고 수준 지표(LOI) 계산 서비스"""
    
    def __init__(self, data_service=None):
        self.data_service = data_service
        
    def calculate_loi_metrics(self) -> Dict[str, Any]:
        """전체 LOI 지표 계산"""
        logger.info("📊 [LOI_CALC] LOI 지표 계산 시작")
        
        if not self.data_service or not self.data_service.data_loaded:
            logger.warning("⚠️ [LOI_ERROR] 데이터 서비스가 없거나 데이터가 로드되지 않음")
            return self._get_default_loi()
        
        try:
            # 기본 데이터 가져오기
            product_df = self.data_service.product_master
            inbound_df = self.data_service.inbound_data
            outbound_df = self.data_service.outbound_data
            
            logger.info(f"📊 [LOI_DATA] 데이터 크기 - 제품: {len(product_df) if product_df is not None else 0}, 입고: {len(inbound_df) if inbound_df is not None else 0}, 출고: {len(outbound_df) if outbound_df is not None else 0}")
            
            # LOI 핵심 지표 계산
            logger.info("🔄 [LOI_METRICS] 각종 LOI 지표 계산 중...")
            loi_metrics = {
                "inventory_level": self._calculate_inventory_level(product_df),
                "stock_coverage": self._calculate_stock_coverage(product_df, outbound_df),
                "safety_stock_ratio": self._calculate_safety_stock_ratio(product_df),
                "inventory_accuracy": self._calculate_inventory_accuracy(product_df, inbound_df, outbound_df),
                "stockout_risk": self._calculate_stockout_risk(product_df, outbound_df),
                "inventory_distribution": self._calculate_inventory_distribution(product_df),
                "timestamp": datetime.now().isoformat()
            }
            
            # 전체 LOI 점수 계산 (0-100)
            logger.info("🎯 [LOI_SCORE] 전체 LOI 점수 계산")
            loi_metrics["overall_loi_score"] = self._calculate_overall_loi_score(loi_metrics)
            
            logger.info(f"✅ [LOI_SUCCESS] LOI 계산 완료 - 전체 점수: {loi_metrics['overall_loi_score']}")
            return loi_metrics
            
        except Exception as e:
            logger.error(f"❌ [LOI_ERROR] LOI 지표 계산 오류: {e}")
            return self._get_default_loi()
    
    def _calculate_inventory_level(self, product_df: pd.DataFrame) -> Dict[str, Any]:
        """재고 수준 계산"""
        if product_df.empty or '현재고' not in product_df.columns:
            return {"total_stock": 0, "avg_stock_per_product": 0, "stock_variance": 0}
        
        total_stock = int(product_df['현재고'].sum())
        avg_stock = float(product_df['현재고'].mean())
        stock_variance = float(product_df['현재고'].var())
        
        return {
            "total_stock": total_stock,
            "avg_stock_per_product": round(avg_stock, 2),
            "stock_variance": round(stock_variance, 2),
            "product_count": len(product_df)
        }
    
    def _calculate_stock_coverage(self, product_df: pd.DataFrame, outbound_df: pd.DataFrame) -> Dict[str, Any]:
        """재고 커버리지 계산 (현재 재고로 몇 일간 운영 가능한지)"""
        if product_df.empty or outbound_df.empty:
            return {"avg_coverage_days": 0, "min_coverage_days": 0, "risk_products": 0}
        
        try:
            # 일별 평균 출고량 계산
            daily_outbound = outbound_df.groupby('Date')['PalleteQty'].sum().mean() if not outbound_df.empty else 1
            
            # 제품별 커버리지 계산
            coverages = []
            risk_count = 0
            
            for _, product in product_df.iterrows():
                current_stock = product.get('현재고', 0)
                # 간단한 추정: 전체 평균 출고량을 제품 수로 나눔
                estimated_daily_usage = daily_outbound / len(product_df) if len(product_df) > 0 else 1
                
                if estimated_daily_usage > 0:
                    coverage_days = current_stock / estimated_daily_usage
                    coverages.append(coverage_days)
                    
                    if coverage_days < 7:  # 7일 미만이면 위험
                        risk_count += 1
                else:
                    coverages.append(999)  # 출고가 없으면 매우 높은 값
            
            return {
                "avg_coverage_days": round(np.mean(coverages), 1) if coverages else 0,
                "min_coverage_days": round(min(coverages), 1) if coverages else 0,
                "risk_products": risk_count,
                "total_products": len(product_df)
            }
            
        except Exception as e:
            logger.error(f"재고 커버리지 계산 오류: {e}")
            return {"avg_coverage_days": 0, "min_coverage_days": 0, "risk_products": 0}
    
    def _calculate_safety_stock_ratio(self, product_df: pd.DataFrame) -> Dict[str, Any]:
        """안전재고 비율 계산"""
        if product_df.empty:
            return {"safety_stock_ratio": 0, "adequate_safety_stock": 0}
        
        try:
            # 안전재고 기준: 초기재고의 20% 이상
            safety_threshold = 0.2
            adequate_count = 0
            
            for _, product in product_df.iterrows():
                initial_stock = product.get('Start Pallete Qty', 0)
                current_stock = product.get('현재고', 0)
                
                if initial_stock > 0:
                    safety_ratio = current_stock / initial_stock
                    if safety_ratio >= safety_threshold:
                        adequate_count += 1
            
            safety_stock_ratio = (adequate_count / len(product_df) * 100) if len(product_df) > 0 else 0
            
            return {
                "safety_stock_ratio": round(safety_stock_ratio, 1),
                "adequate_safety_stock": adequate_count,
                "total_products": len(product_df),
                "safety_threshold": int(safety_threshold * 100)
            }
            
        except Exception as e:
            logger.error(f"안전재고 비율 계산 오류: {e}")
            return {"safety_stock_ratio": 0, "adequate_safety_stock": 0}
    
    def _calculate_inventory_accuracy(self, product_df: pd.DataFrame, inbound_df: pd.DataFrame, outbound_df: pd.DataFrame) -> Dict[str, Any]:
        """재고 정확도 계산"""
        try:
            # 이론적 재고 vs 실제 재고 비교
            # 간단한 추정: 초기재고 + 입고 - 출고 vs 현재고
            
            total_products = len(product_df)
            accurate_count = 0
            
            for _, product in product_df.iterrows():
                product_code = str(product.get('ProductCode', ''))
                initial_stock = product.get('Start Pallete Qty', 0)
                current_stock = product.get('현재고', 0)
                
                # 해당 제품의 입고량
                product_inbound = inbound_df[inbound_df['ProductCode'].astype(str) == product_code]['PalleteQty'].sum() if not inbound_df.empty else 0
                
                # 해당 제품의 출고량
                product_outbound = outbound_df[outbound_df['ProductCode'].astype(str) == product_code]['PalleteQty'].sum() if not outbound_df.empty else 0
                
                # 이론적 재고
                theoretical_stock = initial_stock + product_inbound - product_outbound
                
                # 정확도 허용 범위: ±10%
                if theoretical_stock > 0:
                    accuracy = abs(current_stock - theoretical_stock) / theoretical_stock
                    if accuracy <= 0.1:  # 10% 이내면 정확
                        accurate_count += 1
                elif current_stock == 0:  # 둘 다 0이면 정확
                    accurate_count += 1
            
            accuracy_ratio = (accurate_count / total_products * 100) if total_products > 0 else 100
            
            return {
                "accuracy_ratio": round(accuracy_ratio, 1),
                "accurate_products": accurate_count,
                "total_products": total_products,
                "tolerance": 10  # 허용 오차 10%
            }
            
        except Exception as e:
            logger.error(f"재고 정확도 계산 오류: {e}")
            return {"accuracy_ratio": 0, "accurate_products": 0}
    
    def _calculate_stockout_risk(self, product_df: pd.DataFrame, outbound_df: pd.DataFrame) -> Dict[str, Any]:
        """재고 소진 위험도 계산"""
        try:
            # 위험도 레벨별 분류
            high_risk = 0  # 재고 < 3일분
            medium_risk = 0  # 재고 3-7일분
            low_risk = 0  # 재고 > 7일분
            
            # 일평균 출고량 계산
            if not outbound_df.empty and 'Date' in outbound_df.columns:
                daily_avg_outbound = outbound_df.groupby('Date')['PalleteQty'].sum().mean()
            else:
                daily_avg_outbound = 1
            
            for _, product in product_df.iterrows():
                current_stock = product.get('현재고', 0)
                estimated_daily_usage = daily_avg_outbound / len(product_df) if len(product_df) > 0 else 1
                
                if estimated_daily_usage > 0:
                    days_remaining = current_stock / estimated_daily_usage
                    
                    if days_remaining < 3:
                        high_risk += 1
                    elif days_remaining < 7:
                        medium_risk += 1
                    else:
                        low_risk += 1
                else:
                    low_risk += 1
            
            total_products = len(product_df)
            
            return {
                "high_risk": high_risk,
                "medium_risk": medium_risk,
                "low_risk": low_risk,
                "high_risk_percentage": round((high_risk / total_products * 100), 1) if total_products > 0 else 0,
                "total_products": total_products
            }
            
        except Exception as e:
            logger.error(f"재고 소진 위험도 계산 오류: {e}")
            return {"high_risk": 0, "medium_risk": 0, "low_risk": 0}
    
    def _calculate_inventory_distribution(self, product_df: pd.DataFrame) -> Dict[str, Any]:
        """재고 분포 분석"""
        try:
            if product_df.empty or '랙위치' not in product_df.columns:
                return {"rack_distribution": [], "balanced_score": 0}
            
            # 랙별 재고 분포
            rack_distribution = product_df.groupby('랙위치')['현재고'].sum().to_dict()
            
            # 분포의 균형도 계산 (표준편차 기반)
            rack_stocks = list(rack_distribution.values())
            if len(rack_stocks) > 1:
                std_dev = np.std(rack_stocks)
                mean_stock = np.mean(rack_stocks)
                balance_score = max(0, 100 - (std_dev / mean_stock * 100)) if mean_stock > 0 else 0
            else:
                balance_score = 100
            
            return {
                "rack_distribution": [{"rack": k, "stock": int(v)} for k, v in rack_distribution.items()],
                "balanced_score": round(balance_score, 1),
                "total_racks": len(rack_distribution)
            }
            
        except Exception as e:
            logger.error(f"재고 분포 계산 오류: {e}")
            return {"rack_distribution": [], "balanced_score": 0}
    
    def _calculate_overall_loi_score(self, loi_metrics: Dict[str, Any]) -> float:
        """전체 LOI 점수 계산 (0-100)"""
        try:
            # 각 지표의 가중치
            weights = {
                "safety_stock": 0.25,  # 안전재고 비율
                "accuracy": 0.25,      # 재고 정확도
                "coverage": 0.20,      # 재고 커버리지
                "risk": 0.20,          # 재고 소진 위험
                "balance": 0.10        # 재고 분포 균형
            }
            
            # 각 지표를 0-100 스케일로 정규화
            safety_score = loi_metrics.get("safety_stock_ratio", {}).get("safety_stock_ratio", 0)
            accuracy_score = loi_metrics.get("inventory_accuracy", {}).get("accuracy_ratio", 0)
            
            # 커버리지 점수 (평균 커버리지가 14일 이상이면 100점)
            avg_coverage = loi_metrics.get("stock_coverage", {}).get("avg_coverage_days", 0)
            coverage_score = min(100, (avg_coverage / 14) * 100)
            
            # 위험 점수 (고위험 제품이 적을수록 높은 점수)
            high_risk_pct = loi_metrics.get("stockout_risk", {}).get("high_risk_percentage", 0)
            risk_score = max(0, 100 - (high_risk_pct * 2))  # 고위험 1%당 2점 감점
            
            # 균형 점수
            balance_score = loi_metrics.get("inventory_distribution", {}).get("balanced_score", 0)
            
            # 가중 평균 계산
            overall_score = (
                safety_score * weights["safety_stock"] +
                accuracy_score * weights["accuracy"] +
                coverage_score * weights["coverage"] +
                risk_score * weights["risk"] +
                balance_score * weights["balance"]
            )
            
            return round(overall_score, 1)
            
        except Exception as e:
            logger.error(f"전체 LOI 점수 계산 오류: {e}")
            return 0.0
    
    def _get_default_loi(self) -> Dict[str, Any]:
        """기본 LOI 데이터"""
        return {
            "inventory_level": {
                "total_stock": 0,
                "avg_stock_per_product": 0,
                "stock_variance": 0,
                "product_count": 0
            },
            "stock_coverage": {
                "avg_coverage_days": 0,
                "min_coverage_days": 0,
                "risk_products": 0,
                "total_products": 0
            },
            "safety_stock_ratio": {
                "safety_stock_ratio": 0,
                "adequate_safety_stock": 0,
                "total_products": 0,
                "safety_threshold": 20
            },
            "inventory_accuracy": {
                "accuracy_ratio": 0,
                "accurate_products": 0,
                "total_products": 0,
                "tolerance": 10
            },
            "stockout_risk": {
                "high_risk": 0,
                "medium_risk": 0,
                "low_risk": 0,
                "high_risk_percentage": 0,
                "total_products": 0
            },
            "inventory_distribution": {
                "rack_distribution": [],
                "balanced_score": 0,
                "total_racks": 0
            },
            "overall_loi_score": 0.0,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_loi_alerts(self, loi_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """LOI 기반 알림 생성"""
        alerts = []
        
        try:
            # 고위험 재고 소진 알림
            high_risk_pct = loi_metrics.get("stockout_risk", {}).get("high_risk_percentage", 0)
            if high_risk_pct > 20:
                alerts.append({
                    "type": "error",
                    "level": "high",
                    "tab": "inventory",
                    "message": f"재고 소진 고위험 제품 {high_risk_pct}% 발견",
                    "action": "즉시 재고 보충 필요"
                })
            elif high_risk_pct > 10:
                alerts.append({
                    "type": "warning",
                    "level": "medium",
                    "tab": "inventory",
                    "message": f"재고 소진 위험 제품 {high_risk_pct}% 감지",
                    "action": "재고 수준 점검 권장"
                })
            
            # 재고 정확도 알림
            accuracy = loi_metrics.get("inventory_accuracy", {}).get("accuracy_ratio", 0)
            if accuracy < 80:
                alerts.append({
                    "type": "warning",
                    "level": "medium",
                    "tab": "inventory",
                    "message": f"재고 정확도 {accuracy}% (권장: 90% 이상)",
                    "action": "재고 실사 권장"
                })
            
            # 전체 LOI 점수 알림
            loi_score = loi_metrics.get("overall_loi_score", 0)
            if loi_score < 60:
                alerts.append({
                    "type": "error",
                    "level": "high",
                    "tab": "inventory",
                    "message": f"전체 재고 수준 점수 {loi_score}점 (권장: 80점 이상)",
                    "action": "재고 관리 정책 재검토 필요"
                })
            elif loi_score < 80:
                alerts.append({
                    "type": "warning",
                    "level": "medium",
                    "tab": "inventory",
                    "message": f"재고 수준 점수 {loi_score}점 (목표: 80점 이상)",
                    "action": "재고 최적화 권장"
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"LOI 알림 생성 오류: {e}")
            return []