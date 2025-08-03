"""
ChromaDB를 활용한 벡터 데이터베이스 서비스
"""
import os
import logging
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
except ImportError:
    chromadb = None
    SentenceTransformer = None

class VectorDBService:
    """ChromaDB를 활용한 창고 데이터 벡터화 및 검색 서비스"""
    
    def __init__(self, data_service=None, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.data_service = data_service
        self.client = None
        self.collection = None
        self.encoder = None
        self.is_initialized = False
        
        if chromadb is None or SentenceTransformer is None:
            self.logger.warning("⚠️ ChromaDB 또는 SentenceTransformers가 설치되지 않았습니다.")
            self.logger.warning("pip install chromadb sentence-transformers를 실행해주세요.")
            return
        
        self._initialize_chromadb()
    
    def _initialize_chromadb(self):
        """ChromaDB 클라이언트 초기화"""
        try:
            # ChromaDB 클라이언트 생성 (로컬 모드)
            self.client = chromadb.PersistentClient(
                path="./chromadb_storage",
                settings=Settings(anonymized_telemetry=False)
            )
            
            # 컬렉션 생성 또는 가져오기
            collection_name = "warehouse_data"
            try:
                self.collection = self.client.get_collection(collection_name)
                self.logger.info(f"✅ 기존 ChromaDB 컬렉션 로드: {collection_name}")
            except:
                self.collection = self.client.create_collection(collection_name)
                self.logger.info(f"✅ 새 ChromaDB 컬렉션 생성: {collection_name}")
            
            # 임베딩 모델 초기화 (한국어 지원, fallback 포함)
            try:
                self.encoder = SentenceTransformer('jhgan/ko-sroberta-multitask')
                self.logger.info("✅ 한국어 임베딩 모델 로드 완료")
            except Exception as korean_model_error:
                self.logger.warning(f"⚠️ 한국어 모델 로드 실패: {korean_model_error}")
                try:
                    # 다국어 모델로 fallback
                    self.encoder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                    self.logger.info("✅ 다국어 임베딩 모델 로드 완료 (fallback)")
                except Exception as fallback_error:
                    self.logger.warning(f"⚠️ 다국어 모델 로드 실패: {fallback_error}")
                    # 가장 기본적인 영어 모델로 fallback
                    self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
                    self.logger.info("✅ 영어 임베딩 모델 로드 완료 (final fallback)")
            
            self.is_initialized = True
            
        except Exception as e:
            self.logger.error(f"❌ ChromaDB 초기화 실패: {str(e)}")
            self.is_initialized = False
    
    async def index_warehouse_data(self, force_rebuild=False):
        """창고 데이터를 벡터 데이터베이스에 인덱싱 (강제 리빌드 지원)"""
        if not self.is_initialized or not self.data_service:
            self.logger.warning("⚠️ VectorDB 또는 DataService가 초기화되지 않았습니다.")
            return False
        
        try:
            # 데이터 서비스 상태 확인
            self.logger.info(f"📊 데이터 로드 상태: {self.data_service.data_loaded}")
            self.logger.info(f"📊 입고 데이터: {len(self.data_service.inbound_data) if self.data_service.inbound_data is not None else 0}개")
            self.logger.info(f"📊 출고 데이터: {len(self.data_service.outbound_data) if self.data_service.outbound_data is not None else 0}개")
            self.logger.info(f"📊 제품 데이터: {len(self.data_service.product_master) if self.data_service.product_master is not None else 0}개")
            
            # 📅 날짜 범위 상세 확인
            if not self.data_service.inbound_data.empty and 'Date' in self.data_service.inbound_data.columns:
                import pandas as pd
                dates = pd.to_datetime(self.data_service.inbound_data['Date'], errors='coerce').dropna()
                unique_dates = sorted(dates.dt.strftime('%Y-%m-%d').unique())
                self.logger.info(f"📅 [VECTOR_INDEX] 입고 데이터 날짜: {unique_dates}")
            
            if not self.data_service.outbound_data.empty and 'Date' in self.data_service.outbound_data.columns:
                import pandas as pd
                dates = pd.to_datetime(self.data_service.outbound_data['Date'], errors='coerce').dropna()
                unique_dates = sorted(dates.dt.strftime('%Y-%m-%d').unique())
                self.logger.info(f"📅 [VECTOR_INDEX] 출고 데이터 날짜: {unique_dates}")
            
            # 기존 데이터 확인
            existing_count = self.collection.count()
            
            # 🔥 강제 리빌드 모드: 데이터 일관성 확보
            if force_rebuild or existing_count == 0:
                if existing_count > 0:
                    self.logger.info(f"🔄 강제 리빌드 모드: 기존 {existing_count}개 문서 삭제")
                    self.collection.delete(where={})
                    self.logger.info("🗑️ 기존 벡터 데이터 완전 삭제")
                else:
                    self.logger.info("🆕 초기 인덱싱 시작")
            else:
                self.logger.info(f"✅ 기존 벡터 데이터 사용: {existing_count}개 문서")
                return True
            
            documents = []
            metadatas = []
            ids = []
            
            # 입고 데이터 인덱싱
            if self.data_service.inbound_data is not None and len(self.data_service.inbound_data) > 0:
                inbound_docs, inbound_metas, inbound_ids = self._process_inbound_data()
                documents.extend(inbound_docs)
                metadatas.extend(inbound_metas)
                ids.extend(inbound_ids)
            else:
                self.logger.warning("⚠️ 입고 데이터가 없거나 비어있습니다.")
            
            # 출고 데이터 인덱싱
            if self.data_service.outbound_data is not None and len(self.data_service.outbound_data) > 0:
                outbound_docs, outbound_metas, outbound_ids = self._process_outbound_data()
                documents.extend(outbound_docs)
                metadatas.extend(outbound_metas)
                ids.extend(outbound_ids)
            else:
                self.logger.warning("⚠️ 출고 데이터가 없거나 비어있습니다.")
            
            # 상품 마스터 데이터 인덱싱
            if self.data_service.product_master is not None and len(self.data_service.product_master) > 0:
                product_docs, product_metas, product_ids = self._process_product_data()
                documents.extend(product_docs)
                metadatas.extend(product_metas)
                ids.extend(product_ids)
            else:
                self.logger.warning("⚠️ 제품 마스터 데이터가 없거나 비어있습니다.")
            
            if documents:
                # 임베딩 생성
                self.logger.info(f"🔄 {len(documents)}개 문서 임베딩 생성 중...")
                embeddings = self.encoder.encode(documents).tolist()
                
                # ChromaDB에 저장
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    embeddings=embeddings,
                    ids=ids
                )
                
                # 인덱싱 결과 상세 정보
                type_counts = {}
                for meta in metadatas:
                    data_type = meta.get('type', 'unknown')
                    type_counts[data_type] = type_counts.get(data_type, 0) + 1
                
                self.logger.info(f"✅ 벡터 데이터베이스 인덱싱 완료:")
                self.logger.info(f"  📊 총 문서: {len(documents)}개")
                for data_type, count in type_counts.items():
                    self.logger.info(f"  📋 {data_type}: {count}개")
                
                return True
            else:
                self.logger.warning("⚠️ 인덱싱할 데이터가 없습니다.")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 벡터 인덱싱 실패: {str(e)}")
            return False
    
    def _process_inbound_data(self):
        """입고 데이터를 문서화"""
        documents = []
        metadatas = []
        ids = []
        
        df = self.data_service.inbound_data
        self.logger.info(f"📦 입고 데이터 처리 시작: {len(df)}개 행")
        self.logger.info(f"📦 입고 데이터 컬럼: {list(df.columns)}")
        
        for idx, row in df.iterrows():
            try:
                # 자연어 문서 생성 (실제 컬럼명 사용)
                doc = f"""
                입고 정보: {row.get('Supplier', '알 수 없음')} 공급업체에서 {row.get('ProductName', '알 수 없음')} 상품을 
                {row.get('PalleteQty', 0)}개 파레트 입고했습니다. 
                날짜: {row.get('Date', '알 수 없음')}, 
                상품코드: {row.get('ProductCode', '알 수 없음')}, 
                입고위치: {row.get('InboundPosition', '알 수 없음')},
                입고라인: {row.get('InboundLine', '알 수 없음')}
                """
                
                # 메타데이터 (실제 차트에 사용될 수치 데이터)
                metadata = {
                    "type": "inbound",
                    "supplier": str(row.get('Supplier', '')),
                    "product_code": str(row.get('ProductCode', '')),
                    "product_name": str(row.get('ProductName', '')),
                    "quantity": float(row.get('PalleteQty', 0)),
                    "date": str(row.get('Date', '')),
                    "position": str(row.get('InboundPosition', '')),
                    "inbound_line": str(row.get('InboundLine', '')),
                    "row_index": int(idx)
                }
                
                documents.append(doc.strip())
                metadatas.append(metadata)
                ids.append(f"inbound_{idx}")
                
            except Exception as e:
                self.logger.warning(f"⚠️ 입고 데이터 행 {idx} 처리 실패: {e}")
                continue
        
        self.logger.info(f"✅ 입고 데이터 처리 완료: {len(documents)}개 문서 생성")
        return documents, metadatas, ids
    
    def _process_outbound_data(self):
        """출고 데이터를 문서화"""
        documents = []
        metadatas = []
        ids = []
        
        df = self.data_service.outbound_data
        self.logger.info(f"📤 출고 데이터 처리 시작: {len(df)}개 행")
        self.logger.info(f"📤 출고 데이터 컬럼: {list(df.columns)}")
        
        for idx, row in df.iterrows():
            try:
                # 자연어 문서 생성 (실제 컬럼명 사용)
                doc = f"""
                출고 정보: {row.get('Business name', '알 수 없음')} 고객사로 {row.get('ProductName', '알 수 없음')} 상품을 
                {row.get('PalleteQty', 0)}개 파레트 출고했습니다. 
                날짜: {row.get('Date', '알 수 없음')}, 
                상품코드: {row.get('ProductCode', '알 수 없음')}, 
                출고위치: {row.get('ProductPosition', '알 수 없음')},
                출고라인: {row.get('OutboundLine', '알 수 없음')}
                """
                
                # 메타데이터
                metadata = {
                    "type": "outbound",
                    "business_name": str(row.get('Business name', '')),
                    "product_code": str(row.get('ProductCode', '')),
                    "product_name": str(row.get('ProductName', '')),
                    "quantity": float(row.get('PalleteQty', 0)),
                    "date": str(row.get('Date', '')),
                    "position": str(row.get('ProductPosition', '')),
                    "outbound_line": str(row.get('OutboundLine', '')),
                    "row_index": int(idx)
                }
                
                documents.append(doc.strip())
                metadatas.append(metadata)
                ids.append(f"outbound_{idx}")
                
            except Exception as e:
                self.logger.warning(f"⚠️ 출고 데이터 행 {idx} 처리 실패: {e}")
                continue
        
        self.logger.info(f"✅ 출고 데이터 처리 완료: {len(documents)}개 문서 생성")
        return documents, metadatas, ids
    
    def _process_product_data(self):
        """상품 마스터 데이터를 문서화 (실제 컬럼명 기반 개선)"""
        documents = []
        metadatas = []
        ids = []
        
        df = self.data_service.product_master
        self.logger.info(f"📋 제품 데이터 처리 시작: {len(df)}개 행")
        self.logger.info(f"📋 제품 데이터 컬럼: {list(df.columns)}")
        
        # 🔧 실제 컬럼명 매핑 (로그에서 확인된 실제 컬럼명 사용)
        rack_column_options = ['랙위치', 'Rack Name', 'Rack Code Name']
        rack_column = None
        for col in rack_column_options:
            if col in df.columns:
                rack_column = col
                self.logger.info(f"🔍 랙 정보 컬럼 사용: {rack_column}")
                break
        
        if not rack_column:
            self.logger.warning(f"⚠️ 랙 정보 컬럼을 찾을 수 없음. 사용 가능한 컬럼: {list(df.columns)}")
            rack_column = '랙위치'  # 기본값
        
        for idx, row in df.iterrows():
            try:
                # 🏷️ 실제 랙 정보 추출
                rack_info = str(row.get(rack_column, '알 수 없음'))
                product_name = str(row.get('ProductName', '알 수 없음'))
                product_code = str(row.get('상품코드', row.get('ProductCode', '알 수 없음')))
                current_stock = row.get('현재고', row.get('Start Pallete Qty', 0))
                unit = str(row.get('Unit', '개'))
                
                # 📝 자연어 문서 생성 (랙 정보 강화)
                doc = f"""
                상품명: {product_name} (상품코드: {product_code})
                현재 재고량: {current_stock} {unit}
                저장 위치: {rack_info}랙
                시작 재고량: {row.get('Start Pallete Qty', 0)}
                랙 위치 정보: {rack_info}랙에 저장된 {product_name} 상품
                """
                
                # 📊 메타데이터 (실제 컬럼명 기반)
                metadata = {
                    "type": "product",
                    "product_code": product_code,
                    "product_name": product_name,
                    "current_stock": float(current_stock) if current_stock else 0.0,
                    "unit": unit,
                    "rack_name": rack_info,
                    "rack_location": rack_info,  # 검색용 추가 필드
                    "start_qty": float(row.get('Start Pallete Qty', 0)),
                    "row_index": int(idx),
                    "rack_column_used": rack_column  # 디버깅용
                }
                
                documents.append(doc.strip())
                metadatas.append(metadata)
                ids.append(f"product_{idx}")
                
                # 🔍 디버깅: 처음 5개 항목 로그
                if idx < 5:
                    self.logger.info(f"📦 상품 {idx}: {product_name} → {rack_info}랙 ({current_stock} {unit})")
                
            except Exception as e:
                self.logger.warning(f"⚠️ 제품 데이터 행 {idx} 처리 실패: {e}")
                continue
        
        # 📊 랙별 통계 생성
        rack_stats = {}
        for meta in metadatas:
            rack = meta['rack_name']
            if rack not in rack_stats:
                rack_stats[rack] = {'count': 0, 'total_stock': 0}
            rack_stats[rack]['count'] += 1
            rack_stats[rack]['total_stock'] += meta['current_stock']
        
        self.logger.info(f"✅ 제품 데이터 처리 완료: {len(documents)}개 문서 생성")
        self.logger.info(f"📊 랙별 통계: {dict(sorted(rack_stats.items()))}")
        return documents, metadatas, ids
    
    async def search_relevant_data(self, query: str, n_results: int = 20) -> Dict[str, Any]:
        """사용자 쿼리와 관련된 데이터 검색"""
        self.logger.info(f"🔍 [VECTOR_SEARCH] 검색 시작: '{query}' (최대 {n_results}개)")
        
        if not self.is_initialized:
            self.logger.error("❌ [VECTOR_ERROR] 벡터 데이터베이스가 초기화되지 않았습니다")
            return {"error": "벡터 데이터베이스가 초기화되지 않았습니다."}
        
        try:
            # 쿼리 임베딩
            self.logger.info("🔄 [VECTOR_EMBEDDING] 쿼리 임베딩 생성")
            query_embedding = self.encoder.encode([query]).tolist()[0]
            self.logger.info(f"📊 [VECTOR_EMBEDDING] 임베딩 차원: {len(query_embedding)}")
            
            # 유사한 문서 검색
            self.logger.info(f"🔍 [VECTOR_QUERY] ChromaDB 검색 수행 (n_results={n_results})")
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=['documents', 'metadatas', 'distances']
            )
            
            if not results['documents'] or not results['documents'][0]:
                self.logger.warning("⚠️ [VECTOR_EMPTY] 관련 데이터를 찾을 수 없습니다")
                return {"error": "관련 데이터를 찾을 수 없습니다."}
            
            # 검색 결과 정리
            documents = results['documents'][0]
            metadatas = results['metadatas'][0]
            distances = results['distances'][0]
            
            self.logger.info(f"✅ [VECTOR_SUCCESS] 검색 완료: {len(documents)}개 문서 발견")
            self.logger.info(f"📊 [VECTOR_STATS] 평균 거리: {sum(distances)/len(distances):.3f}" if distances else "📊 [VECTOR_STATS] 거리 정보 없음")
            
            # 메타데이터에서 실제 차트 데이터 추출
            self.logger.info("📈 [VECTOR_CHART] 차트 데이터 추출 시도")
            chart_data = self._extract_chart_data_from_metadata(metadatas, query)
            self.logger.info(f"📈 [VECTOR_CHART] 차트 데이터 추출 결과: {bool(chart_data)}")
            
            # 메타데이터 요약
            self.logger.info("📋 [VECTOR_META] 메타데이터 요약 생성")
            metadata_summary = self._summarize_metadata(metadatas)
            self.logger.info(f"📋 [VECTOR_META] 메타데이터 요약: {list(metadata_summary.keys()) if metadata_summary else 'None'}")
            
            return {
                "success": True,
                "query": query,
                "found_documents": len(documents),
                "documents": documents[:5],  # 상위 5개 문서만 반환
                "chart_data": chart_data,
                "metadata_summary": metadata_summary
            }
            
        except Exception as e:
            self.logger.error(f"❌ [VECTOR_ERROR] 벡터 검색 실패: {str(e)}")
            return {"error": f"검색 중 오류 발생: {str(e)}"}
    
    def _extract_chart_data_from_metadata(self, metadatas: List[Dict], query: str) -> Dict[str, Any]:
        """메타데이터에서 차트 데이터 추출"""
        try:
            # 쿼리 분석하여 차트 타입 추정
            query_lower = query.lower()
            
            # 데이터 타입별 분류
            inbound_data = [m for m in metadatas if m.get('type') == 'inbound']
            outbound_data = [m for m in metadatas if m.get('type') == 'outbound']
            product_data = [m for m in metadatas if m.get('type') == 'product']
            
            chart_data = {}
            
            # 입고/공급업체 관련 쿼리 (확장된 키워드)
            inbound_keywords = ['입고', '공급업체', 'inbound', 'supplier', '납품업체', '업체', '공급', 
                              'inboundline', 'inboundposition', '입고라인', '입고위치', 'pallete']
            if any(word in query_lower for word in inbound_keywords):
                if inbound_data:
                    chart_data.update(self._process_inbound_chart_data(inbound_data, query_lower))
            
            # 출고/고객 관련 쿼리 (확장된 키워드)
            outbound_keywords = ['출고', '고객', 'outbound', 'customer', 'business name', '고객사',
                               'outboundline', 'productposition', '출고라인', '출고위치']
            if any(word in query_lower for word in outbound_keywords):
                if outbound_data:
                    chart_data.update(self._process_outbound_chart_data(outbound_data, query_lower))
            
            # 재고/상품/랙 관련 쿼리 (확장된 키워드)
            product_keywords = ['재고', '상품', '제품', '랙', 'inventory', 'product', 'rack', 'productcode', 
                              'productname', 'rack name', 'unit', 'start pallete qty', '상품코드', '제품코드', 
                              '랙명', '랙위치', '단위', '시작재고']
            if any(word in query_lower for word in product_keywords):
                if product_data:
                    chart_data.update(self._process_product_chart_data(product_data, query_lower))
            
            # 전체 데이터가 필요한 경우
            if not chart_data and metadatas:
                chart_data = self._process_general_chart_data(metadatas, query_lower)
            
            return chart_data
            
        except Exception as e:
            self.logger.error(f"❌ 차트 데이터 추출 실패: {str(e)}")
            return {}
    
    def _process_inbound_chart_data(self, inbound_data: List[Dict], query: str) -> Dict[str, Any]:
        """입고 데이터로 차트 데이터 생성"""
        if any(word in query for word in ['공급업체', 'supplier', '납품업체', '업체', '공급']):
            # 공급업체별 집계
            supplier_counts = {}
            for item in inbound_data:
                supplier = item.get('supplier', '알 수 없음')
                quantity = item.get('quantity', 0)
                supplier_counts[supplier] = supplier_counts.get(supplier, 0) + quantity
            
            # 상위 10개 공급업체로 정렬
            sorted_suppliers = sorted(supplier_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "labels": [item[0] for item in sorted_suppliers],
                "data": [item[1] for item in sorted_suppliers],
                "title": "주요 공급업체별 입고량 (상위 10개)",
                "type": "inbound_by_supplier",
                "total_suppliers": len(supplier_counts),
                "top_supplier": sorted_suppliers[0] if sorted_suppliers else None
            }
        
        elif '날짜' in query or '일별' in query or 'daily' in query:
            # 날짜별 집계
            date_counts = {}
            for item in inbound_data:
                date = item.get('date', '알 수 없음')
                quantity = item.get('quantity', 0)
                date_counts[date] = date_counts.get(date, 0) + quantity
            
            return {
                "labels": list(date_counts.keys()),
                "data": list(date_counts.values()),
                "title": "일별 입고량",
                "type": "inbound_by_date"
            }
        
        return {}
    
    def _process_outbound_chart_data(self, outbound_data: List[Dict], query: str) -> Dict[str, Any]:
        """출고 데이터로 차트 데이터 생성"""
        if any(word in query for word in ['고객', 'customer', 'business', '고객사', 'business name']):
            # 고객사별 집계
            business_counts = {}
            for item in outbound_data:
                business = item.get('business_name', '알 수 없음')
                quantity = item.get('quantity', 0)
                business_counts[business] = business_counts.get(business, 0) + quantity
            
            # 상위 10개 고객사로 정렬
            sorted_businesses = sorted(business_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "labels": [item[0] for item in sorted_businesses],
                "data": [item[1] for item in sorted_businesses],
                "title": "주요 고객사별 출고량 (상위 10개)",
                "type": "outbound_by_business",
                "total_customers": len(business_counts),
                "top_customer": sorted_businesses[0] if sorted_businesses else None
            }
        
        elif any(word in query for word in ['상품', 'product', 'productname', 'productcode', '제품']):
            # 상품별 집계
            product_counts = {}
            for item in outbound_data:
                product = item.get('product_name', '알 수 없음')
                quantity = item.get('quantity', 0)
                product_counts[product] = product_counts.get(product, 0) + quantity
            
            # 상위 10개 상품으로 정렬
            sorted_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "labels": [item[0] for item in sorted_products],
                "data": [item[1] for item in sorted_products],
                "title": "주요 출고 상품 (상위 10개)",
                "type": "outbound_by_product",
                "total_products": len(product_counts),
                "top_product": sorted_products[0] if sorted_products else None
            }
        
        elif any(word in query for word in ['날짜', '일별', 'daily', 'date', '기간']):
            # 날짜별 집계
            date_counts = {}
            for item in outbound_data:
                date = item.get('date', '알 수 없음')
                quantity = item.get('quantity', 0)
                date_counts[date] = date_counts.get(date, 0) + quantity
            
            return {
                "labels": list(date_counts.keys()),
                "data": list(date_counts.values()),
                "title": "일별 출고량",
                "type": "outbound_by_date"
            }
        
        return {}
    
    def _process_product_chart_data(self, product_data: List[Dict], query: str) -> Dict[str, Any]:
        """상품 데이터로 차트 데이터 생성"""
        if any(word in query for word in ['랙', 'rack', 'rack name', '랙명', '랙위치', '위치']):
            # 랙별 집계
            rack_counts = {}
            for item in product_data:
                rack = item.get('rack_name', '알 수 없음')
                stock = item.get('current_stock', 0)
                rack_counts[rack] = rack_counts.get(rack, 0) + stock
            
            # 랙별 정렬 (알파벳 순)
            sorted_racks = sorted(rack_counts.items())
            
            return {
                "labels": [item[0] for item in sorted_racks],
                "data": [item[1] for item in sorted_racks],
                "title": "랙별 재고량",
                "type": "inventory_by_rack",
                "total_racks": len(rack_counts)
            }
        
        elif any(word in query for word in ['상품', 'product', 'productname', 'productcode', '제품', '품목']):
            # 상품별 재고량 집계
            product_counts = {}
            for item in product_data:
                product = item.get('product_name', '알 수 없음')
                stock = item.get('current_stock', 0)
                product_counts[product] = stock  # 재고는 합계가 아닌 개별 값
            
            # 상위 10개 상품으로 정렬
            sorted_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "labels": [item[0] for item in sorted_products],
                "data": [item[1] for item in sorted_products],
                "title": "상품별 재고량 (상위 10개)",
                "type": "inventory_by_product",
                "total_products": len(product_counts)
            }
        
        elif any(word in query for word in ['unit', '단위', 'box', 'pac', 'kg', 'ea']):
            # 단위별 집계
            unit_counts = {}
            for item in product_data:
                unit = item.get('unit', '알 수 없음')
                unit_counts[unit] = unit_counts.get(unit, 0) + 1
            
            return {
                "labels": list(unit_counts.keys()),
                "data": list(unit_counts.values()),
                "title": "단위별 상품 개수",
                "type": "products_by_unit"
            }
        
        return {}
    
    def _process_general_chart_data(self, metadatas: List[Dict], query: str) -> Dict[str, Any]:
        """일반적인 차트 데이터 생성"""
        # 데이터 타입별 개수 집계
        type_counts = {}
        for item in metadatas:
            data_type = item.get('type', '알 수 없음')
            type_counts[data_type] = type_counts.get(data_type, 0) + 1
        
        return {
            "labels": ["입고", "출고", "상품"],
            "data": [
                type_counts.get('inbound', 0),
                type_counts.get('outbound', 0),
                type_counts.get('product', 0)
            ],
            "title": "데이터 유형별 분포",
            "type": "general_overview"
        }
    
    def _summarize_metadata(self, metadatas: List[Dict]) -> Dict[str, Any]:
        """메타데이터 요약"""
        summary = {
            "total_records": len(metadatas),
            "data_types": {},
            "date_range": {"min": None, "max": None},
            "quantity_stats": {"min": 0, "max": 0, "total": 0}
        }
        
        quantities = []
        dates = []
        
        for item in metadatas:
            # 데이터 타입 집계
            data_type = item.get('type', 'unknown')
            summary["data_types"][data_type] = summary["data_types"].get(data_type, 0) + 1
            
            # 수량 통계
            quantity = item.get('quantity', 0)
            if quantity > 0:
                quantities.append(quantity)
            
            # 날짜 수집
            date_str = item.get('date', '')
            if date_str and date_str != '':
                dates.append(date_str)
        
        # 수량 통계 계산
        if quantities:
            summary["quantity_stats"] = {
                "min": min(quantities),
                "max": max(quantities),
                "total": sum(quantities),
                "average": sum(quantities) / len(quantities)
            }
        
        # 날짜 범위 계산
        if dates:
            summary["date_range"] = {
                "min": min(dates),
                "max": max(dates),
                "unique_dates": len(set(dates))
            }
        
        return summary
    
    def get_status(self) -> Dict[str, Any]:
        """벡터 데이터베이스 상태 반환"""
        if not self.is_initialized:
            return {
                "status": "not_initialized",
                "message": "벡터 데이터베이스가 초기화되지 않았습니다."
            }
        
        try:
            count = self.collection.count()
            encoder_name = "ko-sroberta-multitask" if hasattr(self.encoder, 'model_name') else "unknown"
            
            return {
                "status": "ready",
                "document_count": count,
                "collection_name": self.collection.name,
                "encoder_model": encoder_name,
                "is_initialized": self.is_initialized,
                "collection_exists": self.collection is not None
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }