import os
import logging
import time
import asyncio
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
from threading import Lock

import google.generativeai as genai

# AI 모델 설정 (legacy/crad_lcrag/utils/ai_model_manager.py 참조)
AI_MODEL_CONFIG = {
    "temperature": 0.1,
    "top_p": 0.8,
    "top_k": 40,
    "max_output_tokens": 2048,
}

@dataclass
class APIKeyStatus:
    """API 키 상태 정보 (gemini_client.py 참조)"""
    key: str
    is_active: bool = True
    request_count: int = 0
    last_request_time: float = 0.0
    error_count: int = 0
    success_count: int = 0
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.error_count
        return self.success_count / total if total > 0 else 0.0

@dataclass
class RateLimitConfig:
    """요청 제한 설정 (rate_limiter.py 참조)"""
    rpm_limit: int = 2000  # 분당 요청 제한
    tpm_limit: int = 4000000  # 분당 토큰 제한
    burst_limit: int = 100  # 버스트 허용 한도
    window_size: int = 60  # 시간 윈도우 (초)

@dataclass
class TokenBucket:
    """토큰 버킷 (rate_limiter.py 참조)"""
    capacity: int
    tokens: float = field(default_factory=lambda: 0)
    last_refill: float = field(default_factory=time.time)
    refill_rate: float = field(default=1.0)  # 초당 토큰 보충률
    
    def __post_init__(self):
        self.tokens = self.capacity
        self.refill_rate = self.capacity / 60.0  # 분당 용량을 초당으로 변환

