"""
LangChain Tools + SELF-RAG 구현
할루시네이션 방지 및 정확한 정보 제공을 위한 고급 RAG 시스템
"""

import datetime
import logging
import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# LangChain 관련 import (필요시 설치: pip install langchain langchain-community)
try:
    from langchain.tools import Tool
    from langchain.agents import initialize_agent, AgentType
    from langchain.schema import Document
    LANGCHAIN_AVAILABLE = True
except ImportError:
    # LangChain이 없어도 동작하도록 fallback
    LANGCHAIN_AVAILABLE = False
    Tool = object
    Document = dict

class RAGMode(Enum):
    """RAG 처리 모드"""
    SIMPLE = "simple"           # 기본 RAG
    SELF_RAG = "self_rag"      # SELF-RAG (자체 검증)
    TOOL_ENHANCED = "tool_enhanced"  # LangChain Tools 활용

@dataclass
class RetrievalResult:
    """검색 결과 구조"""
    documents: List[Dict]
    scores: List[float]
    metadata: Dict[str, Any]
    total_found: int
    search_quality: float  # 0.0 ~ 1.0

@dataclass
class CritiqueResult:
    """검색 결과 비평/검증"""
    relevance_score: float      # 관련성 점수 (0.0 ~ 1.0)
    confidence_score: float     # 신뢰도 점수 (0.0 ~ 1.0)
    missing_info: List[str]     # 부족한 정보
    hallucination_risk: float  # 할루시네이션 위험도 (0.0 ~ 1.0)
    needs_additional_search: bool

