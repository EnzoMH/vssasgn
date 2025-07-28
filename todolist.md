# Smart Warehouse Management System - 진행 상황 To-Do 리스트

## 📋 프로젝트 개요

- **프로젝트명**: Smart Warehouse Management System (V)
- **목표**: 실제 물류센터에서 사용 가능한 AI 기반 창고관리 대시보드 (V - 핵심 기능 구현 완료, 고급 기능 예정)
- **기술스택**: React + TypeScript + FastAPI + Gemini + XGBoost + K-means (V - 기본 스택 구성 완료)

## 🚀 단계별 구현 계획

### Phase 1: 핵심 기능 ⭐

#### 1.1 React 대시보드 구축

- React 프로젝트 초기화 (△ - 수동 파일 생성으로 대체, 기능 동등)
- npm 패키지 설치 (recharts, lucide-react, axios, tailwindcss, react-dropzone) (V)

**구현 컴포넌트**:

- `Dashboard.tsx` - 메인 대시보드 (V)
- `InventoryChart.tsx` - 랙별 재고 현황 (V)
- `TrendChart.tsx` - 일별 입출고 트렌드 (V)
- `KPICards.tsx` - 핵심 지표 카드 (V)
- `AIChat.tsx` - AI 질의응답 채팅 (V)
- `ProductCategoryChart.tsx` - 제품 카테고리별 분포 파이차트 (V)
- `FileUpload.tsx` - 파일 업로드 UI (V)

#### 1.2 FastAPI 백엔드 구축

- 백엔드 프로젝트 구조 생성 (`backend/` 디렉토리 및 하위 폴더) (V)
- Python 패키지 설치 (fastapi, uvicorn, pandas, scikit-learn, xgboost, openai, python-multipart) (V)

**API 엔드포인트**:

- `GET /api/dashboard/kpi` (V)
- `GET /api/inventory/by-rack` (V)
- `GET /api/trends/daily` (V)
- `GET /api/product/category-distribution` (V)
- `POST /api/ai/chat` (V)
- `POST /api/predict/demand` (V)
- `POST /api/upload/data` (V - 업로드 기능 구현, 데이터 처리/저장 로직은 △)
- `POST /api/product/cluster` (V)
- `GET /api/analysis/anomalies` (V)

#### 1.3 기본 데이터 시각화

- 랙별 입출고 현황 (막대차트) (V)
- 일별 물동량 트렌드 (라인차트) (V)
- 제품 카테고리별 분포 (파이차트) (V)
- KPI 대시보드 (카드 형태) (V)

### Phase 2: AI 기능 추가 🤖

#### 2.1 LLM 연동 구현

- `backend/app/services/ai_service.py` (`WarehouseAI` 클래스) (V - Gemini 기반, 다중 API 키, Rate Limiter 통합)
- `backend/app/utils/ai_chat.py` (`WarehouseChatbot` 클래스) (V - `WarehouseAI` 및 `DataService` 연동)
- **지원할 질의 예시 구현 (예: "어제 A랙 입고량이 얼마야?")**: (△ - 기본적인 의도 분석은 가능하나, 복합 질의 응답을 위한 `DataService` 연동 및 LLM 프롬프트 구성 심화 필요)

#### 2.2 ML 모델 구현

- `backend/app/models/ml_models.py` (`DemandPredictor` 클래스) (V)
- `backend/app/models/ml_models.py` (`ProductClusterer` 클래스) (V)
- `backend/app/models/ml_models.py` (`AnomalyDetector` 클래스) (V)
- 수요 예측 모델 학습 및 추론 로직 (V - `main.py`에 포함, 현재는 더미 데이터 기반)
- 제품 클러스터링 모델 학습 및 추론 로직 (V - `main.py`에 포함, 현재는 더미 데이터 기반)
- 이상 탐지 모델 학습 및 추론 로직 (V - `main.py` 및 `data_analysis_service.py`에 포함)

#### 2.3 파일 업로드 및 분석

- CSV/Excel 파일 드래그앤드롭 (V - `FileUpload.tsx`)
- 자동 데이터 프로파일링 (X)
- AI 기반 인사이트 추출 (V - CMD 상에서 `analyze_data.py`를 통해 구현)

### Phase 3: 고급 기능 (선택사항) 🔥

- CAD 파일 처리 (X)
- 멀티모달 AI (X)
- 3D 시각화 (X)

## 💻 구체적 구현 가이드

- 프로젝트 구조 (V - 가이드에 따라 `frontend/`, `backend/` 구성)
- 핵심 컴포넌트 코드 예시 (V - `Dashboard.tsx`, FastAPI `main.py` 구조)
- 데이터 처리 파이프라인 (`DataService`로 구현) (V)
- AI 챗봇 구현 (`WarehouseChatbot`, `WarehouseAI`로 구현) (V)

## 🎨 UI/UX 디자인 가이드

- 색상 팔레트 (V - `tailwind.config.js`에 적용)
- 컴포넌트 스타일 (V - Tailwind CSS 클래스 및 `index.css` `@apply` 적용)
- 반응형 그리드 (V - Tailwind CSS 클래스 적용)

## 🚀 배포 및 실행 가이드

- 개발 환경 실행 (△ - 설정은 완료되었으나, 실제 실행 및 검증은 다음 단계)

## 💡 추가 개선 아이디어

- 알림 시스템 (재고 부족 경고) (△)
- 엑셀 리포트 자동 생성 (△)
- 모바일 앱 지원 (△)
- IoT 센서 연동 (△)
- 로봇 제어 시스템 (△)
- 블록체인 기반 이력 관리 (△)