class RateLimiter:
    """API 요청 제한 관리자 (rate_limiter.py 참조)"""
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.request_buckets: Dict[str, TokenBucket] = {}
        self.token_buckets: Dict[str, TokenBucket] = {}
        self.request_history: Dict[str, deque] = {}
        self.token_history: Dict[str, deque] = {}
        self.lock = Lock()
        self.logger = logging.getLogger(__name__)

    def _get_or_create_buckets(self, api_key: str) -> tuple[TokenBucket, TokenBucket]:
        with self.lock:
            if api_key not in self.request_buckets:
                self.request_buckets[api_key] = TokenBucket(
                    capacity=self.config.rpm_limit,
                    refill_rate=self.config.rpm_limit / 60.0
                )
                self.token_buckets[api_key] = TokenBucket(
                    capacity=self.config.tpm_limit,
                    refill_rate=self.config.tpm_limit / 60.0
                )
                self.request_history[api_key] = deque(maxlen=self.config.rpm_limit)
                self.token_history[api_key] = deque(maxlen=self.config.tpm_limit)
                self.logger.debug(f"🔧 API 키 {api_key[:10]}... 토큰 버킷 생성")
            return self.request_buckets[api_key], self.token_buckets[api_key]

    def _refill_bucket(self, bucket: TokenBucket):
        current_time = time.time()
        time_passed = current_time - bucket.last_refill
        tokens_to_add = time_passed * bucket.refill_rate
        bucket.tokens = min(bucket.capacity, bucket.tokens + tokens_to_add)
        bucket.last_refill = current_time

    def _check_window_limit(self, api_key: str, estimated_tokens: int = 1) -> bool:
        current_time = time.time()
        window_start = current_time - self.config.window_size
        
        request_history = self.request_history[api_key]
        while request_history and request_history[0] < window_start:
            request_history.popleft()
        
        token_history = self.token_history[api_key]
        while token_history and token_history[0]['timestamp'] < window_start:
            token_history.popleft()
        
        current_requests = len(request_history)
        current_tokens = sum(entry['tokens'] for entry in token_history)
        
        if current_requests >= self.config.rpm_limit:
            self.logger.warning(f"⚠️ API 키 {api_key[:10]}... RPM 제한 초과: {current_requests}/{self.config.rpm_limit}")
            return False
        
        if current_tokens + estimated_tokens > self.config.tpm_limit:
            self.logger.warning(f"⚠️ API 키 {api_key[:10]}... TPM 제한 초과: {current_tokens + estimated_tokens}/{self.config.tpm_limit}")
            return False
        
        return True

    async def acquire_permission(
        self,
        api_key: str,
        estimated_tokens: int = 1,
        timeout: float = 10.0
    ) -> bool:
        start_time = time.time()
        request_bucket, token_bucket = self._get_or_create_buckets(api_key)
        
        while time.time() - start_time < timeout:
            with self.lock:
                self._refill_bucket(request_bucket)
                self._refill_bucket(token_bucket)
                
                if not self._check_window_limit(api_key, estimated_tokens):
                    await asyncio.sleep(0.1)
                    continue
                
                if request_bucket.tokens >= 1 and token_bucket.tokens >= estimated_tokens:
                    request_bucket.tokens -= 1
                    token_bucket.tokens -= estimated_tokens
                    current_time = time.time()
                    self.request_history[api_key].append(current_time)
                    self.token_history[api_key].append({'timestamp': current_time, 'tokens': estimated_tokens})
                    self.logger.debug(f"✅ 요청 허가 승인: {api_key[:10]}... (토큰: {estimated_tokens})")
                    return True
            await asyncio.sleep(0.1)
        self.logger.warning(f"⏰ 요청 허가 타임아웃: {api_key[:10]}...")
        return False

    def estimate_tokens(self, text: str) -> int:
        # 간단한 추정 (실제로는 더 정확한 토큰화 필요)
        return max(1, len(text) // 4)

    def get_usage_stats(self, api_key: str) -> Dict[str, Any]:
        if api_key not in self.request_buckets:
            return {"requests_available": self.config.rpm_limit,
                    "tokens_available": self.config.tpm_limit,
                    "requests_used": 0,
                    "tokens_used": 0,
                    "usage_rate": 0.0}
        request_bucket, token_bucket = self._get_or_create_buckets(api_key)
        self._refill_bucket(request_bucket)
        self._refill_bucket(token_bucket)
        current_time = time.time()
        window_start = current_time - self.config.window_size
        recent_requests = [req for req in self.request_history[api_key] if req > window_start]
        recent_tokens = sum(entry['tokens'] for entry in self.token_history[api_key] if entry['timestamp'] > window_start)
        return {"requests_available": int(request_bucket.tokens),
                "tokens_available": int(token_bucket.tokens),
                "requests_used": len(recent_requests),
                "tokens_used": recent_tokens,
                "usage_rate": len(recent_requests) / self.config.rpm_limit,
                "request_bucket_capacity": request_bucket.capacity,
                "token_bucket_capacity": token_bucket.capacity}

class WarehouseAI:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.gemini_models: List[Dict] = []
        self.gemini_config = AI_MODEL_CONFIG
        self.current_model_index = 0
        self.rate_limiter = RateLimiter() # RateLimiter 인스턴스 추가
        self._setup_models()

    def _setup_models(self):
        """여러 Gemini API 키로 모델 초기화"""
        try:
            api_keys = {
                'GEMINI_1': os.getenv('GEMINI_API_KEY_1'),
                'GEMINI_2': os.getenv('GEMINI_API_KEY_2'),
                'GEMINI_3': os.getenv('GEMINI_API_KEY_3'),
                'GEMINI_4': os.getenv('GEMINI_API_KEY_4')
            }

            valid_keys = {k: v for k, v in api_keys.items() if v}
            if not valid_keys:
                self.logger.warning("경고: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. AI 기능이 제한될 수 있습니다.")

            for model_name, api_key in valid_keys.items():
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(
                        "gemini-2.0-flash-lite-001", # ai_model_manager.py에서 사용된 모델명
                        generation_config=self.gemini_config
                    )
                    self.gemini_models.append({
                        'model': model,
                        'api_key': api_key,
                        'name': model_name,
                        'failures': 0 # 실패 횟수 추적 (간단 구현)
                    })
                    self.logger.info(f"🤖 {model_name} 모델 초기화 성공")
                except Exception as e:
                    self.logger.error(f"❌ {model_name} 모델 초기화 실패: {e}")
                    continue

            if not self.gemini_models:
                self.logger.error("사용 가능한 Gemini 모델이 없습니다.")

            self.logger.info(f"🎉 총 {len(self.gemini_models)}개의 Gemini 모델 초기화 완료")

        except Exception as e:
            self.logger.error(f"❌ AI 모델 초기화 실패: {e}")
            raise

    def _get_next_model(self) -> Optional[Dict]:
        """다음 사용 가능한 모델 선택 (RateLimiter를 활용하여 개선)"""
        if not self.gemini_models:
            return None
        
        available_api_keys = [m['api_key'] for m in self.gemini_models if m['failures'] < 3]
        if not available_api_keys:
            # 모든 모델이 실패한 경우 실패 횟수 리셋
            for model in self.gemini_models:
                model['failures'] = 0
            available_api_keys = [m['api_key'] for m in self.gemini_models]
        
        # RateLimiter의 get_best_available_key를 활용하여 최적의 키 선택
        best_key = self.rate_limiter.get_best_available_key(available_api_keys, estimated_tokens=1) # 토큰 추정은 나중에 질문 텍스트 기반으로 개선
        
        if best_key:            
            # 선택된 키에 해당하는 모델 정보 반환
            for model_info in self.gemini_models:
                if model_info['api_key'] == best_key:
                    return model_info
        return None

    async def answer_query(self, question: str, data_context: dict):
        """Gemini API를 통한 질의응답"""
        if not self.gemini_models:
            return "오류: 사용 가능한 AI 모델이 없습니다."

        max_attempts = len(self.gemini_models)
        estimated_tokens = self.rate_limiter.estimate_tokens(question) # 질문 텍스트 기반 토큰 추정

        for attempt in range(max_attempts):
            current_model_info = self._get_next_model()
            if not current_model_info:
                continue

            api_key = current_model_info['api_key']
            
            # RateLimiter를 통해 권한 획득 시도
            if not await self.rate_limiter.acquire_permission(api_key, estimated_tokens):
                self.logger.warning(f"⚠️ API 키 {api_key[:10]}... 요청 제한으로 인해 대기 또는 다른 키 시도.")
                # 여기서는 바로 다음 키로 넘어가거나, 짧게 대기 후 재시도할 수 있음
                # 간단하게 다음 모델로 넘어가도록 처리
                continue

            try:
                model_instance = current_model_info['model']
                prompt = f"""
        창고 데이터를 바탕으로 질문에 답하세요:
        데이터: {data_context}
        질문: {question}
        """
                # Gemini API 호출
                response = await model_instance.generate_content(prompt)
                result_text = response.text

                self.logger.info(f"✅ {current_model_info['name']} API 성공 - 응답 (일부): {result_text[:200]}...")
                return result_text

            except Exception as e:
                current_model_info['failures'] += 1
                self.logger.warning(f"⚠️ {current_model_info['name']} API 실패 (시도 {attempt + 1}/{max_attempts}): {str(e)}")

                # 지수 백오프 적용 (RateLimiter의 acquire_permission에서 이미 처리되지만, 여기서도 추가 가능)
                await asyncio.sleep(0.5 * (2 ** attempt)) # 간단한 백오프

                if attempt < max_attempts - 1:
                    self.logger.info(f"🔄 다음 모델로 재시도 중...")
                    continue
                else:
                    self.logger.error(f"❌ 모든 Gemini 모델 시도 실패")
                    return f"오류: 모든 API 호출 실패 - 마지막 오류: {str(e)}"

        return "오류: 모든 모델 시도 실패" 