class LangChainRAGService:
    """LangChain Tools + SELF-RAG 서비스"""
    
    def __init__(self, vector_db_service=None, ai_client=None, data_service=None, 
                 demand_predictor=None, product_clusterer=None, anomaly_detector=None):
        self.vector_db_service = vector_db_service
        self.ai_client = ai_client
        self.data_service = data_service
        self.logger = logging.getLogger(__name__)
        
        # 🤖 ML 모델들 주입
        self.ml_models = {
            'demand_predictor': demand_predictor,
            'product_clusterer': product_clusterer,
            'anomaly_detector': anomaly_detector
        }
        self.logger.info(f"🤖 ML 모델 주입 완료: {[k for k, v in self.ml_models.items() if v is not None]}")
        
        # 현재 날짜/시간 캐시 (할루시네이션 방지용)
        self.current_datetime = datetime.datetime.now()
        self.system_context = self._build_system_context()
        
        # LangChain Tools 초기화
        self.tools = self._create_langchain_tools()
        
        # SELF-RAG 설정
        self.critique_threshold = 0.7  # 검증 통과 임계값
        self.max_retrieval_attempts = 3  # 최대 재검색 횟수
        
        self.logger.info("🔧 LangChain SELF-RAG 서비스 초기화 완료")
    
    def _build_system_context(self) -> Dict[str, Any]:
        """시스템 컨텍스트 구성 (할루시네이션 방지)"""
        return {
            "current_datetime": self.current_datetime.strftime("%Y년 %m월 %d일 %H시 %M분"),
            "current_date": self.current_datetime.strftime("%Y년 %m월 %d일"),
            "current_time": self.current_datetime.strftime("%H시 %M분"),
            "data_range": "2025년 1월 1일 ~ 2025년 1월 7일 (과거 데이터)",
            "system_status": "벡터 검색 가능 (2,900개 문서 인덱싱 완료)",
            "warning": "데이터는 과거 기록이며, 현재 날짜와 다름을 명시할 것"
        }
    
    def _create_langchain_tools(self) -> List:
        """LangChain Tools 생성"""
        if not LANGCHAIN_AVAILABLE:
            self.logger.warning("⚠️ LangChain이 설치되지 않음. 기본 도구만 사용")
            return []
        
        tools = [
            Tool(
                name="get_current_datetime",
                description="현재 정확한 날짜와 시간을 가져옵니다. 할루시네이션 방지용.",
                func=self._get_current_datetime
            ),
            Tool(
                name="get_system_context", 
                description="시스템 상태와 데이터 범위 정보를 가져옵니다.",
                func=self._get_system_context
            ),
            Tool(
                name="search_vector_database",
                description="창고 데이터에서 관련 정보를 검색합니다. 상품, 입출고, 랙 정보 등.",
                func=self._search_vector_database
            ),
            Tool(
                name="calculate_warehouse_statistics",
                description="창고 통계를 계산합니다. 총 재고량, 입출고량 등. (통합 계산 기반)",
                func=self._calculate_warehouse_statistics
            ),
            Tool(
                name="validate_information",
                description="제공된 정보의 정확성을 검증합니다.",
                func=self._validate_information
            ),
            # 🆕 새로운 Tool들 추가
            Tool(
                name="get_rack_specific_info",
                description="특정 랙(A~Z)의 상세 정보를 조회합니다. 재고량, 활용률, 저장 상품 등.",
                func=self._get_rack_specific_info
            ),
            Tool(
                name="analyze_inventory_trends",
                description="재고 트렌드를 분석합니다. 입출고 패턴, 일별 변화 등.",
                func=self._analyze_inventory_trends
            ),
            Tool(
                name="get_low_stock_alerts",
                description="재고 부족 상품과 위험 상품을 분석합니다.",
                func=self._get_low_stock_alerts
            ),
            Tool(
                name="calculate_rack_utilization",
                description="랙별 활용률과 전체 창고 효율성을 계산합니다.",
                func=self._calculate_rack_utilization
            ),
            Tool(
                name="get_date_specific_data",
                description="특정 날짜의 입출고 데이터를 분석합니다. (2025-01-01 ~ 2025-01-07)",
                func=self._get_date_specific_data
            ),
            # 🤖 ML Tools 추가
            Tool(
                name="ml_demand_prediction",
                description="수요 예측 및 트렌드 분석을 수행합니다. 미래 출고량, 판매 전망 등.",
                func=self._tool_ml_prediction
            ),
            Tool(
                name="ml_anomaly_detection",
                description="이상 패턴 및 위험 요소를 감지합니다. 비정상적인 입출고 패턴 등.",
                func=self._tool_ml_anomaly
            ),
            Tool(
                name="ml_product_clustering",
                description="상품 분류 및 클러스터 분석을 수행합니다. 유사한 상품 그룹화 등.",
                func=self._tool_ml_clustering
            )
        ]
        
        self.logger.info(f"✅ {len(tools)}개 LangChain Tools 생성 완료")
        return tools
    
    def _get_current_datetime(self, query: str = "") -> str:
        """현재 정확한 날짜/시간 반환"""
        current = datetime.datetime.now()
        return f"""현재 날짜와 시간: {current.strftime('%Y년 %m월 %d일 %H시 %M분')}

⚠️ 중요 알림: 
- 현재 날짜: {current.strftime('%Y년 %m월 %d일')}
- 창고 데이터 범위: 2025년 1월 1일 ~ 2025년 1월 7일 (과거 데이터)
- 데이터는 과거 기록이므로 "현재"가 아님을 명시할 것"""
    
    def _get_system_context(self, query: str = "") -> str:
        """시스템 컨텍스트 반환"""
        context = self.system_context.copy()
        
        # 실시간 시스템 상태 업데이트
        if self.vector_db_service and hasattr(self.vector_db_service, 'is_initialized'):
            if self.vector_db_service.is_initialized:
                context["vector_db_status"] = "✅ 정상 작동"
            else:
                context["vector_db_status"] = "⚠️ 연결 불가"
        
        return json.dumps(context, ensure_ascii=False, indent=2)
    
    def _search_vector_database(self, query: str) -> str:
        """🔍 강화된 벡터 데이터베이스 검색 - AI 처리용 구조화된 결과"""
        if not self.vector_db_service:
            return "❌ 벡터 데이터베이스 서비스가 초기화되지 않음"
        
        try:
            # 동기 호출을 위한 래퍼
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    self.vector_db_service.search_relevant_data(query, n_results=20)  # 더 많은 결과
                )
            finally:
                loop.close()
            
            if result.get("success"):
                # 구조화된 검색 결과 생성
                enhanced_result = self._format_vector_search_result(result, query)
                return enhanced_result
            else:
                return f"❌ 벡터 검색 실패: {result.get('error', '알 수 없는 오류')}"
                
        except Exception as e:
            return f"❌ 벡터 검색 오류: {str(e)}"
    
    def _format_vector_search_result(self, result: Dict[str, Any], query: str) -> str:
        """벡터 검색 결과를 AI 처리용으로 구조화"""
        docs = result.get("documents", [])
        found = result.get("found_documents", 0)
        metadata = result.get("metadata_summary", {})
        chart_data = result.get("chart_data", {})
        
        formatted_result = []
        
        # 🔍 검색 요약
        formatted_result.append(f"🔍 **벡터 검색 결과 (질의: {query})**")
        formatted_result.append(f"- 총 검색된 문서: {found}개 (2,900개 중)")
        formatted_result.append(f"- 관련도: {'높음' if found >= 10 else '보통' if found >= 5 else '낮음'}")
        formatted_result.append("")
        
        # 📊 핵심 문서 내용 (상위 5개)
        if docs:
            formatted_result.append("📊 **핵심 관련 문서:**")
            for i, doc in enumerate(docs[:5], 1):
                # 문서 내용을 AI가 이해하기 쉽게 정리
                cleaned_doc = doc.strip()
                if len(cleaned_doc) > 300:
                    cleaned_doc = cleaned_doc[:300] + "..."
                formatted_result.append(f"{i}. {cleaned_doc}")
            formatted_result.append("")
        
        # 📈 메타데이터 정보
        if metadata:
            formatted_result.append("📈 **데이터 메타정보:**")
            for key, value in metadata.items():
                if key in ['total_records', 'date_range', 'data_types', 'quantity_stats']:
                    formatted_result.append(f"- {key}: {value}")
            formatted_result.append("")
        
        # 📊 차트 데이터 (집계 결과)
        if chart_data:
            formatted_result.append("📊 **집계 데이터:**")
            if 'title' in chart_data:
                formatted_result.append(f"- 제목: {chart_data['title']}")
            if 'data' in chart_data and 'labels' in chart_data:
                formatted_result.append(f"- 데이터: {dict(zip(chart_data.get('labels', []), chart_data.get('data', [])))}")
            formatted_result.append("")
        
        # 🎯 AI 처리 가이드
        formatted_result.append("🎯 **AI 처리 지침:**")
        formatted_result.append("- 위 검색 결과를 바탕으로 구체적이고 상세한 답변 생성")
        formatted_result.append("- 회사명, 상품명, 수량 등 구체적 정보 활용")
        formatted_result.append("- 데이터는 2025년 1월 1일~7일 과거 기록임을 명시")
        formatted_result.append("- 현재 날짜와 구분하여 답변")
        
        return "\n".join(formatted_result)
    
    def _calculate_warehouse_statistics(self, query: str) -> str:
        """창고 통계 계산 - 통합 계산 기반으로 개선"""
        if not self.data_service:
            return "❌ 데이터 서비스가 초기화되지 않음"
        
        try:
            # 🔄 통합 계산 메서드 사용
            if hasattr(self.data_service, 'get_unified_inventory_stats'):
                unified_stats = self.data_service.get_unified_inventory_stats()
                
                if "error" not in unified_stats:
                    return f"""📊 창고 통계 (통합 계산 기반, 2025년 1월 1일-7일):
- 총 재고량: {unified_stats.get('total_inventory', 0):,}개
- 상품 종류: {unified_stats.get('total_products', 0)}개
- 총 입고량: {unified_stats.get('total_inbound_qty', 0):,}개
- 총 출고량: {unified_stats.get('total_outbound_qty', 0):,}개
- 일평균 입고: {unified_stats.get('daily_inbound_avg', 0):,}개
- 일평균 출고: {unified_stats.get('daily_outbound_avg', 0):,}개
- 활성 랙 수: {len(unified_stats.get('rack_distribution', {})):,}개
- 계산 방식: {unified_stats.get('calculation_method', 'unknown')}

⚠️ 주의: 이 데이터는 과거 7일간의 기록이며, 모든 시스템에서 동일한 수치를 제공합니다."""
            
            # Fallback: 기존 방식
            stats = {}
            
            # 총 재고량
            if hasattr(self.data_service, 'product_master') and self.data_service.product_master is not None:
                if '현재고' in self.data_service.product_master.columns:
                    stats['total_inventory'] = int(self.data_service.product_master['현재고'].sum())
                    stats['product_count'] = len(self.data_service.product_master)
            
            # 입고량
            if hasattr(self.data_service, 'inbound_data') and self.data_service.inbound_data is not None:
                if 'PalleteQty' in self.data_service.inbound_data.columns:
                    stats['total_inbound'] = int(self.data_service.inbound_data['PalleteQty'].sum())
                    stats['inbound_records'] = len(self.data_service.inbound_data)
            
            # 출고량
            if hasattr(self.data_service, 'outbound_data') and self.data_service.outbound_data is not None:
                if 'PalleteQty' in self.data_service.outbound_data.columns:
                    stats['total_outbound'] = int(self.data_service.outbound_data['PalleteQty'].sum())
                    stats['outbound_records'] = len(self.data_service.outbound_data)
            
            return f"""📊 창고 통계 (레거시 계산, 2025년 1월 1일-7일):
- 총 재고량: {stats.get('total_inventory', 0):,}개
- 상품 종류: {stats.get('product_count', 0)}개
- 총 입고량: {stats.get('total_inbound', 0):,}개 ({stats.get('inbound_records', 0)}건)
- 총 출고량: {stats.get('total_outbound', 0):,}개 ({stats.get('outbound_records', 0)}건)

⚠️ 주의: 이 데이터는 과거 7일간의 기록입니다. (레거시 계산 방식 사용)"""
            
        except Exception as e:
            return f"❌ 통계 계산 오류: {str(e)}"
    
    def _get_rack_specific_info(self, query: str) -> str:
        """🏢 특정 랙의 상세 정보 조회"""
        if not self.data_service or not hasattr(self.data_service, 'get_unified_inventory_stats'):
            return "❌ 데이터 서비스가 초기화되지 않음"
        
        try:
            # 쿼리에서 랙 이름 추출
            import re
            rack_match = re.search(r'([A-Za-z])랙?', query)
            if not rack_match:
                rack_match = re.search(r'rack[_\s]*([A-Za-z])', query, re.IGNORECASE)
            
            if not rack_match:
                return "❌ 랙 이름을 찾을 수 없습니다. 예: A랙, B랙, C랙"
            
            rack_letter = rack_match.group(1).upper()
            
            # 통합 계산에서 랙 정보 가져오기
            unified_stats = self.data_service.get_unified_inventory_stats()
            
            if "error" in unified_stats:
                return f"❌ 통합 계산 실패: {unified_stats['error']}"
            
            rack_distribution = unified_stats.get("rack_distribution", {})
            
            # 랙 이름 매칭
            target_rack = None
            for rack_name in rack_distribution.keys():
                if rack_letter in rack_name.upper():
                    target_rack = rack_name
                    break
            
            if not target_rack:
                return f"❌ {rack_letter}랙 정보를 찾을 수 없습니다.\n사용 가능한 랙: {list(rack_distribution.keys())}"
            
            current_stock = rack_distribution[target_rack]
            avg_capacity = 50  # 랙당 평균 용량
            utilization = (current_stock / avg_capacity) * 100
            
            status = "✅ 정상" if utilization < 80 else "⚠️ 주의" if utilization < 95 else "🚨 포화"
            
            return f"""🏢 {target_rack} 상세 정보:
- 현재 재고량: {int(current_stock):,}개
- 최대 용량: {avg_capacity}개
- 활용률: {utilization:.1f}%
- 상태: {status}
- 데이터 소스: 통합 계산 (일관성 보장)

⚠️ 주의: 2025년 1월 1일-7일 데이터 기준"""
            
        except Exception as e:
            return f"❌ 랙 정보 조회 오류: {str(e)}"
    
    def _analyze_inventory_trends(self, query: str) -> str:
        """📈 재고 트렌드 분석"""
        if not self.data_service:
            return "❌ 데이터 서비스가 초기화되지 않음"
        
        try:
            # 통합 계산 데이터 활용
            unified_stats = self.data_service.get_unified_inventory_stats()
            
            if "error" in unified_stats:
                return f"❌ 통합 계산 실패: {unified_stats['error']}"
            
            # 일별 트렌드 데이터 시도
            trend_data = None
            if hasattr(self.data_service, 'get_daily_trends_summary'):
                try:
                    trend_data = self.data_service.get_daily_trends_summary()
                except Exception as e:
                    self.logger.warning(f"일별 트렌드 조회 실패: {e}")
            
            total_inbound = unified_stats.get('total_inbound_qty', 0)
            total_outbound = unified_stats.get('total_outbound_qty', 0)
            daily_inbound = unified_stats.get('daily_inbound_avg', 0)
            daily_outbound = unified_stats.get('daily_outbound_avg', 0)
            
            # 트렌드 분석
            net_flow = total_inbound - total_outbound
            daily_net = daily_inbound - daily_outbound
            
            trend_direction = "📈 증가" if daily_net > 0 else "📉 감소" if daily_net < 0 else "➡️ 균형"
            
            return f"""📈 재고 트렌드 분석 (2025년 1월 1일-7일):

📊 **전체 흐름:**
- 총 입고량: {total_inbound:,}개
- 총 출고량: {total_outbound:,}개
- 순 증감: {net_flow:,}개

📅 **일별 평균:**
- 일평균 입고: {daily_inbound:,}개
- 일평균 출고: {daily_outbound:,}개
- 일평균 순증감: {daily_net:,}개

🎯 **트렌드 방향:** {trend_direction}

💡 **해석:**
- {"재고가 지속적으로 증가하는 추세" if daily_net > 0 else "재고가 지속적으로 감소하는 추세" if daily_net < 0 else "입출고가 균형을 이루고 있음"}

⚠️ 주의: 과거 7일간의 데이터 기반 분석"""
            
        except Exception as e:
            return f"❌ 트렌드 분석 오류: {str(e)}"
    
    def _get_low_stock_alerts(self, query: str) -> str:
        """⚠️ 재고 부족 경고 분석"""
        if not self.data_service:
            return "❌ 데이터 서비스가 초기화되지 않음"
        
        try:
            # 제품별 재고 데이터 분석
            if not hasattr(self.data_service, 'product_master') or self.data_service.product_master is None:
                return "❌ 상품 마스터 데이터가 없습니다"
            
            df = self.data_service.product_master
            stock_column = '현재고' if '현재고' in df.columns else 'Start Pallete Qty'
            
            if stock_column not in df.columns:
                return "❌ 재고 데이터를 찾을 수 없습니다"
            
            # 임계값 설정
            critical_threshold = 10  # 긴급 재고 부족
            warning_threshold = 20   # 주의 필요
            
            # 분류
            critical_products = df[df[stock_column] <= critical_threshold]
            warning_products = df[(df[stock_column] > critical_threshold) & (df[stock_column] <= warning_threshold)]
            
            result = f"""⚠️ 재고 부족 경고 분석:

🚨 **긴급 재고 부족** ({critical_threshold}개 이하):
- 대상 상품: {len(critical_products)}개"""
            
            if len(critical_products) > 0:
                for _, product in critical_products.head(5).iterrows():
                    product_name = product.get('ProductName', '이름 없음')
                    stock = product.get(stock_column, 0)
                    result += f"\n  • {product_name}: {int(stock)}개"
                
                if len(critical_products) > 5:
                    result += f"\n  • 외 {len(critical_products) - 5}개 상품"
            
            result += f"""

⚠️ **주의 재고** ({warning_threshold}개 이하):
- 대상 상품: {len(warning_products)}개"""
            
            if len(warning_products) > 0:
                for _, product in warning_products.head(3).iterrows():
                    product_name = product.get('ProductName', '이름 없음')
                    stock = product.get(stock_column, 0)
                    result += f"\n  • {product_name}: {int(stock)}개"
                
                if len(warning_products) > 3:
                    result += f"\n  • 외 {len(warning_products) - 3}개 상품"
            
            # 전체 요약
            total_products = len(df)
            at_risk_products = len(critical_products) + len(warning_products)
            risk_percentage = (at_risk_products / total_products) * 100 if total_products > 0 else 0
            
            result += f"""

📊 **전체 요약:**
- 전체 상품 수: {total_products}개
- 위험 상품 수: {at_risk_products}개 ({risk_percentage:.1f}%)
- 안전 상품 수: {total_products - at_risk_products}개

💡 **권장사항:**
- 긴급 재고 부족 상품은 즉시 발주 필요
- 주의 재고 상품은 1-2일 내 발주 검토

⚠️ 주의: 2025년 1월 데이터 기준"""
            
            return result
            
        except Exception as e:
            return f"❌ 재고 부족 분석 오류: {str(e)}"
    
    def _calculate_rack_utilization(self, query: str) -> str:
        """🏗️ 랙 활용률 계산"""
        if not self.data_service:
            return "❌ 데이터 서비스가 초기화되지 않음"
        
        try:
            # 통합 계산에서 랙 활용률 가져오기
            if hasattr(self.data_service, 'calculate_rack_utilization'):
                rack_util = self.data_service.calculate_rack_utilization()
                
                if not rack_util:
                    return "❌ 랙 활용률 데이터를 가져올 수 없습니다"
                
                result = "🏗️ 랙 활용률 분석:\n\n"
                
                # 활용률 순으로 정렬
                sorted_racks = sorted(rack_util.items(), key=lambda x: x[1].get('utilization_rate', 0), reverse=True)
                
                high_util_count = 0
                normal_util_count = 0
                low_util_count = 0
                
                for rack_name, rack_info in sorted_racks:
                    current_stock = rack_info.get('current_stock', 0)
                    max_capacity = rack_info.get('max_capacity', 50)
                    utilization_rate = rack_info.get('utilization_rate', 0)
                    
                    if utilization_rate >= 95:
                        status_icon = "🚨"
                        high_util_count += 1
                    elif utilization_rate >= 80:
                        status_icon = "⚠️"
                        normal_util_count += 1
                    else:
                        status_icon = "✅"
                        low_util_count += 1
                    
                    result += f"{status_icon} **{rack_name}**: {current_stock}개/{max_capacity}개 ({utilization_rate:.1f}%)\n"
                
                # 전체 요약
                total_racks = len(rack_util)
                avg_utilization = sum(r.get('utilization_rate', 0) for r in rack_util.values()) / total_racks if total_racks > 0 else 0
                
                result += f"""
📊 **전체 요약:**
- 총 랙 수: {total_racks}개
- 평균 활용률: {avg_utilization:.1f}%
- 포화 상태 (95%+): {high_util_count}개
- 주의 상태 (80-95%): {normal_util_count}개  
- 여유 상태 (80% 미만): {low_util_count}개

💡 **효율성 분석:**
- {"창고 공간이 효율적으로 활용되고 있음" if avg_utilization > 70 else "창고 공간 활용도가 낮음 - 재배치 검토 필요" if avg_utilization < 50 else "보통 수준의 활용률"}

⚠️ 주의: 통합 계산 기반 데이터"""
                
                return result
            else:
                return "❌ 랙 활용률 계산 기능이 없습니다"
                
        except Exception as e:
            return f"❌ 랙 활용률 계산 오류: {str(e)}"
    
    def _get_date_specific_data(self, query: str) -> str:
        """📅 특정 날짜 데이터 분석"""
        if not self.data_service:
            return "❌ 데이터 서비스가 초기화되지 않음"
        
        try:
            # 쿼리에서 날짜 추출
            import re
            date_patterns = [
                r'2025[.-]01[.-](\d{1,2})',
                r'1월\s*(\d{1,2})일?',
                r'(\d{1,2})일',
                r'01[.-](\d{1,2})'
            ]
            
            target_day = None
            for pattern in date_patterns:
                match = re.search(pattern, query)
                if match:
                    target_day = int(match.group(1))
                    break
            
            if not target_day or target_day < 1 or target_day > 7:
                return """❌ 유효한 날짜를 찾을 수 없습니다.

사용 가능한 날짜: 2025년 1월 1일 ~ 7일
예시: "1월 3일", "2025-01-05", "6일" 등"""
            
            target_date = f"2025-01-{target_day:02d}"
            display_date = f"2025년 1월 {target_day}일"
            
            result = f"📅 {display_date} 데이터 분석:\n\n"
            
            # 입고 데이터 분석
            inbound_count = 0
            inbound_qty = 0
            if hasattr(self.data_service, 'inbound_data') and self.data_service.inbound_data is not None:
                df = self.data_service.inbound_data
                if 'Date' in df.columns:
                    # 날짜 필터링
                    date_matches = df['Date'].astype(str).str.contains(f"2025.01.{target_day:02d}|2025-01-{target_day:02d}|01/{target_day:02d}/2025", na=False)
                    day_data = df[date_matches]
                    inbound_count = len(day_data)
                    if 'PalleteQty' in day_data.columns:
                        inbound_qty = day_data['PalleteQty'].sum()
            
            # 출고 데이터 분석
            outbound_count = 0
            outbound_qty = 0
            if hasattr(self.data_service, 'outbound_data') and self.data_service.outbound_data is not None:
                df = self.data_service.outbound_data
                if 'Date' in df.columns:
                    date_matches = df['Date'].astype(str).str.contains(f"2025.01.{target_day:02d}|2025-01-{target_day:02d}|01/{target_day:02d}/2025", na=False)
                    day_data = df[date_matches]
                    outbound_count = len(day_data)
                    if 'PalleteQty' in day_data.columns:
                        outbound_qty = day_data['PalleteQty'].sum()
            
            net_qty = inbound_qty - outbound_qty
            net_direction = "📈 증가" if net_qty > 0 else "📉 감소" if net_qty < 0 else "➡️ 균형"
            
            result += f"""📦 **입고 현황:**
- 입고 건수: {inbound_count}건
- 입고 수량: {int(inbound_qty):,}개

🚚 **출고 현황:**
- 출고 건수: {outbound_count}건
- 출고 수량: {int(outbound_qty):,}개

📊 **일일 요약:**
- 순 증감: {int(net_qty):,}개
- 트렌드: {net_direction}
- 총 거래: {inbound_count + outbound_count}건

💡 **분석:**
- {"활발한 입출고 활동" if (inbound_count + outbound_count) > 10 else "보통 수준의 활동" if (inbound_count + outbound_count) > 5 else "낮은 수준의 활동"}
- {"재고 증가일" if net_qty > 0 else "재고 감소일" if net_qty < 0 else "입출고 균형일"}

⚠️ 주의: {display_date} 과거 데이터 기준"""
            
            return result
            
        except Exception as e:
            return f"❌ 날짜별 데이터 분석 오류: {str(e)}"
    
    def _validate_information(self, information: str) -> str:
        """정보 검증"""
        validation_issues = []
        
        # 날짜 관련 할루시네이션 체크
        if "2025년 1월" in information and "현재" in information:
            validation_issues.append("⚠️ 2025년 1월 데이터를 '현재'라고 표현하면 안됨")
        
        # 확정적 표현 체크
        uncertain_patterns = ["확실히", "분명히", "틀림없이", "반드시"]
        for pattern in uncertain_patterns:
            if pattern in information:
                validation_issues.append(f"⚠️ 과도한 확신 표현 발견: '{pattern}'")
        
        # 숫자 정확성 체크 (기본적인 범위 검증)
        import re
        numbers = re.findall(r'(\d{1,3}(?:,\d{3})*)', information)
        large_numbers = [n for n in numbers if int(n.replace(',', '')) > 100000]
        if large_numbers:
            validation_issues.append(f"⚠️ 큰 숫자 검증 필요: {large_numbers}")
        
        if validation_issues:
            return f"🔍 검증 결과:\n" + "\n".join(validation_issues)
        else:
            return "✅ 검증 통과: 문제 없음"
    
    async def _classify_ml_intent(self, question: str) -> Dict[str, Any]:
        """🤖 AI 기반 ML 의도 분류"""
        try:
            classification_prompt = f"""질문을 4가지 중 하나로 분류:

1. PREDICTION: 예측, 수요, 미래, 전망
2. ANOMALY: 이상, 문제, 비정상
3. CLUSTERING: 분류, 그룹, 카테고리
4. DATA: 현재 조회, 목록

질문: {question}

JSON 형식으로만 답변:
{{"category": "분류결과", "confidence": 0.8}}"""
            
            # AI 서비스 호출
            self.logger.info(f"🤖 [ML_CLASSIFICATION] AI에게 분류 요청: '{question[:30]}...'")
            response = await self.ai_client.answer_simple_query(
                classification_prompt, 
                {"classification_task": True}
            )
            self.logger.info(f"🤖 [ML_CLASSIFICATION] AI 응답 원문: '{response[:100]}...'")  
            
            # JSON 파싱
            import json
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                
                # 신뢰도 검증
                confidence = result.get('confidence', 0.5)
                category = result.get('category', 'DATA')
                
                self.logger.info(f"🎯 [ML_CLASSIFICATION] {question[:30]}... → {category} (신뢰도: {confidence})")
                
                return {
                    "category": category,
                    "confidence": confidence,
                    "reasoning": result.get("reasoning", "AI 분류"),
                    "needs_ml": category in ["PREDICTION", "ANOMALY", "CLUSTERING"]
                }
            else:
                raise ValueError("JSON 파싱 실패")
                
        except Exception as e:
            self.logger.warning(f"⚠️ [ML_CLASSIFICATION] AI 분류 실패: {e}, fallback 사용")
            return self._fallback_keyword_classification(question)

    def _fallback_keyword_classification(self, question: str) -> Dict[str, Any]:
        """🔧 키워드 기반 fallback 분류 (강화된 버전)"""
        question_lower = question.lower()
        
        # 예측 관련 키워드
        prediction_keywords = [
            '예측', '예상', '미래', '내일', '다음', '수요', '전망', '트렌드',
            '늘어날', '증가', '감소', '변화', '어떨까', '될까', '예측해'
        ]
        
        # 이상 탐지 키워드  
        anomaly_keywords = [
            '이상', '문제', '비정상', '위험', '오류', '잘못', '이슈',
            '패턴', '문제가', '위험한', '비정상적', '이상한'
        ]
        
        # 클러스터링 키워드
        clustering_keywords = [
            '분류', '그룹', '카테고리', '비슷', '유사', '묶어', '분석',
            '클러스터', '그룹핑', '카테고리별', '분류해'
        ]
        
        # 키워드 매칭 점수 계산
        prediction_score = sum(1 for kw in prediction_keywords if kw in question_lower)
        anomaly_score = sum(1 for kw in anomaly_keywords if kw in question_lower)
        clustering_score = sum(1 for kw in clustering_keywords if kw in question_lower)
        
        # 최고 점수 결정
        scores = {
            'PREDICTION': prediction_score,
            'ANOMALY': anomaly_score, 
            'CLUSTERING': clustering_score
        }
        
        max_category = max(scores, key=scores.get)
        max_score = scores[max_category]
        
        if max_score > 0:
            confidence = min(0.8, 0.5 + (max_score * 0.1))  # 최대 0.8
            self.logger.info(f"🔧 [FALLBACK] {question[:30]}... → {max_category} (키워드 {max_score}개)")
            return {
                "category": max_category,
                "confidence": confidence,
                "reasoning": f"키워드 매칭: {max_score}개",
                "needs_ml": True
            }
        else:
            # 일반 데이터 조회로 분류
            return {
                "category": "DATA",
                "confidence": 0.3,
                "reasoning": "키워드 매칭 없음",
                "needs_ml": False
            }

    async def determine_optimal_mode(self, question: str) -> RAGMode:
        """🎯 질문에 최적화된 처리 모드 결정 (AI 기반 ML 분류 통합)"""
        
        self.logger.info(f"📊 [MODE_DECISION] 모드 결정 시작: '{question[:50]}...'")
        
        # 🚀 AI 기반 ML 분류 먼저 시도
        ml_classification = await self._classify_ml_intent(question)
        
        self.logger.info(f"🤖 [MODE_DECISION] ML 분류 결과: {ml_classification}")
        
        if ml_classification["needs_ml"] and ml_classification["confidence"] > 0.7:
            self.logger.info(f"✅ [MODE_DECISION] TOOL_ENHANCED 모드 선택: {ml_classification['category']} (신뢰도: {ml_classification['confidence']})")
            return RAGMode.TOOL_ENHANCED
        elif ml_classification["needs_ml"]:
            self.logger.info(f"⚠️ [MODE_DECISION] ML 필요하지만 신뢰도 낮음: {ml_classification['confidence']} < 0.7, 기존 로직 사용")
        
        # 기존 로직 (fallback)
        question_lower = question.lower()
        
        # 🚀 단순 통계 질문 - SIMPLE 모드
        simple_patterns = [
            "총 재고", "전체 재고", "총 입고", "총 출고",
            "몇 개", "얼마나", "총합", "전체 개수"
        ]
        
        # 🏢 랙 관련 질문 - TOOL_ENHANCED 모드
        rack_patterns = [
            "랙", "rack", "a랙", "b랙", "c랙", "활용률", "랙별"
        ]
        
        # 📅 날짜 관련 질문 - TOOL_ENHANCED 모드  
        date_patterns = [
            "1월", "날짜", "언제", "2025", "일별", "매일"
        ]
        
        # ⚠️ 재고 부족/위험 - TOOL_ENHANCED 모드
        alert_patterns = [
            "부족", "위험", "낮은", "적은", "경고", "부족한"
        ]
        
        # 📊 트렌드/분석 - TOOL_ENHANCED 모드
        analysis_patterns = [
            "분석", "트렌드", "경향", "패턴", "변화", "추세"
        ]
        
        # 🔍 복잡한 질문/비교 - SELF_RAG 모드
        complex_patterns = [
            "비교", "어떤 차이", "왜", "어떻게", "원인", "이유",
            "가장 좋은", "최적의", "추천", "제안"
        ]
        
        # 패턴 매칭으로 모드 결정
        if any(pattern in question_lower for pattern in simple_patterns):
            self.logger.info(f"🎯 [MODE_DECISION] SIMPLE 모드 선택: 단순 통계 질문")
            return RAGMode.SIMPLE
        
        elif any(pattern in question_lower for pattern in (rack_patterns + date_patterns + alert_patterns + analysis_patterns)):
            self.logger.info(f"🎯 [MODE_DECISION] TOOL_ENHANCED 모드 선택: 전문 도구 필요")
            return RAGMode.TOOL_ENHANCED
        
        elif any(pattern in question_lower for pattern in complex_patterns):
            self.logger.info(f"🎯 [MODE_DECISION] SELF_RAG 모드 선택: 복잡한 분석 필요")
            return RAGMode.SELF_RAG
        
        # 기본값: 질문 길이로 판단
        elif len(question.split()) > 10:
            self.logger.info(f"🎯 [MODE_DECISION] SELF_RAG 모드 선택: 긴 질문 (단어 수: {len(question.split())})")
            return RAGMode.SELF_RAG
        
        else:
            self.logger.info(f"🎯 [MODE_DECISION] TOOL_ENHANCED 모드 선택: 기본값")
            return RAGMode.TOOL_ENHANCED

    async def process_with_adaptive_mode(self, question: str) -> str:
        """🎯 적응형 모드로 질문 처리 (개선된 진입점)"""
        # 최적 모드 결정
        optimal_mode = self.determine_optimal_mode(question)
        
        self.logger.info(f"🧠 [ADAPTIVE] 적응형 처리 시작: '{question}'")
        self.logger.info(f"🎯 [ADAPTIVE] 선택된 모드: {optimal_mode.value}")
        
        if optimal_mode == RAGMode.SIMPLE:
            return await self.process_simple_query(question)
        elif optimal_mode == RAGMode.TOOL_ENHANCED:
            return await self.process_with_tools(question)
        else:
            return await self.process_with_self_rag(question, optimal_mode)
    
    async def process_simple_query(self, question: str) -> str:
        """⚡ 단순 질문 빠른 처리"""
        self.logger.info(f"⚡ [SIMPLE] 단순 질문 처리: '{question}'")
        
        try:
            # 직접 통계 계산으로 빠른 응답
            if "총 재고" in question.lower() or "전체 재고" in question.lower():
                stats = self._calculate_warehouse_statistics(question)
                return f"📊 **창고 통계 조회 결과:**\n\n{stats}"
            
            # 기본 벡터 검색
            if self.vector_db_service:
                result = await self.vector_db_service.search_relevant_data(question, n_results=5)
                if result.get("success") and result.get("documents"):
                    return f"📋 **간단 조회 결과:**\n{result['documents'][0]}"
            
            return "❌ 빠른 조회 결과를 찾을 수 없습니다."
            
        except Exception as e:
            self.logger.error(f"❌ [SIMPLE] 단순 처리 오류: {e}")
            return f"죄송합니다. 단순 조회 중 오류가 발생했습니다: {str(e)}"
    
    async def process_with_tools(self, question: str) -> str:
        """🔧 LangChain Tools 활용 처리"""
        self.logger.info(f"🔧 [TOOLS] 도구 기반 처리: '{question}'")
        
        try:
            # 적절한 도구 선택 및 실행
            if "랙" in question.lower():
                result = self._get_rack_specific_info(question)
                
            elif any(word in question.lower() for word in ["부족", "위험", "낮은"]):
                result = self._get_low_stock_alerts(question)
                
            elif any(word in question.lower() for word in ["트렌드", "분석", "패턴"]):
                result = self._analyze_inventory_trends(question)
                
            elif any(word in question.lower() for word in ["활용률", "효율"]):
                result = self._calculate_rack_utilization(question)
                
            elif any(word in question.lower() for word in ["1월", "날짜", "일별"]):
                result = self._get_date_specific_data(question)
                
            else:
                # 기본 통계 계산
                result = self._calculate_warehouse_statistics(question)
            
            return f"🔧 **전문 도구 분석 결과:**\n\n{result}"
            
        except Exception as e:
            self.logger.error(f"❌ [TOOLS] 도구 기반 처리 오류: {e}")
            return f"죄송합니다. 전문 도구 처리 중 오류가 발생했습니다: {str(e)}"

    async def process_with_self_rag(self, question: str, mode: RAGMode = RAGMode.SELF_RAG) -> str:
        """SELF-RAG 프로세스로 질문 처리 (기존 방식 유지)"""
        self.logger.info(f"🧠 [SELF_RAG] SELF-RAG 처리 시작: '{question}'")
        self.logger.info(f"🎯 [SELF_RAG] 처리 모드: {mode.value}")
        
        try:
            # 1단계: Retrieve (검색)
            self.logger.info("🔍 [SELF_RAG_STEP1] 문서 검색 단계")
            retrieval_result = await self._retrieve_documents(question)
            self.logger.info(f"📊 [SELF_RAG_RETRIEVE] 검색 결과: {retrieval_result.total_found}개 문서, 품질: {retrieval_result.search_quality:.2f}")
            
            # 2단계: Critique (비평/검증)
            self.logger.info("🔬 [SELF_RAG_STEP2] 검색 결과 검증 단계")
            critique_result = await self._critique_retrieval(question, retrieval_result)
            self.logger.info(f"📋 [SELF_RAG_CRITIQUE] 검증 결과 - 관련성: {critique_result.relevance_score:.2f}, 신뢰도: {critique_result.confidence_score:.2f}, 추가검색필요: {critique_result.needs_additional_search}")
            
            # 3단계: 추가 검색 필요성 판단
            if critique_result.needs_additional_search and retrieval_result.total_found > 0:
                self.logger.info("🔄 [SELF_RAG_STEP3] 추가 검색 필요 - 재시도")
                enhanced_query = await self._enhance_query(question, critique_result.missing_info)
                self.logger.info(f"📝 [SELF_RAG_ENHANCE] 강화된 쿼리: '{enhanced_query}'")
                retrieval_result = await self._retrieve_documents(enhanced_query)
                critique_result = await self._critique_retrieval(enhanced_query, retrieval_result)
                self.logger.info(f"📊 [SELF_RAG_RECHECK] 재검색 결과: {retrieval_result.total_found}개 문서, 신뢰도: {critique_result.confidence_score:.2f}")
            
            # 4단계: Generate (답변 생성)
            self.logger.info("💭 [SELF_RAG_STEP4] 답변 생성 단계")
            if critique_result.confidence_score >= self.critique_threshold:
                self.logger.info(f"✅ [SELF_RAG_GENERATE] 검증된 응답 생성 (신뢰도: {critique_result.confidence_score:.2f} >= {self.critique_threshold})")
                response = await self._generate_verified_response(question, retrieval_result, critique_result)
            else:
                self.logger.info(f"⚠️ [SELF_RAG_GENERATE] 주의 응답 생성 (신뢰도: {critique_result.confidence_score:.2f} < {self.critique_threshold})")
                response = await self._generate_cautious_response(question, retrieval_result, critique_result)
            
            # 5단계: Self-Reflect (자체 검증)
            self.logger.info("🔍 [SELF_RAG_STEP5] 자체 검증 단계")
            final_response = await self._self_reflect_response(question, response, retrieval_result)
            
            self.logger.info("✅ [SELF_RAG_SUCCESS] SELF-RAG 처리 완료")
            self.logger.info(f"🎯 [SELF_RAG_OUTPUT] 최종 응답: '{final_response[:200]}...'")
            return final_response
            
        except Exception as e:
            self.logger.error(f"❌ [SELF_RAG_ERROR] SELF-RAG 처리 실패: {e}")
            return f"죄송합니다. 고급 검증 처리 중 오류가 발생했습니다: {str(e)}"
    
    async def _retrieve_documents(self, query: str) -> RetrievalResult:
        """문서 검색 단계"""
        if not self.vector_db_service:
            return RetrievalResult([], [], {}, 0, 0.0)
        
        try:
            result = await self.vector_db_service.search_relevant_data(
                query=query,
                n_results=20  # SELF-RAG에서는 더 많은 문서 검색
            )
            
            if result.get("success"):
                documents = result.get("documents", [])
                scores = [0.8] * len(documents)  # 임시 점수
                metadata = result.get("metadata_summary", {})
                total_found = result.get("found_documents", 0)
                
                # 검색 품질 계산
                quality = min(1.0, total_found / 10.0) if total_found > 0 else 0.0
                
                return RetrievalResult(
                    documents=documents,
                    scores=scores,
                    metadata=metadata,
                    total_found=total_found,
                    search_quality=quality
                )
            else:
                return RetrievalResult([], [], {}, 0, 0.0)
                
        except Exception as e:
            self.logger.error(f"문서 검색 오류: {e}")
            return RetrievalResult([], [], {}, 0, 0.0)
    
    async def _critique_retrieval(self, query: str, retrieval: RetrievalResult) -> CritiqueResult:
        """검색 결과 비평/검증"""
        if not self.ai_client or retrieval.total_found == 0:
            return CritiqueResult(0.0, 0.0, ["검색 결과 없음"], 1.0, True)
        
        critique_prompt = f"""
다음 검색 결과가 질문에 얼마나 관련성이 있는지 평가해주세요.

**질문:** {query}

**검색된 문서 수:** {retrieval.total_found}개
**상위 3개 문서:**
{retrieval.documents[:3]}

**평가 기준:**
1. 관련성 (0.0~1.0): 문서들이 질문과 얼마나 관련있는가?
2. 신뢰도 (0.0~1.0): 정보가 얼마나 정확하고 완전한가?
3. 부족한 정보: 추가로 필요한 정보가 있는가?
4. 할루시네이션 위험도 (0.0~1.0): 잘못된 답변을 생성할 위험이 얼마나 되는가?

**응답 형식 (JSON):**
{{
    "relevance_score": 0.8,
    "confidence_score": 0.7,
    "missing_info": ["부족한 정보1", "부족한 정보2"],
    "hallucination_risk": 0.3,
    "needs_additional_search": true,
    "reasoning": "평가 이유"
}}
"""
        
        try:
            response = await self.ai_client.answer_simple_query(critique_prompt, {"critique_analysis": True})
            
            # JSON 파싱
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                critique_data = json.loads(json_match.group(0))
                
                return CritiqueResult(
                    relevance_score=critique_data.get("relevance_score", 0.5),
                    confidence_score=critique_data.get("confidence_score", 0.5),
                    missing_info=critique_data.get("missing_info", []),
                    hallucination_risk=critique_data.get("hallucination_risk", 0.5),
                    needs_additional_search=critique_data.get("needs_additional_search", False)
                )
            else:
                # Fallback: 단순 휴리스틱
                return self._simple_critique_fallback(query, retrieval)
                
        except Exception as e:
            self.logger.warning(f"비평 분석 실패, fallback 사용: {e}")
            return self._simple_critique_fallback(query, retrieval)
    
    def _simple_critique_fallback(self, query: str, retrieval: RetrievalResult) -> CritiqueResult:
        """간단한 휴리스틱 기반 비평"""
        # 기본적인 관련성 판단
        query_lower = query.lower()
        doc_text = " ".join(retrieval.documents[:5]).lower()
        
        # 키워드 매칭 기반 점수
        query_words = set(query_lower.split())
        doc_words = set(doc_text.split())
        overlap = len(query_words.intersection(doc_words))
        relevance = min(1.0, overlap / max(1, len(query_words)))
        
        # 신뢰도는 문서 수와 검색 품질 기반
        confidence = min(1.0, retrieval.search_quality * (retrieval.total_found / 10.0))
        
        # 할루시네이션 위험도
        hallucination_risk = 1.0 - confidence
        
        return CritiqueResult(
            relevance_score=relevance,
            confidence_score=confidence,
            missing_info=[] if relevance > 0.5 else ["더 구체적인 정보 필요"],
            hallucination_risk=hallucination_risk,
            needs_additional_search=relevance < 0.6
        )
    
    async def _enhance_query(self, original_query: str, missing_info: List[str]) -> str:
        """부족한 정보를 바탕으로 검색 쿼리 향상"""
        if not missing_info:
            return original_query
        
        enhanced_query = f"{original_query} {' '.join(missing_info)}"
        self.logger.info(f"🔍 쿼리 향상: {original_query} → {enhanced_query}")
        return enhanced_query
    
    async def _generate_verified_response(self, question: str, retrieval: RetrievalResult, critique: CritiqueResult) -> str:
        """검증된 고품질 응답 생성"""
        if not self.ai_client:
            return "AI 서비스가 사용할 수 없습니다."
        
        # 시스템 컨텍스트 강제 주입
        system_context = self._get_system_context()
        
        verified_prompt = f"""
당신은 창고 관리 전문 AI입니다. 검증된 정보만을 사용하여 정확한 답변을 제공하세요.

**시스템 컨텍스트 (필수 확인):**
{system_context}

**질문:** {question}

**검증된 검색 결과 (신뢰도: {critique.confidence_score:.2f}):**
{retrieval.documents[:5]}

**응답 규칙:**
1. 🕐 현재 날짜: {self.current_datetime.strftime('%Y년 %m월 %d일')} (반드시 명시)
2. 📅 데이터 범위: 2025년 1월 1일~7일 (과거 데이터임을 명시)
3. 🔍 검색된 {retrieval.total_found}개 문서 기반으로 답변
4. ✅ 확인된 사실만 제시, 추정은 명시적으로 구분
5. ⚠️ 데이터와 현재 날짜의 차이를 반드시 언급

**답변 예시:**
"데이터에 따르면 2025년 1월 5일(과거)에 Y랙에서는 ○○ 상품이 ●●개 출고되었습니다. 단, 이는 과거 데이터이며 현재 날짜({self.current_datetime.strftime('%Y년 %m월 %d일')})와는 다릅니다."

답변:"""
        
        try:
            response = await self.ai_client.answer_simple_query(verified_prompt, {"verified_generation": True})
            return response
        except Exception as e:
            return f"검증된 응답 생성 실패: {str(e)}"
    
    async def _generate_cautious_response(self, question: str, retrieval: RetrievalResult, critique: CritiqueResult) -> str:
        """신뢰도가 낮을 때 신중한 응답 생성"""
        cautious_response = f"""⚠️ **제한된 정보로 인한 부분 응답**

**현재 날짜:** {self.current_datetime.strftime('%Y년 %m월 %d일')}
**데이터 범위:** 2025년 1월 1일~7일 (과거 데이터)

검색된 정보가 불완전합니다 (신뢰도: {critique.confidence_score:.1f}/1.0).

**부족한 정보:**
{chr(10).join(f'• {info}' for info in critique.missing_info)}

**가능한 답변:**
검색된 {retrieval.total_found}개 문서에서 제한적인 정보를 확인했으나, 정확한 답변을 위해서는 추가 정보가 필요합니다.

💡 **권장 사항:**
1. 더 구체적인 질문으로 재시도
2. 대시보드 차트 확인
3. 시스템 관리자 문의

🔍 **대안:** "전체 재고량", "총 입고량" 같은 간단한 통계 질문을 시도해보세요."""
        
        return cautious_response
    
    async def _self_reflect_response(self, question: str, response: str, retrieval: RetrievalResult) -> str:
        """응답에 대한 자체 검증 및 최종 조정"""
        # 기본적인 자체 검증
        issues = []
        
        # 날짜 관련 할루시네이션 체크
        if "현재" in response and "2025년 1월" in response:
            if self.current_datetime.strftime('%Y년 %m월') != "2025년 01월":
                issues.append("날짜 혼동 위험 감지")
        
        # 과도한 확신 체크
        confident_words = ["확실히", "분명히", "틀림없이"]
        if any(word in response for word in confident_words):
            issues.append("과도한 확신 표현 감지")
        
        # 검증 정보 추가
        final_response = response
        
        # 자체 검증 메시지 제거 (사용자 요청에 따라 간소화)
        
        # 현재 시각 정보 제거 (사용자 요청에 따라 메타데이터 간소화)
        
        return final_response
    
    async def process_with_tools(self, question: str) -> str:
        """LangChain Tools를 활용한 처리"""
        if not LANGCHAIN_AVAILABLE:
            return await self.process_with_self_rag(question)
        
        self.logger.info(f"🔧 Tools 활용 처리: {question[:50]}...")
        
        try:
            # 간단한 Tool 체인 실행 (Agent 없이)
            results = []
            
            # 1. 시스템 컨텍스트 확인
            context = self._get_system_context()
            results.append(f"시스템 상태: {context}")
            
            # 2. 질문 유형에 따른 적절한 도구 선택
            if any(word in question.lower() for word in ['오늘', '현재', '지금', '몇월', '날짜']):
                datetime_info = self._get_current_datetime()
                results.append(f"날짜/시간 정보: {datetime_info}")
            
            if any(word in question.lower() for word in ['검색', '찾기', '어떤', '무엇', '누가']):
                search_result = self._search_vector_database(question)
                results.append(f"검색 결과: {search_result}")
            
            if any(word in question.lower() for word in ['총', '전체', '합계', '통계']):
                stats = self._calculate_warehouse_statistics(question)
                results.append(f"통계 정보: {stats}")
            
            # 3. AI로 최종 답변 생성
            if self.ai_client:
                tools_context = "\n\n".join(results)
                final_prompt = f"""
다음 도구들의 결과를 바탕으로 질문에 정확히 답변하세요:

**질문:** {question}

**도구 실행 결과:**
{tools_context}

**답변 규칙:**
1. 도구 결과의 정확한 정보만 사용
2. 현재 날짜와 데이터 범위 구분 명시
3. 간결하고 정확한 답변

답변:"""
                
                return await self.ai_client.answer_simple_query(final_prompt, {"tools_enhanced": True})
            else:
                return "\n\n".join(results)
                
        except Exception as e:
            self.logger.error(f"Tools 처리 실패: {e}")
            return f"도구 기반 처리 중 오류 발생: {str(e)}"
    
    async def smart_process_query(self, question: str) -> str:
        """🧠 하이브리드 접근법: Tools + 벡터 검색 + AI 통합 답변"""
        self.logger.info(f"🚀 [LANGCHAIN] 스마트 처리 시작: '{question}'")
        question_lower = question.lower()
        
        try:
            # 🚀 1단계: Tools로 기본 정보 수집 (항상 실행)
            self.logger.info("🔧 [LANGCHAIN_TOOLS] Tool 컨텍스트 수집 시작")
            tools_context = await self._collect_tools_context(question)
            self.logger.info(f"🔧 [LANGCHAIN_TOOLS] Tool 컨텍스트 수집 완료: {list(tools_context.keys()) if tools_context else 'None'}")
            
            # 🚀 2단계: 질문 유형에 따른 추가 처리 결정
            processing_mode = self._determine_processing_mode(question_lower)
            self.logger.info(f"🧠 [LANGCHAIN_MODE] 처리 모드 결정: {processing_mode}")
            
            if processing_mode == "datetime_only":
                # 단순 날짜/시간 질문 → Tools 결과만 반환
                self.logger.info("📅 [LANGCHAIN_DATETIME] 날짜/시간 전용 처리")
                raw_response = tools_context.get("datetime_info", "날짜 정보를 가져올 수 없습니다.")
                result = self._clean_response(raw_response, question, is_simple_question=True)
                self.logger.info(f"✅ [LANGCHAIN_SUCCESS] 날짜/시간 처리 완료: '{result[:100]}...'")
                return result
            
            elif processing_mode == "hybrid_enhanced":
                # 복합 질문 → Tools + 벡터 검색 + AI 통합
                self.logger.info("🔍 [LANGCHAIN_HYBRID] 하이브리드 강화 처리")
                result = await self._process_hybrid_enhanced(question, tools_context)
                self.logger.info(f"✅ [LANGCHAIN_SUCCESS] 하이브리드 처리 완료: '{result[:100]}...'")
                return result
            
            elif processing_mode == "simple_stats":
                # 간단한 통계 → Tools + 기본 AI
                self.logger.info("📊 [LANGCHAIN_STATS] 간단 통계 처리")
                raw_response = await self._process_simple_with_context(question, tools_context)
                result = self._clean_response(raw_response, question, is_simple_question=True)
                self.logger.info(f"✅ [LANGCHAIN_SUCCESS] 통계 처리 완료: '{result[:100]}...'")
                return result
            
            else:
                # 기본 하이브리드 처리
                self.logger.info("🔄 [LANGCHAIN_DEFAULT] 기본 하이브리드 처리")
                raw_response = await self._process_hybrid_enhanced(question, tools_context)
                result = self._clean_response(raw_response, question, is_simple_question=False)
                self.logger.info(f"✅ [LANGCHAIN_SUCCESS] 기본 처리 완료: '{result[:100]}...'")
                return result
                
        except Exception as e:
            self.logger.error(f"하이브리드 처리 실패: {e}")
            return f"처리 중 오류 발생: {str(e)}"
    
    def _determine_processing_mode(self, question_lower: str) -> str:
        """🔍 강화된 질문 유형 분석 - 처리 모드 결정"""
        
        # 🕐 1순위: 단순 날짜/시간 질문 (가장 간단)
        datetime_patterns = [
            r'오늘.*몇월', r'오늘.*몇일', r'현재.*몇월', r'현재.*몇일', 
            r'지금.*몇월', r'지금.*몇일', r'날짜.*몇월', r'날짜.*몇일',
            r'^오늘$', r'오늘.*날짜', r'현재.*날짜'
        ]
        
        import re
        if any(re.search(pattern, question_lower) for pattern in datetime_patterns):
            return "datetime_only"
        
        # 📊 2순위: 단순 통계 질문 (빠른 계산)
        simple_stats_patterns = [
            r'총.*재고량?$', r'전체.*재고$', r'총재고$',
            r'총.*입고량?$', r'총.*출고량?$', r'합계.*몇',
            r'전체.*몇.*개', r'총.*몇.*개'
        ]
        
        if any(re.search(pattern, question_lower) for pattern in simple_stats_patterns):
            return "simple_stats"
        
        # 🧠 3순위: 복잡한 분석 질문 판단
        analysis_indicators = [
            # 분석 키워드
            '비정상적', '분석', '비교', '트렌드', '패턴', '예측',
            '상위', '하위', '순위', '랭킹', '최고', '최저',
            
            # 상세 정보 요구
            '어떤', '무엇', '누가', '어디', '왜', '어떻게',
            '상태', '현황', '정보', '상황', '내역', '목록',
            
            # 비교/조건 질문
            '많은', '적은', '높은', '낮은', '차이', '비교',
            '~보다', '이상', '이하', '초과', '미만'
        ]
        
        complex_score = sum(1 for keyword in analysis_indicators if keyword in question_lower)
        
        # 복잡한 질문으로 판단되면 전체 분석 필요
        if complex_score >= 1:
            return "hybrid_enhanced"
        
        # 🔄 4순위: 기본값 (길이 기반 판단)
        if len(question_lower) <= 15:
            return "simple_stats"  # 짧은 질문은 간단히 처리
        else:
            return "hybrid_enhanced"  # 긴 질문은 상세 분석
    
    async def _collect_tools_context(self, question: str) -> Dict[str, Any]:
        """Tools로 기본 컨텍스트 정보 수집"""
        context = {}
        
        try:
            # 항상 시스템 컨텍스트 수집
            context["system_info"] = self._get_system_context()
            
            # 날짜/시간 관련 질문이면 현재 시간 정보 추가
            if any(word in question.lower() for word in ['오늘', '현재', '지금', '몇월', '몇일', '날짜', '시간']):
                context["datetime_info"] = self._get_current_datetime()
            
            # 통계 관련 질문이면 기본 통계 수집
            if any(word in question.lower() for word in ['총', '전체', '합계', '통계', '재고', '입고', '출고']):
                context["stats_info"] = self._calculate_warehouse_statistics(question)
            
            self.logger.info(f"✅ Tools 컨텍스트 수집 완료: {len(context)}개 항목")
            return context
            
        except Exception as e:
            self.logger.warning(f"Tools 컨텍스트 수집 실패: {e}")
            return {"error": str(e)}
    
    async def _process_hybrid_enhanced(self, question: str, tools_context: Dict[str, Any]) -> str:
        """하이브리드 강화 처리: Tools + 벡터 검색 + AI 통합"""
        try:
            # 🔍 벡터 검색으로 상세 데이터 수집
            vector_result = await self._enhanced_vector_search(question)
            
            # 🧠 모든 정보를 통합하여 AI 답변 생성
            raw_response = await self._generate_integrated_response(question, tools_context, vector_result)
            
            # 질문 복잡도에 따른 정제
            is_simple = self._is_simple_question_type(question)
            return self._clean_response(raw_response, question, is_simple_question=is_simple)
            
        except Exception as e:
            self.logger.error(f"하이브리드 강화 처리 실패: {e}")
            # Fallback: Tools 정보만으로 기본 답변
            raw_fallback = await self._process_simple_with_context(question, tools_context)
            return self._clean_response(raw_fallback, question, is_simple_question=True)
    
    async def _process_simple_with_context(self, question: str, tools_context: Dict[str, Any]) -> str:
        """간단한 처리: Tools 컨텍스트만으로 AI 답변"""
        if not self.ai_client:
            return self._format_tools_only_response(tools_context)
        
        try:
            # 질문 유형에 따른 경량 프롬프트 생성
            lightweight_prompt = self._create_lightweight_prompt(question, tools_context)
            
            response = await self.ai_client.answer_simple_query(lightweight_prompt, {"lightweight": True})
            return response
            
        except Exception as e:
            self.logger.error(f"간단한 컨텍스트 처리 실패: {e}")
            return self._format_tools_only_response(tools_context)
    
    async def _enhanced_vector_search(self, question: str) -> Dict[str, Any]:
        """강화된 벡터 검색 - 구조화된 결과 반환"""
        if not self.vector_db_service:
            return {"success": False, "error": "벡터 DB 서비스 없음"}
        
        try:
            # 기존 벡터 검색 호출
            result = await self.vector_db_service.search_relevant_data(
                query=question,
                n_results=15  # 상세 분석을 위해 충분한 문서 수집
            )
            
            if result.get("success"):
                # 검색 결과를 AI 처리용으로 구조화
                enhanced_result = {
                    "success": True,
                    "documents": result.get("documents", []),
                    "metadata": result.get("metadata_summary", {}),
                    "chart_data": result.get("chart_data", {}),
                    "found_count": result.get("found_documents", 0),
                    "search_query": question
                }
                
                self.logger.info(f"🔍 강화된 벡터 검색 성공: {enhanced_result['found_count']}개 문서")
                return enhanced_result
            else:
                return {"success": False, "error": result.get("error", "검색 실패")}
                
        except Exception as e:
            self.logger.error(f"강화된 벡터 검색 실패: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_integrated_response(self, question: str, tools_context: Dict[str, Any], vector_result: Dict[str, Any]) -> str:
        """모든 정보를 통합하여 완전한 AI 답변 생성"""
        if not self.ai_client:
            return self._format_integrated_fallback(tools_context, vector_result)
        
        try:
            # 통합 컨텍스트 구성
            integrated_context = self._build_integrated_context(tools_context, vector_result)
            
            integrated_prompt = f"""
당신은 창고 관리 전문 AI입니다. 다음의 모든 정보를 종합하여 질문에 정확하고 상세한 답변을 제공하세요.

**질문:** {question}

{integrated_context}

**답변 규칙:**
1. 🕐 현재 날짜: {self.current_datetime.strftime('%Y년 %m월 %d일')} (반드시 명시)
2. 📅 데이터 범위: 2025년 1월 1일~7일 (과거 데이터임을 명시)
3. 🔍 Tools 정보와 벡터 검색 결과를 모두 활용
4. ✅ 구체적인 수치, 회사명, 상품명 등 상세 정보 포함
5. ⚠️ 추정이나 불확실한 내용은 명시적으로 구분
6. 📊 정보 출처 명시 (검색된 문서 수, 도구 결과 등)

**답변 예시:**
"현재 날짜({self.current_datetime.strftime('%Y년 %m월 %d일')})와 과거 데이터(2025년 1월)를 구분하여 말씀드리면..."

답변:"""
            
            response = await self.ai_client.answer_simple_query(integrated_prompt, {"integrated_response": True})
            
            # 📊 조건부 출처 정보 추가 (복잡한 질문에만)
            if vector_result.get("success"):
                found_count = vector_result.get('found_count', 0)
                # 질문 복잡도에 따른 출처 정보 표시
                if self._should_show_source_info(question, found_count):
                    response += f"\n\n({found_count}개 데이터 기반)"
            
            return response
            
        except Exception as e:
            self.logger.error(f"통합 응답 생성 실패: {e}")
            return self._format_integrated_fallback(tools_context, vector_result)
    
    def _build_integrated_context(self, tools_context: Dict[str, Any], vector_result: Dict[str, Any]) -> str:
        """통합 컨텍스트 구성"""
        context_parts = []
        
        # Tools 정보 추가
        if tools_context:
            context_parts.append("== 도구 수집 정보 ==")
            
            if "datetime_info" in tools_context:
                context_parts.append(f"현재 시간 정보:\n{tools_context['datetime_info']}")
            
            if "stats_info" in tools_context:
                context_parts.append(f"통계 정보:\n{tools_context['stats_info']}")
            
            if "system_info" in tools_context:
                context_parts.append(f"시스템 정보:\n{tools_context['system_info']}")
        
        # 벡터 검색 결과 추가
        if vector_result.get("success"):
            context_parts.append("== 벡터 검색 결과 ==")
            context_parts.append(f"검색된 문서 수: {vector_result.get('found_count', 0)}개")
            
            documents = vector_result.get("documents", [])
            if documents:
                context_parts.append("주요 검색 문서:")
                for i, doc in enumerate(documents[:5], 1):
                    context_parts.append(f"{i}. {doc[:200]}...")
            
            metadata = vector_result.get("metadata", {})
            if metadata:
                context_parts.append(f"메타데이터: {metadata}")
            
            chart_data = vector_result.get("chart_data", {})
            if chart_data:
                context_parts.append(f"차트 데이터: {chart_data}")
        
        return "\n\n".join(context_parts)
    
    def _format_tools_context(self, tools_context: Dict[str, Any]) -> str:
        """Tools 컨텍스트 포맷팅"""
        formatted_parts = []
        
        for key, value in tools_context.items():
            if key == "error":
                formatted_parts.append(f"⚠️ 오류: {value}")
            elif key == "datetime_info":
                formatted_parts.append(f"📅 날짜/시간: {value}")
            elif key == "stats_info":
                formatted_parts.append(f"📊 통계: {value}")
            elif key == "system_info":
                formatted_parts.append(f"🔧 시스템: {value}")
            else:
                formatted_parts.append(f"{key}: {value}")
        
        return "\n".join(formatted_parts)
    
    def _format_tools_only_response(self, tools_context: Dict[str, Any]) -> str:
        """Tools 정보만으로 기본 응답 생성"""
        if not tools_context:
            return "수집된 정보가 없습니다."
        
        if "error" in tools_context:
            return f"정보 수집 중 오류 발생: {tools_context['error']}"
        
        response_parts = []
        
        if "datetime_info" in tools_context:
            response_parts.append(tools_context["datetime_info"])
        
        if "stats_info" in tools_context:
            response_parts.append(tools_context["stats_info"])
        
        if response_parts:
            return "\n\n".join(response_parts)
        else:
            return "요청하신 정보를 찾을 수 없습니다."
    
    def _format_integrated_fallback(self, tools_context: Dict[str, Any], vector_result: Dict[str, Any]) -> str:
        """통합 처리 실패 시 fallback 응답"""
        response_parts = []
        
        response_parts.append("⚠️ **AI 처리 실패 - 수집된 정보만 제공**")
        response_parts.append("")
        
        # Tools 정보
        if tools_context:
            response_parts.append("🔧 **도구 수집 정보:**")
            response_parts.append(self._format_tools_context(tools_context))
            response_parts.append("")
        
        # 벡터 검색 정보
        if vector_result.get("success"):
            response_parts.append("🔍 **벡터 검색 정보:**")
            response_parts.append(f"검색된 문서: {vector_result.get('found_count', 0)}개")
            
            documents = vector_result.get("documents", [])
            if documents:
                response_parts.append("주요 내용:")
                for i, doc in enumerate(documents[:3], 1):
                    response_parts.append(f"{i}. {doc[:150]}...")
        
        response_parts.append("")
        # 현재 시각 정보 제거 (사용자 요청)
        
        return "\n".join(response_parts)
    
    def _clean_response(self, response: str, question: str, is_simple_question: bool = False) -> str:
        """🧹 응답 후처리 - 깔끔한 답변으로 정제"""
        if not response:
            return response
        
        try:
            # 1단계: 불필요한 이모지 제거 (경고 이모지는 유지)
            cleaned = self._remove_unnecessary_emojis(response)
            
            # 2단계: 중복 정보 제거
            cleaned = self._remove_duplicate_info(cleaned)
            
            # 3단계: 질문 유형에 따른 특별 처리
            if is_simple_question:
                cleaned = self._simplify_for_basic_questions(cleaned, question)
            
            # 4단계: 기술적 정보 정리
            cleaned = self._clean_technical_info(cleaned, is_simple_question)
            
            # 5단계: 응답 템플릿 적용
            cleaned = self._apply_response_template(cleaned, question, is_complex=not is_simple_question)
            
            # 6단계: 최종 포맷팅
            cleaned = self._final_formatting(cleaned)
            
            self.logger.debug(f"응답 정제 완료: {len(response)} → {len(cleaned)} 문자")
            return cleaned
            
        except Exception as e:
            self.logger.warning(f"응답 정제 실패, 원본 반환: {e}")
            return response
    
    def _remove_unnecessary_emojis(self, text: str) -> str:
        """불필요한 장식용 이모지 제거 (경고 이모지는 유지)"""
        import re
        
        # 유지할 이모지 (경고, 주의사항 관련만)
        keep_emojis = ["⚠️", "❌", "✅"]
        
        # 제거할 장식용 이모지 패턴
        decorative_patterns = [
            r"🔍\s*\*?",  # 🔍 검색 아이콘
            r"📊\s*\*?",  # 📊 차트 아이콘
            r"🔧\s*\*?",  # 🔧 도구 아이콘
            r"🧠\s*\*?",  # 🧠 두뇌 아이콘
            r"🚀\s*\*?",  # 🚀 로켓 아이콘
            r"💡\s*\*?",  # 💡 전구 아이콘
            r"🎯\s*\*?",  # 🎯 타겟 아이콘
            r"📅\s*\*?",  # 📅 달력 아이콘
            r"🕐\s*\*?",  # 🕐 시계 아이콘
            r"🏢\s*\*?",  # 🏢 건물 아이콘
            r"📦\s*\*?",  # 📦 박스 아이콘
            r"📈\s*\*?",  # 📈 그래프 아이콘
            r"🔄\s*\*?",  # 🔄 순환 아이콘
        ]
        
        cleaned = text
        for pattern in decorative_patterns:
            cleaned = re.sub(pattern, "", cleaned)
        
        return cleaned
    
    def _remove_duplicate_info(self, text: str) -> str:
        """중복된 날짜/시간 정보 제거"""
        import re
        
        # 현재 날짜 중복 제거 (여러 번 언급된 경우)
        current_date_pattern = r"현재 날짜[:\s]*2025년\s*0?8월\s*0?3일"
        matches = re.findall(current_date_pattern, text)
        if len(matches) > 1:
            # 첫 번째 언급만 유지
            text = re.sub(current_date_pattern, "", text)
            text = f"현재 날짜: 2025년 8월 3일\n\n{text}"
        
        # 과도한 줄바꿈 정리
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def _simplify_for_basic_questions(self, text: str, question: str) -> str:
        """📝 간단한 질문에 대한 표준 응답 템플릿 적용"""
        question_lower = question.lower()
        import re
        
        # 🕐 날짜/시간 질문 템플릿
        if any(word in question_lower for word in ['오늘', '몇월', '몇일', '날짜', '현재']):
            # 날짜 정보 추출
            date_pattern = r"2025년\s*0?8월\s*0?3일"
            date_match = re.search(date_pattern, text)
            
            if date_match:
                clean_date = re.sub(r'\s+', ' ', date_match.group())
                return f"오늘은 {clean_date}입니다."
            else:
                # 현재 날짜 fallback
                current_date = self.current_datetime.strftime('%Y년 %m월 %d일')
                return f"오늘은 {current_date}입니다."
        
        # 📊 재고량 질문 템플릿
        if any(pattern in question_lower for pattern in ['총 재고량', '총재고', '전체 재고']):
            number_pattern = r"(\d{1,3}(?:,\d{3})*)\s*개"
            number_match = re.search(number_pattern, text)
            
            if number_match:
                return f"총 재고량은 {number_match.group(1)}개입니다."
        
        # 📦 입고량 질문 템플릿
        if any(pattern in question_lower for pattern in ['총 입고량', '입고량', '입고 현황']):
            number_pattern = r"(\d{1,3}(?:,\d{3})*)\s*개"
            number_match = re.search(number_pattern, text)
            
            if number_match:
                return f"총 입고량은 {number_match.group(1)}개입니다."
        
        # 🚚 출고량 질문 템플릿
        if any(pattern in question_lower for pattern in ['총 출고량', '출고량', '출고 현황']):
            number_pattern = r"(\d{1,3}(?:,\d{3})*)\s*개"
            number_match = re.search(number_pattern, text)
            
            if number_match:
                return f"총 출고량은 {number_match.group(1)}개입니다."
        
        # 🏢 랙 상태 질문 템플릿
        rack_patterns = ['a랙', 'b랙', 'c랙', 'd랙', 'e랙', 'f랙']
        matched_rack = None
        for rack in rack_patterns:
            if rack in question_lower:
                matched_rack = rack.upper()
                break
        
        if matched_rack and any(word in question_lower for word in ['상태', '현황', '어때']):
            # 랙 관련 숫자 정보 추출
            numbers = re.findall(r"(\d{1,3}(?:,\d{3})*)\s*개", text)
            if numbers:
                return f"{matched_rack}의 현재 재고는 {numbers[0]}개입니다."
        
        # 📈 상품 질문 템플릿 (가장 많이/적게 등)
        if any(word in question_lower for word in ['가장 많이', '최대', '가장 적게', '최소']) and '상품' in question_lower:
            # 상품명 추출 (간단한 패턴)
            product_patterns = [
                r"'([^']+)'",  # 따옴표로 둘러싸인 상품명
                r"「([^」]+)」",  # 일본식 괄호
                r"([가-힣]{2,}(?:콜라|나이프|국수|요구르트|스프라이트))",  # 일반적인 상품명 패턴
            ]
            
            for pattern in product_patterns:
                product_match = re.search(pattern, text)
                if product_match:
                    product_name = product_match.group(1)
                    # 상품명 정리 (긴 이름은 축약)
                    if len(product_name) > 15:
                        product_name = product_name[:12] + "..."
                    
                    # 수량 정보 추출
                    quantity_match = re.search(r"(\d+)\s*개", text)
                    if quantity_match:
                        return f"가장 많이 출고된 상품은 '{product_name}'입니다 ({quantity_match.group(1)}개)."
                    else:
                        return f"가장 많이 출고된 상품은 '{product_name}'입니다."
        
        return text
    
    def _clean_technical_info(self, text: str, is_simple_question: bool) -> str:
        """🔧 기술적 정보 조건부 표시 - 질문 복잡도에 따른 출처 정보 관리"""
        import re
        
        if is_simple_question:
            # 🚫 간단한 질문: 모든 기술적 정보 완전 제거
            technical_patterns = [
                # 출처 정보 패턴
                r"\*.*?개의?\s*(?:벡터\s*검색\s*결과|관련\s*데이터|문서).*?\*",
                r"\*.*?데이터.*?분석.*?결과.*?\*",
                r"\([0-9]+개\s*데이터\s*분석\)",
                
                # 기술적 용어 제거
                r"벡터\s*검색\s*결과",
                r"도구\s*정보를?\s*종합한?",
                r"강화된\s*fallback",
                r"고급\s*처리\s*시스템",
                r"SELF-RAG\s*처리",
                r"Tools?\s*정보",
                r"하이브리드\s*처리",
                
                # 시스템 상태 정보
                r"⚠️\s*\*?고급\s*처리.*?\*?",
                r"일시\s*불가.*?활용.*?",
                
                # 과도한 메타정보
                r"검색된\s*\d+개\s*문서",
                r"관련\s*문서.*?개",
                r"문서.*?분석.*?결과"
            ]
            
            for pattern in technical_patterns:
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)
                
            # 빈 줄과 공백 정리
            text = re.sub(r'\n\s*\n+', '\n\n', text)
            text = re.sub(r'\s+', ' ', text)
            
        else:
            # 🔍 복잡한 질문: 기술적 정보를 간소화하여 유지
            # 상세한 출처 정보 → 간단한 출처 정보로 변환
            text = re.sub(
                r"\*(\d+)개의?\s*(?:벡터\s*검색\s*결과|관련\s*데이터).*?종합한.*?\*", 
                r"(\1개 데이터 기반)", 
                text, flags=re.IGNORECASE
            )
            
            # 기술적 용어 간소화
            technical_replacements = {
                r"강화된\s*fallback으로": "분석을 통해",
                r"고급\s*처리\s*시스템\s*일시\s*불가": "시스템 제약으로",
                r"벡터\s*검색\s*결과와\s*도구\s*정보": "검색 정보",
                r"SELF-RAG\s*처리": "고급 분석",
                r"하이브리드\s*강화\s*처리": "통합 분석"
            }
            
            for pattern, replacement in technical_replacements.items():
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def _final_formatting(self, text: str) -> str:
        """최종 포맷팅"""
        import re
        
        # 과도한 공백 제거
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # 문장 끝 정리
        text = re.sub(r'\s*\.\s*$', '.', text)
        
        # 시작/끝 공백 제거
        text = text.strip()
        
        return text
    
    def _is_simple_question_type(self, question: str) -> bool:
        """질문이 간단한 유형인지 판단"""
        question_lower = question.lower()
        
        # 간단한 질문 패턴
        simple_patterns = [
            # 날짜/시간 관련
            ['오늘', '몇월'], ['오늘', '몇일'], ['현재', '날짜'], ['지금', '몇월'],
            
            # 단순 통계
            ['총', '재고량'], ['전체', '재고'], ['총재고'], 
            ['총', '입고량'], ['총', '출고량'],
            
            # 단순 수치 질문
            ['얼마', '개'], ['몇', '개'], ['수량']
        ]
        
        # 복잡한 질문 패턴 (분석, 비교, 상세 정보)
        complex_patterns = [
            '비정상적', '분석', '비교', '트렌드', '패턴', 
            '상위', '하위', '순위', '많은', '적은',
            '어떤', '무엇', '누가', '어디', '왜',
            '상태', '현황', '정보', '상황'
        ]
        
        # 간단한 패턴 체크
        for pattern_group in simple_patterns:
            if isinstance(pattern_group, list):
                if all(word in question_lower for word in pattern_group):
                    return True
            else:
                if pattern_group in question_lower:
                    return True
        
        # 복잡한 패턴이 있으면 복잡한 질문
        if any(word in question_lower for word in complex_patterns):
            return False
        
        # 기본적으로 간단한 질문으로 분류 (짧은 질문)
        return len(question) < 20
    
    def _create_lightweight_prompt(self, question: str, tools_context: Dict[str, Any]) -> str:
        """📝 질문 유형별 경량 프롬프트 생성"""
        question_lower = question.lower()
        
        # 🕐 날짜/시간 질문용 초경량 프롬프트
        if any(word in question_lower for word in ['오늘', '몇월', '몇일', '현재', '날짜']):
            current_date = self.current_datetime.strftime('%Y년 %m월 %d일')
            return f"""질문: {question}
답변: 오늘은 {current_date}입니다."""
        
        # 📊 단순 통계 질문용 경량 프롬프트
        if any(word in question_lower for word in ['총', '전체', '합계']) and any(word in question_lower for word in ['재고', '입고', '출고']):
            stats_info = tools_context.get("stats_info", "")
            return f"""질문: {question}
데이터: {stats_info}

간단히 답변하세요. 예: "총 재고량은 1,234개입니다."
답변:"""
        
        # 🔍 기본 경량 프롬프트 (복잡한 질문용)
        context_summary = self._format_tools_context_minimal(tools_context)
        return f"""질문: {question}
정보: {context_summary}

간결하고 정확하게 답변하세요. 불필요한 설명은 생략하세요.
답변:"""
    
    def _format_tools_context_minimal(self, tools_context: Dict[str, Any]) -> str:
        """Tools 컨텍스트를 최소한으로 포맷팅"""
        essential_parts = []
        
        # 날짜 정보 (필수)
        current_date = self.current_datetime.strftime('%Y년 %m월 %d일')
        essential_parts.append(f"현재: {current_date}")
        essential_parts.append("데이터: 2025년 1월 1일~7일 (과거)")
        
        # 통계 정보 (있으면 포함)
        if "stats_info" in tools_context:
            stats = tools_context["stats_info"]
            # 핵심 숫자만 추출
            import re
            numbers = re.findall(r'(\d{1,3}(?:,\d{3})*)\s*개', stats)
            if numbers:
                essential_parts.append(f"주요 수치: {', '.join(numbers[:3])}개")
        
        return " | ".join(essential_parts)
    
    def _should_show_source_info(self, question: str, found_count: int) -> bool:
        """📋 출처 정보 표시 여부 결정"""
        question_lower = question.lower()
        
        # 🚫 간단한 질문에서는 출처 정보 숨김
        simple_question_indicators = [
            # 날짜/시간 질문
            '오늘', '몇월', '몇일', '현재', '날짜', '시간',
            
            # 단순 통계
            '총재고', '전체재고', '총입고', '총출고',
            
            # 단순 수치
            '얼마', '몇개', '수량'
        ]
        
        # 간단한 질문으로 판단되면 출처 정보 숨김
        if any(indicator in question_lower for indicator in simple_question_indicators):
            return False
        
        # 🔍 복잡한 분석 질문에서는 출처 정보 표시
        complex_question_indicators = [
            # 분석 키워드
            '분석', '비교', '트렌드', '패턴', '예측',
            '상위', '하위', '순위', '랭킹',
            
            # 상세 정보 요구
            '어떤', '무엇', '누가', '어디', '왜',
            '상태', '현황', '정보', '상황',
            
            # 비교/조건
            '많은', '적은', '비정상적', '특별한'
        ]
        
        has_complex_indicators = any(indicator in question_lower for indicator in complex_question_indicators)
        
        # 복잡한 질문이고 충분한 데이터가 있으면 출처 정보 표시
        if has_complex_indicators and found_count >= 5:
            return True
        
        # 매우 많은 데이터를 사용한 경우 (10개 이상) 출처 정보 표시
        if found_count >= 10:
            return True
        
        # 기본적으로 출처 정보 숨김 (깔끔한 답변)
        return False
    
    def _apply_response_template(self, text: str, question: str, is_complex: bool) -> str:
        """📋 질문 유형별 응답 템플릿 적용"""
        if not text or not text.strip():
            return text
        
        question_lower = question.lower()
        
        # 복잡한 질문에 대한 템플릿
        if is_complex:
            return self._apply_complex_template(text, question_lower)
        else:
            # 간단한 질문은 이미 _simplify_for_basic_questions에서 처리됨
            return text
    
    def _apply_complex_template(self, text: str, question_lower: str) -> str:
        """🔍 복잡한 질문에 대한 표준 템플릿"""
        import re
        
        # 분석 결과 형식 표준화
        if any(word in question_lower for word in ['분석', '비교', '트렌드']):
            # 분석 결과 문장 정리
            text = re.sub(r'^데이터에\s*따르면[,\s]*', '', text)
            text = re.sub(r'^검색.*?결과[,\s]*', '', text)
            
            # 분석 결과로 시작하도록 조정
            if not text.startswith('분석'):
                text = f"분석 결과, {text}"
        
        # 상위/순위 질문 형식 표준화
        elif any(word in question_lower for word in ['상위', '순위', '랭킹', '많이', '적게']):
            # 순위 정보 정리
            text = re.sub(r'가장\s*많이.*?상품은', '1위는', text)
            text = re.sub(r'(\d+)번째.*?많이', r'\1위로', text)
        
        # 상태/현황 질문 형식 표준화
        elif any(word in question_lower for word in ['상태', '현황', '어떤']):
            # 현황 보고 형식으로 조정
            if not any(text.startswith(prefix) for prefix in ['현재', '상태', '현황']):
                text = f"현재 상황: {text}"
        
        # 과도한 접속사/부사 제거
        text = re.sub(r'그러나\s*또한\s*', '', text)
        text = re.sub(r'따라서\s*그리고\s*', '', text)
        text = re.sub(r'또한\s*더불어\s*', '', text)
        
        return text.strip()
    
    # ==================== ML Tools 구현 ====================
    
    def _tool_ml_prediction(self, query: str) -> str:
        """🔮 수요 예측 도구"""
        if not self.ml_models.get('demand_predictor'):
            return "🔮 수요 예측 모델이 준비되지 않았습니다. 모델을 먼저 학습해주세요."
        
        try:
            self.logger.info(f"🔮 [ML_PREDICTION] 수요 예측 시작: {query[:50]}...")
            
            # TODO: 실제 ML 모델 호출 로직 구현
            # 현재는 개발 중 메시지 반환
            return f"""🔮 **수요 예측 결과:**

📊 **질문:** {query}

📈 **예측 분석:**
• 현재 수요 예측 모델이 개발 중입니다
• 향후 업데이트에서 실제 예측 기능을 제공할 예정입니다

⚠️ **현재 상태:** 개발 중인 기능입니다. 기본 데이터 분석은 다른 질문으로 문의해주세요."""
            
        except Exception as e:
            self.logger.error(f"❌ [ML_PREDICTION] 수요 예측 오류: {e}")
            return f"🔮 수요 예측 중 오류가 발생했습니다: {e}"
    
    def _tool_ml_anomaly(self, query: str) -> str:
        """⚠️ 이상 탐지 도구"""
        if not self.ml_models.get('anomaly_detector'):
            return "⚠️ 이상 탐지 모델이 준비되지 않았습니다. 모델을 먼저 학습해주세요."
        
        try:
            self.logger.info(f"⚠️ [ML_ANOMALY] 이상 탐지 시작: {query[:50]}...")
            
            # TODO: 실제 ML 모델 호출 로직 구현
            # 현재는 개발 중 메시지 반환
            return f"""⚠️ **이상 탐지 결과:**

📊 **질문:** {query}

🔍 **이상 패턴 분석:**
• 현재 이상 탐지 모델이 개발 중입니다
• 향후 업데이트에서 실제 이상 탐지 기능을 제공할 예정입니다

⚠️ **현재 상태:** 개발 중인 기능입니다. 기본 데이터 분석은 다른 질문으로 문의해주세요."""
            
        except Exception as e:
            self.logger.error(f"❌ [ML_ANOMALY] 이상 탐지 오류: {e}")
            return f"⚠️ 이상 탐지 중 오류가 발생했습니다: {e}"
    
    def _tool_ml_clustering(self, query: str) -> str:
        """🎯 클러스터링 도구"""
        if not self.ml_models.get('product_clusterer'):
            return "🎯 클러스터링 모델이 준비되지 않았습니다. 모델을 먼저 학습해주세요."
        
        try:
            self.logger.info(f"🎯 [ML_CLUSTERING] 클러스터링 시작: {query[:50]}...")
            
            # TODO: 실제 ML 모델 호출 로직 구현
            # 현재는 개발 중 메시지 반환
            return f"""🎯 **클러스터링 결과:**

📊 **질문:** {query}

🔗 **상품 분류 분석:**
• 현재 클러스터링 모델이 개발 중입니다
• 향후 업데이트에서 실제 상품 그룹화 기능을 제공할 예정입니다

⚠️ **현재 상태:** 개발 중인 기능입니다. 기본 데이터 분석은 다른 질문으로 문의해주세요."""
            
        except Exception as e:
            self.logger.error(f"❌ [ML_CLUSTERING] 클러스터링 오류: {e}")
            return f"🎯 클러스터링 중 오류가 발생했습니다: {e}"