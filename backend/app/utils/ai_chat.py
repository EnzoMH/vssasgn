from ..services.ai_service import WarehouseAI
from ..services.data_service import DataService
from ..services.langchain_service import LangChainRAGService
import logging
import asyncio
from typing import Dict, Any, Optional

class WarehouseChatbot:
    def __init__(self, data_service=None, vector_db_service=None):
        self.data_service = data_service or DataService()
        self.vector_db_service = vector_db_service
        self.llm_client = WarehouseAI() # WarehouseAI 인스턴스 사용
        self.logger = logging.getLogger(__name__)
        
        # 🚀 LangChain SELF-RAG 서비스 초기화
        self.langchain_service = LangChainRAGService(
            vector_db_service=self.vector_db_service,
            ai_client=self.llm_client,
            data_service=self.data_service
        )
        
        # 처리 체인 설정 (SELF-RAG 추가)
        self.processing_chains = {
            "direct": self._handle_direct_query,
            "vector_search": self._handle_vector_search_query, 
            "self_rag": self._handle_self_rag_query,  # 새로 추가
            "general": self._handle_general_query
        }

    def analyze_intent(self, question: str):
        # 질문에서 의도 분석 (예: "재고", "출고량", "예측")
        if "재고" in question:
            return "inventory"
        elif "출고량" in question:
            return "outbound"
        elif "예상" in question or "예측" in question:
            return "prediction"
        else:
            return "general"

    async def process_query(self, question: str) -> str:
        """
        🧠 SELF-RAG + LangChain Tools 기반 고급 질의 처리
        1. SELF-RAG (할루시네이션 방지 + 자체 검증)
        2. Direct Answer (간단한 계산)
        3. Fallback Vector Search (기존 방식)
        4. General LLM (최후 수단)
        """
        try:
            self.logger.info(f"🧠 SELF-RAG 질의 처리 시작: {question[:50]}...")
            
            # 🚀 1단계: SELF-RAG 스마트 처리 (할루시네이션 방지)
            try:
                self.logger.info("🔬 SELF-RAG 스마트 처리 시도")
                self_rag_result = await self.langchain_service.smart_process_query(question)
                if self_rag_result and not self_rag_result.startswith("오류"):
                    self.logger.info("✅ SELF-RAG 처리 성공")
                    return self_rag_result
            except Exception as e:
                self.logger.warning(f"⚠️ SELF-RAG 처리 실패, fallback 사용: {e}")
            
            # 2단계: 직접 답변 가능한 간단한 질문 체크
            direct_result = await self._handle_direct_query(question)
            if direct_result:
                self.logger.info("📊 직접 답변으로 처리 완료")
                return direct_result
            
            # 3단계: 기존 벡터 검색 방식 (fallback)
            if self._requires_immediate_vector_search(question) or self._is_data_inquiry(question):
                self.logger.info("🔍 기존 벡터 검색 방식 사용")
                vector_result = await self._handle_vector_search_query(question)
                if vector_result:
                    return vector_result
            
            # 4단계: 최후의 일반 LLM 처리
            self.logger.info("💬 일반 LLM 체인으로 처리")
            return await self._handle_general_query(question)
            
        except Exception as e:
            self.logger.error(f"❌ 질의 처리 오류: {e}")
            return f"죄송합니다. 질문을 처리하는 중 오류가 발생했습니다: {str(e)}"
    
    def _requires_immediate_vector_search(self, question: str) -> bool:
        """즉시 벡터 검색이 필요한 패턴 감지"""
        question_lower = question.lower()
        
        # 특정 위치/객체의 상태/정보를 묻는 패턴
        import re
        immediate_patterns = [
            # 랙 관련
            r"a랙", r"b랙", r"c랙", r"d랙", r"e랙", r"f랙", 
            r"랙.*상태", r"랙.*어때", r"랙.*정보", r"랙.*현황",
            r"랙에.*뭐", r"랙에.*어떤", r"랙에.*무엇",
            
            # 상품 관련
            r"어떤.*상품", r"무슨.*상품", r"뭔.*상품",
            r"상품.*목록", r"상품.*리스트", r"상품.*현황",
            
            # 업체 관련  
            r"어떤.*업체", r"어떤.*공급", r"어떤.*고객",
            r"주요.*공급", r"주요.*업체", r"주요.*고객",
            
            # 상태/현황 질문
            r"상태.*어때", r"현황.*어때", r"어떻게.*되", 
            r"상황.*어때", r"상태.*뭐", r"현황.*뭐"
        ]
        
        for pattern in immediate_patterns:
            if re.search(pattern, question_lower):
                self.logger.info(f"즉시 벡터 검색 패턴 매칭: {pattern}")
                return True
        return False
    
    def _is_data_inquiry(self, question: str) -> bool:
        """데이터 조회성 질문인지 판단 (단순 계산 제외)"""
        question_lower = question.lower()
        
        # 데이터 조회 키워드
        inquiry_keywords = [
            "어떤", "무엇", "뭐", "누가", "어디", "언제",
            "목록", "리스트", "현황", "상태", "정보", "상황",
            "분석", "통계", "트렌드", "패턴", "비교", "조회"
        ]
        
        # 단순 계산 키워드 (벡터 검색 불필요)
        import re
        simple_calc_patterns = [
            r"총.*얼마", r"전체.*얼마", r"합계.*얼마",
            r"총.*개수", r"전체.*개수", r"합계.*개수",
            r"총.*재고량", r"전체.*재고량"
        ]
        
        # 단순 계산이면 벡터 검색 불필요
        for pattern in simple_calc_patterns:
            if re.search(pattern, question_lower):
                self.logger.info(f"단순 계산 패턴으로 벡터 검색 제외: {pattern}")
                return False
        
        # 데이터 조회성 질문이면 벡터 검색 필요
        has_inquiry = any(keyword in question_lower for keyword in inquiry_keywords)
        if has_inquiry:
            self.logger.info("데이터 조회성 질문으로 벡터 검색 필요")
        return has_inquiry
    
    async def _needs_vector_search(self, question: str) -> bool:
        """CoT를 통한 의미론적 분석으로 VectorDB 검색 필요성 판단"""
        try:
            # 1단계: 기본 키워드 필터링 (성능 최적화)
            basic_keywords = [
                "어떤", "어디", "누가", "언제", "얼마", "몇", "얼마나", "무엇", "뭐", "뭔가",
                "리스트", "목록", "현황", "상태", "통계", "조회", "검색", "분석", "주요",
                "supplier", "공급업체", "공급사", "고객사", "업체", "회사", "기업", 
                "product", "상품", "제품", "품목", "랙", "rack", "재고", "수량", "a랙", "b랙"
            ]
            
            question_lower = question.lower()
            has_basic_keywords = any(keyword in question_lower for keyword in basic_keywords)
            
            if not has_basic_keywords:
                return False
            
            # 2단계: 간단한 패턴 기반 사전 필터링
            simple_calc_patterns = ["총 재고량", "총재고", "전체 재고량", "현재 재고량이 얼마"]
            if any(pattern in question_lower for pattern in simple_calc_patterns):
                self.logger.info("사전 필터링: 간단한 계산 질문으로 판단")
                return False
            
            # 벡터 검색 필수 패턴
            vector_required_patterns = ["어떤 상품", "어떤 업체", "주요 공급", "주요 상품", "a랙", "b랙", "랙에"]
            if any(pattern in question_lower for pattern in vector_required_patterns):
                self.logger.info("사전 필터링: 벡터 검색 필수 질문으로 판단")
                return True
            
            # 3단계: CoT 기반 의미론적 분석 (복잡한 케이스만)
            cot_analysis = await self._analyze_question_intent_with_cot(question)
            
            # 4단계: CoT 결과를 바탕으로 최종 판단
            needs_vector = cot_analysis.get("needs_vector_search", False)
            confidence = cot_analysis.get("confidence", 0.5)
            reasoning = cot_analysis.get("reasoning", "")
            
            self.logger.info(f"CoT 분석 결과: needs_vector={needs_vector}, confidence={confidence}, reasoning={reasoning[:100]}...")
            
            return needs_vector
            
        except Exception as e:
            self.logger.warning(f"CoT 분석 실패, 기본 키워드 매칭으로 fallback: {e}")
            # fallback: 기본 키워드 매칭
            basic_vector_keywords = [
                "분석", "트렌드", "패턴", "예측", "supplier", "공급업체", "고객사",
                "상품", "제품", "랙", "재고", "어떤", "어디", "누가", "얼마"
            ]
            return any(keyword in question_lower for keyword in basic_vector_keywords)
    
    async def _analyze_question_intent_with_cot(self, question: str) -> Dict[str, Any]:
        """Chain of Thought를 통한 질문 의도 분석"""
        try:
            if not self.llm_client:
                return {"needs_vector_search": False, "reasoning": "LLM 클라이언트 없음"}
            
            cot_prompt = f"""
당신은 창고 관리 시스템의 질의 분석 전문가입니다. 다음 질문을 단계별로 분석하여 어떤 처리 방식이 필요한지 판단하세요.

**질문:** "{question}"

**분석 단계:**
1. 질문 유형 분류: 이 질문이 요구하는 것은 무엇인가?
2. 데이터 범위 판단: 단순 계산인가, 복합 검색인가?
3. 처리 방식 결정: 직접 계산, 벡터 검색, 일반 LLM 중 무엇이 적합한가?

**판단 기준:**
- 직접 계산: "총 재고량", "전체 입고량" 등 단순 합계 (숫자 하나만 원하는 경우)
- 벡터 검색: "어떤 업체들", "어떤 상품들", "주요 공급사", "A랙 상품", "상위 N개", "목록 조회", "현황 분석"
- 일반 LLM: 개념 설명, 사용법, 일반 상식

**중요:** 다음 질문들은 반드시 벡터 검색이 필요합니다:
- "A랙에 어떤 상품이 있지?" → 벡터 검색 (특정 위치 상품 조회)
- "주요 공급사는?" → 벡터 검색 (공급업체 목록 및 순위)
- "주요 상품은?" → 벡터 검색 (상품 목록 및 분석)
- "현재 재고량이 얼마야?" → 직접 계산 (단순 합계)

**응답 형식 (JSON):**
{{
    "question_type": "data_query|calculation|explanation|other",
    "data_scope": "simple|complex|none",
    "reasoning": "단계별 분석 결과",
    "needs_vector_search": true|false,
    "confidence": 0.0-1.0
}}
"""
            
            # 간단한 LLM 호출로 CoT 분석 수행 (CoT 플래그 전달)
            response = await self.llm_client.answer_simple_query(cot_prompt, {"cot_analysis": True})
            
            # JSON 응답 파싱 시도
            import json
            try:
                # JSON 부분만 추출
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    analysis = json.loads(json_str)
                    
                    self.logger.info(f"CoT 분석 완료: {analysis.get('reasoning', '')}")
                    return analysis
                else:
                    raise ValueError("JSON 형식을 찾을 수 없음")
                    
            except (json.JSONDecodeError, ValueError) as e:
                self.logger.warning(f"CoT JSON 파싱 실패: {e}")
                # 응답에서 키워드 기반 분석 fallback
                return self._fallback_intent_analysis(question, response)
                
        except Exception as e:
            self.logger.warning(f"CoT 분석 오류: {e}")
            return {"needs_vector_search": False, "reasoning": f"분석 실패: {e}"}
    
    def _fallback_intent_analysis(self, question: str, llm_response: str) -> Dict[str, Any]:
        """LLM 응답 기반 fallback 의도 분석"""
        response_lower = llm_response.lower()
        
        # LLM 응답에서 키워드 감지
        vector_indicators = [
            "벡터 검색", "vector", "복합", "검색", "조회", "분석", 
            "데이터", "목록", "비교", "상위", "하위"
        ]
        
        direct_indicators = [
            "직접", "계산", "단순", "합계", "총", "간단"
        ]
        
        has_vector_indicators = any(indicator in response_lower for indicator in vector_indicators)
        has_direct_indicators = any(indicator in response_lower for indicator in direct_indicators)
        
        if has_vector_indicators and not has_direct_indicators:
            return {
                "needs_vector_search": True,
                "reasoning": "LLM 응답에서 복합 검색 필요성 감지",
                "confidence": 0.7
            }
        elif has_direct_indicators:
            return {
                "needs_vector_search": False,
                "reasoning": "LLM 응답에서 직접 계산 가능성 감지",
                "confidence": 0.8
            }
        else:
            # 질문 자체에서 간단한 패턴 매칭
            question_lower = question.lower()
            complex_patterns = ["어떤", "어느", "누가", "뭐가", "무엇", "리스트", "목록", "상위", "하위"]
            
            if any(pattern in question_lower for pattern in complex_patterns):
                return {
                    "needs_vector_search": True,
                    "reasoning": "질문에서 복합 조회 패턴 감지",
                    "confidence": 0.6
                }
            else:
                return {
                    "needs_vector_search": False,
                    "reasoning": "단순 질문으로 판단",
                    "confidence": 0.5
                }

    async def _handle_direct_query(self, question: str) -> Optional[str]:
        """직접 계산으로 답변 가능한 간단한 질문 처리"""
        return self._try_direct_answer(question)
    
    async def _handle_vector_search_query(self, question: str) -> Optional[str]:
        """강화된 VectorDB 검색 - fallback 및 상세 응답 포함"""
        if not (self.vector_db_service and self.vector_db_service.is_initialized):
            self.logger.warning("VectorDB 서비스가 초기화되지 않음, fallback 실행")
            return await self._fallback_data_query(question)
            
        try:
            self.logger.info(f"🔍 VectorDB 검색 시작: {question} (총 2,900개 문서 대상)")
            search_result = await self.vector_db_service.search_relevant_data(
                query=question,
                n_results=25  # 2,900개 문서에서 더 많은 결과 검색
            )
            
            if not search_result.get("success"):
                self.logger.warning("⚠️ VectorDB 검색 실패, fallback 실행")
                return await self._fallback_data_query(question)
            
            # 검색 결과 상태 로깅
            found_docs = search_result.get('found_documents', 0)
            if found_docs > 0:
                self.logger.info(f"✅ {found_docs}개 관련 문서 발견")
            else:
                self.logger.warning("⚠️ 관련 문서를 찾지 못함, fallback 실행")
                return await self._fallback_data_query(question)
                
            # 검색 결과가 있으면 상세 응답 생성
            return await self._generate_detailed_response(search_result, question)
            
        except Exception as e:
            self.logger.error(f"VectorDB 검색 오류: {e}")
            return await self._fallback_data_query(question)
    
    async def _fallback_data_query(self, question: str) -> str:
        """VectorDB 실패 시 직접 데이터 조회"""
        question_lower = question.lower()
        
        try:
            # A랙 상태 문의 예시
            if "a랙" in question_lower and ("상태" in question_lower or "어때" in question_lower):
                rack_data = self._get_rack_specific_data("A")
                if rack_data:
                    status_note = "⚠️ (현재고 데이터는 추정값)" if rack_data.get('is_estimated') else "✅ (실제 데이터)"
                    system_status = self._get_system_status()
                    
                    return f"""🏢 **A랙 상태 정보:** {status_note}

📊 **재고 현황:** {rack_data.get('current_stock', 0):,}개
📈 **활용률:** {rack_data.get('utilization_rate', 0):.1f}%
📦 **저장 상품:** {', '.join(rack_data.get('products', ['정보 없음'])[:3])}
📋 **상품 종류:** {rack_data.get('product_count', 0)}개
⚠️ **상태:** {'✅ 정상' if rack_data.get('utilization_rate', 0) < 80 else '⚠️ 주의' if rack_data.get('utilization_rate', 0) < 95 else '🚨 포화'}

{system_status}"""
            
            # B랙 상태 문의
            elif "b랙" in question_lower and ("상태" in question_lower or "어때" in question_lower):
                rack_data = self._get_rack_specific_data("B")
                if rack_data:
                    return f"""🏢 **B랙 상태 정보:**
                    
📊 **재고 현황:** {rack_data.get('current_stock', 0):,}개
📈 **활용률:** {rack_data.get('utilization_rate', 0):.1f}%
📦 **저장 상품:** {', '.join(rack_data.get('products', ['정보 없음'])[:3])}
⚠️ **상태:** {'✅ 정상' if rack_data.get('utilization_rate', 0) < 80 else '⚠️ 주의' if rack_data.get('utilization_rate', 0) < 95 else '🚨 포화'}

💡 상세 정보는 벡터 데이터베이스가 복구되면 더 정확하게 제공됩니다."""
            
            # 일반 랙 관련 질문
            elif any(word in question_lower for word in ['랙', 'rack']) and any(word in question_lower for word in ['상태', '어때', '현황', '정보']):
                all_racks_data = self._get_all_racks_summary()
                return f"""🏢 **전체 랙 상태 현황:**

{all_racks_data}

💡 특정 랙의 상세 정보를 원하시면 "A랙 상태는 어때?" 형식으로 질문해주세요."""
            
            # 상품 관련 질문
            elif any(word in question_lower for word in ['상품', '제품']) and any(word in question_lower for word in ['어떤', '뭐', '목록']):
                return """📦 **주요 상품 정보:**

현재 벡터 검색 시스템이 일시적으로 사용할 수 없어 기본 정보만 제공됩니다.

🔧 **시스템 상태:** 벡터 데이터베이스 재시작 필요
💡 **권장 사항:** 시스템 관리자에게 문의하여 벡터 DB 서비스를 재시작해주세요.

📞 **대안:** 대시보드의 '상품별 재고 현황' 차트를 확인해보세요."""
            
        except Exception as e:
            self.logger.error(f"Fallback 데이터 조회 오류: {e}")
        
        return """❌ **시스템 일시 오류**

현재 상세 정보를 조회할 수 없습니다.

🔧 **가능한 원인:**
- 벡터 데이터베이스 연결 오류
- 데이터 서비스 일시 중단

💡 **해결 방안:**
1. 잠시 후 다시 시도해주세요
2. 대시보드 차트를 통해 기본 정보 확인
3. 시스템 관리자에게 문의

📞 **문의:** /api/vector-db/status로 시스템 상태를 확인할 수 있습니다."""
    
    def _get_rack_specific_data(self, rack_name: str) -> dict:
        """특정 랙의 데이터 조회 - 로그 기반 실제 컬럼명 사용"""
        try:
            if self.data_service.product_master is not None:
                # 로그에서 확인된 실제 컬럼명들
                rack_column_options = ['Rack Code Name', '랙위치', 'Rack Name']
                rack_column = None
                
                for col in rack_column_options:
                    if col in self.data_service.product_master.columns:
                        rack_column = col
                        self.logger.info(f"🔍 랙 컬럼 사용: {rack_column}")
                        break
                
                if rack_column:
                    # 부분 매칭으로 랙 데이터 찾기 (대소문자 무관)
                    rack_data = self.data_service.product_master[
                        self.data_service.product_master[rack_column].str.contains(
                            rack_name, case=False, na=False
                        )
                    ]
                    
                    if not rack_data.empty:
                        # 현재고 데이터 처리 (모든 값이 10인 경우 추정)
                        raw_stock = int(rack_data['현재고'].sum()) if '현재고' in rack_data.columns else 0
                        product_count = len(rack_data)
                        is_default_value = (raw_stock == product_count * 10)
                        
                        if is_default_value and product_count > 0:
                            self.logger.warning(f"⚠️ {rack_name}랙: 현재고가 기본값(10)으로 설정됨. 추정값 사용")
                            current_stock = product_count * 25  # 상품당 25개로 추정
                        else:
                            current_stock = raw_stock
                        
                        max_capacity = max(current_stock * 1.5, 100)  # 최소 100개 용량
                        utilization_rate = (current_stock / max_capacity) * 100 if max_capacity > 0 else 0
                        
                        products = rack_data['ProductName'].unique().tolist() if 'ProductName' in rack_data.columns else ['정보 없음']
                        
                        return {
                            'current_stock': current_stock,
                            'max_capacity': max_capacity,
                            'utilization_rate': utilization_rate,
                            'products': products,
                            'product_count': product_count,
                            'rack_column_used': rack_column,
                            'is_estimated': is_default_value
                        }
                else:
                    self.logger.warning(f"⚠️ 랙 컬럼을 찾을 수 없음. 사용 가능한 컬럼: {list(self.data_service.product_master.columns)}")
                    
        except Exception as e:
            self.logger.error(f"랙 데이터 조회 오류: {e}")
        
        return None
    
    def _get_all_racks_summary(self) -> str:
        """전체 랙 요약 정보 - 실제 컬럼명 사용"""
        try:
            if self.data_service.product_master is not None:
                # 랙 컬럼 찾기
                rack_column_options = ['Rack Code Name', '랙위치', 'Rack Name']
                rack_column = None
                
                for col in rack_column_options:
                    if col in self.data_service.product_master.columns:
                        rack_column = col
                        break
                
                if rack_column:
                    rack_summary = self.data_service.product_master.groupby(rack_column)['현재고' if '현재고' in self.data_service.product_master.columns else 'Start Pallete Qty'].sum().sort_values(ascending=False)
                    
                    summary_lines = []
                    for i, (rack, qty) in enumerate(rack_summary.head(10).items()):
                        # 기본값(10) 감지 및 수정
                        product_count = len(self.data_service.product_master[self.data_service.product_master[rack_column] == rack])
                        if qty == product_count * 10:
                            # 추정값 사용
                            estimated_qty = product_count * 25
                            utilization = min((estimated_qty / 100.0) * 100, 100)
                            qty_display = f"{estimated_qty:,}개 (추정)"
                        else:
                            utilization = min((qty / 50.0) * 100, 100)
                            qty_display = f"{int(qty):,}개"
                        
                        status_icon = "✅" if utilization < 80 else "⚠️" if utilization < 95 else "🚨"
                        summary_lines.append(f"{status_icon} **{rack}랙:** {qty_display} ({utilization:.1f}%)")
                    
                    return "\n".join(summary_lines)
                else:
                    return "📊 랙 컬럼을 찾을 수 없어 데이터를 가져올 수 없습니다."
        except Exception as e:
            self.logger.error(f"전체 랙 요약 오류: {e}")
        
        return "📊 현재 랙 정보를 가져올 수 없습니다."
    
    async def _generate_detailed_response(self, search_result: dict, question: str) -> str:
        """검색 결과를 바탕으로 상세 응답 생성"""
        try:
            # Vector 검색 결과를 구조화된 프롬프트로 변환
            structured_context = self._vectordb_to_prompt(search_result, question)
            
            # 최적화된 VectorDB 전용 LLM 호출
            response = await self.llm_client.answer_with_vector_context(
                question, structured_context
            )
            
            # 검색된 문서 수 정보 추가
            doc_count = search_result.get('found_documents', 0)
            if doc_count > 0:
                response += f"\n\n📊 *{doc_count}개의 관련 데이터를 분석한 결과입니다.*"
            
            self.logger.info("VectorDB 검색 상세 응답 생성 완료")
            return response
            
        except Exception as e:
            self.logger.error(f"상세 응답 생성 오류: {e}")
            return await self._fallback_data_query(question)
    
    async def _handle_general_query(self, question: str) -> str:
        """일반적인 질문을 기본 데이터로 처리"""
        intent = self.analyze_intent(question)
        context_data = self.data_service.get_relevant_data(intent)
        
        # 간단한 LLM 호출 (VectorDB 없이)
        return await self.llm_client.answer_simple_query(question, context_data)
    
    def _vectordb_to_prompt(self, search_result: Dict, question: str) -> str:
        """VectorDB 검색 결과를 구조화된 프롬프트로 변환"""
        documents = search_result.get('documents', [])
        chart_data = search_result.get('chart_data', {})
        metadata_summary = search_result.get('metadata_summary', {})
        
        prompt_parts = [
            f"질문: {question}",
            "",
            "== 실제 창고 데이터 검색 결과 ==",
            f"검색된 문서 수: {search_result.get('found_documents', 0)}개",
            ""
        ]
        
        # 메타데이터 요약 정보 추가 (더 구체적)
        if metadata_summary:
            prompt_parts.extend([
                "== 데이터 요약 정보 ==",
                f"• 총 레코드: {metadata_summary.get('total_records', 0)}개",
                f"• 데이터 유형: {metadata_summary.get('data_types', {})}",
                f"• 날짜 범위: {metadata_summary.get('date_range', {})}",
                f"• 수량 통계: {metadata_summary.get('quantity_stats', {})}",
                ""
            ])
        
        # 문서 정보 추가 (상위 3개)
        if documents:
            prompt_parts.append("== 관련 문서 내용 ==")
            for i, doc in enumerate(documents[:3], 1):
                prompt_parts.append(f"{i}. {doc.strip()}")
            prompt_parts.append("")
        
        # 차트 데이터가 있으면 추가
        if chart_data:
            prompt_parts.extend([
                "== 집계된 차트 데이터 ==",
                f"제목: {chart_data.get('title', 'N/A')}",
                f"데이터: {chart_data.get('data', [])}",
                f"라벨: {chart_data.get('labels', [])}",
                ""
            ])
        
        return "\n".join(prompt_parts)
    
    def _try_direct_answer(self, question: str) -> Optional[str]:
        """간단한 질문들에 대해 직접 계산하여 답변"""
        if not self.data_service.data_loaded:
            return None
            
        question_lower = question.lower()
        
        try:
            # 총 재고량 질문
            if any(word in question_lower for word in ['총 재고량', '총재고', '전체 재고', '총 재고']):
                if self.data_service.product_master is not None and '현재고' in self.data_service.product_master.columns:
                    total_inventory = int(self.data_service.product_master['현재고'].sum())
                    product_count = len(self.data_service.product_master)
                    return f"🏢 **총 재고량은 {total_inventory:,}개입니다.**\n\n📊 전체 {product_count}개 품목의 현재 재고를 합계한 결과입니다.\n💡 자세한 랙별 분포는 '랙별 재고 현황' 차트를 확인해보세요."
                else:
                    return "📊 죄송합니다. 현재고 데이터를 찾을 수 없습니다. 데이터가 로드되었는지 확인해주세요."
            
            # 입고량 질문
            if any(word in question_lower for word in ['입고량', '입고 현황', '오늘 입고']):
                if self.data_service.inbound_data is not None and 'PalleteQty' in self.data_service.inbound_data.columns:
                    total_inbound = int(self.data_service.inbound_data['PalleteQty'].sum())
                    inbound_count = len(self.data_service.inbound_data)
                    return f"📦 **총 입고량은 {total_inbound:,}개입니다.**\n\n📈 총 {inbound_count}건의 입고 기록이 있습니다.\n💡 상세한 입고 트렌드는 '일별 입출고 트렌드' 차트를 확인해보세요."
                else:
                    return "📦 죄송합니다. 입고 데이터를 찾을 수 없습니다."
            
            # 출고량 질문
            if any(word in question_lower for word in ['출고량', '출고 현황', '오늘 출고']):
                if self.data_service.outbound_data is not None and 'PalleteQty' in self.data_service.outbound_data.columns:
                    total_outbound = int(self.data_service.outbound_data['PalleteQty'].sum())
                    outbound_count = len(self.data_service.outbound_data)
                    return f"🚚 **총 출고량은 {total_outbound:,}개입니다.**\n\n📉 총 {outbound_count}건의 출고 기록이 있습니다.\n💡 상세한 출고 트렌드는 '일별 입출고 트렌드' 차트를 확인해보세요."
                else:
                    return "🚚 죄송합니다. 출고 데이터를 찾을 수 없습니다."
            
            # 랙 관련 질문
            if any(word in question_lower for word in ['랙', 'rack', 'a랙', 'b랙', 'c랙']):
                if self.data_service.product_master is not None and 'Rack Name' in self.data_service.product_master.columns:
                    rack_summary = self.data_service.product_master.groupby('Rack Name')['현재고'].sum().sort_values(ascending=False)
                    if len(rack_summary) > 0:
                        rack_info = []
                        for rack, qty in rack_summary.head(5).items():
                            rack_info.append(f"• {rack}: {int(qty):,}개")
                        
                        return f"🏢 **랙별 재고 현황:**\n\n" + "\n".join(rack_info) + f"\n\n📊 총 {len(rack_summary)}개 랙에 재고가 분산되어 있습니다."
                    else:
                        return "🏢 랙 정보를 찾을 수 없습니다."
                else:
                    return "🏢 죄송합니다. 랙 데이터를 찾을 수 없습니다."
            
        except Exception as e:
            print(f"직접 답변 계산 오류: {e}")
            return None
        
        return None
    
    async def _handle_self_rag_query(self, question: str) -> Optional[str]:
        """SELF-RAG 전용 질문 처리"""
        try:
            self.logger.info(f"🧠 SELF-RAG 전용 처리: {question}")
            return await self.langchain_service.process_with_self_rag(question)
        except Exception as e:
            self.logger.error(f"SELF-RAG 처리 실패: {e}")
            return None
    
    def _get_system_status(self) -> str:
        """현재 시스템 상태 요약"""
        try:
            if self.vector_db_service and self.vector_db_service.is_initialized:
                return "🟢 **시스템 상태:** 벡터 검색 가능 (2,900개 문서 인덱싱 완료)"
            else:
                return "🟡 **시스템 상태:** 벡터 검색 일시 불가, 기본 데이터로 응답"
        except:
            return "🔴 **시스템 상태:** 일부 기능 제한"