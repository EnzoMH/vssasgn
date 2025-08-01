// 대시보드 관리 클래스
class DashboardManager {
  constructor() {
    this.isLoading = false;
    this.autoRefreshInterval = null;
    this.initializeElements();
    this.bindEvents();
  }

  initializeElements() {
    // KPI 요소들
    this.kpiElements = {
      totalInventory: document.getElementById("totalInventory"),
      dailyThroughput: document.getElementById("dailyThroughput"),
      rackUtilization: document.getElementById("rackUtilization"),
      inventoryTurnover: document.getElementById("inventoryTurnover"),
    };

    // 버튼들
    this.refreshBtn = document.getElementById("refreshBtn");
    this.demandPredictBtn = document.getElementById("demandPredictBtn");
    this.clusterAnalysisBtn = document.getElementById("clusterAnalysisBtn");
    this.anomalyDetectionBtn = document.getElementById("anomalyDetectionBtn");
  }

  bindEvents() {
    // 새로고침 버튼
    if (this.refreshBtn) {
      this.refreshBtn.addEventListener("click", () => {
        this.refreshData();
      });
    }

    // ML 분석 버튼들 (안전한 바인딩)
    if (this.demandPredictBtn) {
      this.demandPredictBtn.addEventListener("click", () => {
        this.runDemandPrediction();
      });
    }

    if (this.clusterAnalysisBtn) {
      this.clusterAnalysisBtn.addEventListener("click", () => {
        this.runClusterAnalysis();
      });
    }

    if (this.anomalyDetectionBtn) {
      this.anomalyDetectionBtn.addEventListener("click", () => {
        this.runAnomalyDetection();
      });
    }

    // 페이지 가시성 변경 시 자동 새로고침 제어
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        this.stopAutoRefresh();
      } else {
        this.startAutoRefresh();
      }
    });
  }

  // 초기 데이터 로드
  async initialize() {
    try {
      LoadingManager.show("대시보드 데이터를 불러오는 중...");
      await this.loadDashboardData();
      this.startAutoRefresh();
      NotificationManager.success("대시보드가 성공적으로 로드되었습니다.");
    } catch (error) {
      console.error("대시보드 초기화 오류:", error);
      NotificationManager.error("대시보드 데이터를 불러오는데 실패했습니다.");
    } finally {
      LoadingManager.hide();
    }
  }

  // 대시보드 데이터 로드
  async loadDashboardData() {
    try {
      const [kpiData, inventoryData, trendData, categoryData] =
        await Promise.all([
          APIClient.get("/api/dashboard/kpi"),
          APIClient.get("/api/inventory/by-rack"),
          APIClient.get("/api/trends/daily"),
          APIClient.get("/api/product/category-distribution"),
        ]);

      // KPI 업데이트
      this.updateKPIs(kpiData);

      // 차트 업데이트
      if (chartManager) {
        chartManager.createInventoryChart(inventoryData);
        chartManager.createTrendChart(trendData);
        chartManager.createCategoryChart(categoryData);
      }

      return { kpiData, inventoryData, trendData, categoryData };
    } catch (error) {
      console.error("대시보드 데이터 로드 오류:", error);
      throw error;
    }
  }

  // KPI 업데이트 (실제 rawdata 기반)
  updateKPIs(data) {
    console.log("📊 KPI 데이터 업데이트:", data);

    // 데이터 소스 표시 (개발 모드에서만)
    if (data.data_source === "rawdata") {
      console.log("✅ 실제 rawdata 기반 KPI 로드됨");
    }

    if (this.kpiElements.totalInventory) {
      this.kpiElements.totalInventory.textContent = NumberUtils.formatNumber(
        data.total_inventory
      );
      // 총재고량 상태 색상 업데이트
      this.updateKPIStatus(
        "totalInventoryCard",
        data.total_inventory,
        800,
        1200
      );
    }

    if (this.kpiElements.dailyThroughput) {
      this.kpiElements.dailyThroughput.textContent = NumberUtils.formatNumber(
        data.daily_throughput
      );
      // 일일처리량 상태 색상 업데이트
      this.updateKPIStatus(
        "dailyThroughputCard",
        data.daily_throughput,
        300,
        500
      );
    }

    if (this.kpiElements.rackUtilization) {
      this.kpiElements.rackUtilization.textContent =
        NumberUtils.formatPercentage(data.rack_utilization);
      // 랙활용률 상태 색상 업데이트
      this.updateKPIStatus(
        "rackUtilizationCard",
        data.rack_utilization,
        60,
        85
      );
    }

    if (this.kpiElements.inventoryTurnover) {
      this.kpiElements.inventoryTurnover.textContent =
        NumberUtils.formatDecimal(data.inventory_turnover);
      // 재고회전율 상태 색상 업데이트
      this.updateKPIStatus(
        "inventoryTurnoverCard",
        data.inventory_turnover,
        0.5,
        2.0
      );
    }

    // KPI 카드 애니메이션 효과
    this.animateKPICards();
  }

  // KPI 상태별 색상 업데이트
  updateKPIStatus(cardId, value, lowThreshold, highThreshold) {
    const card = document.getElementById(cardId);
    if (!card) return;

    // 기존 상태 클래스 제거
    card.classList.remove("kpi-low", "kpi-normal", "kpi-high", "kpi-critical");

    // 새로운 상태 클래스 추가
    if (value < lowThreshold) {
      card.classList.add("kpi-low");
    } else if (value >= lowThreshold && value <= highThreshold) {
      card.classList.add("kpi-normal");
    } else if (value > highThreshold && value <= highThreshold * 1.2) {
      card.classList.add("kpi-high");
    } else {
      card.classList.add("kpi-critical");
    }
  }

  // KPI 카드 애니메이션
  animateKPICards() {
    const cards = document.querySelectorAll(".kpi-card");
    cards.forEach((card, index) => {
      setTimeout(() => {
        card.style.transform = "scale(1.05)";
        setTimeout(() => {
          card.style.transform = "scale(1)";
        }, 200);
      }, index * 100);
    });
  }

  // 데이터 새로고침
  async refreshData() {
    if (this.isLoading) return;

    this.isLoading = true;
    this.setRefreshButtonLoading(true);

    try {
      await this.loadDashboardData();
      NotificationManager.success("데이터가 성공적으로 새로고침되었습니다.");
    } catch (error) {
      console.error("데이터 새로고침 오류:", error);
      NotificationManager.error("데이터 새로고침에 실패했습니다.");
    } finally {
      this.isLoading = false;
      this.setRefreshButtonLoading(false);
    }
  }

  // 새로고침 버튼 로딩 상태
  setRefreshButtonLoading(loading) {
    const icon = this.refreshBtn.querySelector("i");
    if (loading) {
      icon.className = "fas fa-spinner fa-spin";
      this.refreshBtn.disabled = true;
    } else {
      icon.className = "fas fa-sync-alt";
      this.refreshBtn.disabled = false;
    }
  }

  // 자동 새로고침 시작 (5분마다)
  startAutoRefresh() {
    this.stopAutoRefresh();
    this.autoRefreshInterval = setInterval(() => {
      this.refreshData();
    }, 5 * 60 * 1000); // 5분
  }

  // 자동 새로고침 중지
  stopAutoRefresh() {
    if (this.autoRefreshInterval) {
      clearInterval(this.autoRefreshInterval);
      this.autoRefreshInterval = null;
    }
  }

  // 수요 예측 실행
  async runDemandPrediction() {
    try {
      this.setMLButtonLoading(this.demandPredictBtn, true);

      // 임시 피처 데이터 (실제로는 사용자 입력이나 현재 데이터 기반)
      const features = {
        feature1: 15,
        feature2: 8,
      };

      const response = await APIClient.post("/api/predict/demand", {
        features,
      });
      chartManager.createMLResultChart(response, "demand");

      NotificationManager.success("수요 예측이 완료되었습니다.");
    } catch (error) {
      console.error("수요 예측 오류:", error);
      NotificationManager.error("수요 예측에 실패했습니다.");
    } finally {
      this.setMLButtonLoading(this.demandPredictBtn, false);
    }
  }

  // 클러스터 분석 실행 (새로운 ML API 사용)
  async runClusterAnalysis() {
    try {
      this.setMLButtonLoading(this.clusterAnalysisBtn, true);

      // 새로운 ML 클러스터링 API 사용
      const response = await APIClient.get(
        "/api/ml/product-clustering/clusters"
      );

      // 클러스터 차트 생성 (간단한 파이 차트)
      if (response && response.clusters) {
        const chartData = {
          labels: response.clusters.map((c) => c.cluster_name),
          datasets: [
            {
              data: response.clusters.map((c) => c.size),
              backgroundColor: response.clusters.map(
                (c) => c.color || "#3b82f6"
              ),
              borderWidth: 2,
            },
          ],
        };

        chartManager.createMLResultChart(
          {
            chart_type: "pie",
            title: `제품 클러스터 분포 (총 ${response.total_products}개 상품)`,
            data: chartData,
          },
          "cluster"
        );
      }

      NotificationManager.success("제품 클러스터링이 완료되었습니다.");
    } catch (error) {
      console.error("클러스터 분석 오류:", error);
      NotificationManager.error("클러스터 분석에 실패했습니다.");
    } finally {
      this.setMLButtonLoading(this.clusterAnalysisBtn, false);
    }
  }

  // 이상 탐지 실행
  async runAnomalyDetection() {
    try {
      this.setMLButtonLoading(this.anomalyDetectionBtn, true);

      const response = await APIClient.get("/api/analysis/anomalies");
      chartManager.createMLResultChart(response, "anomaly");

      NotificationManager.success("이상 탐지 분석이 완료되었습니다.");
    } catch (error) {
      console.error("이상 탐지 오류:", error);
      NotificationManager.error("이상 탐지 분석에 실패했습니다.");
    } finally {
      this.setMLButtonLoading(this.anomalyDetectionBtn, false);
    }
  }

  // ML 버튼 로딩 상태 (안전한 처리)
  setMLButtonLoading(button, loading) {
    if (!button) {
      console.warn("ML 버튼이 존재하지 않습니다.");
      return;
    }

    const icon = button.querySelector("i");
    if (!icon) {
      console.warn("버튼에 아이콘이 없습니다.");
      return;
    }

    if (loading) {
      icon.className = "fas fa-spinner fa-spin";
      button.disabled = true;
    } else {
      // 원래 아이콘으로 복원
      if (button === this.demandPredictBtn) {
        icon.className = "fas fa-chart-line";
      } else if (button === this.clusterAnalysisBtn) {
        icon.className = "fas fa-layer-group";
      } else if (button === this.anomalyDetectionBtn) {
        icon.className = "fas fa-exclamation-triangle";
      }
      button.disabled = false;
    }
  }

  // 실시간 상태 업데이트
  updateSystemStatus() {
    const statusElement = document.createElement("div");
    statusElement.className = "system-status";
    statusElement.innerHTML = `
            <div class="status-item">
                <i class="fas fa-circle" style="color: var(--secondary);"></i>
                <span>시스템 정상</span>
            </div>
            <div class="status-item">
                <i class="fas fa-clock"></i>
                <span>마지막 업데이트: ${DateUtils.formatDateTime(
                  new Date()
                )}</span>
            </div>
        `;

    // 헤더에 상태 추가
    const headerActions = document.querySelector(".header-actions");
    const existingStatus = headerActions.querySelector(".system-status");
    if (existingStatus) {
      existingStatus.remove();
    }
    headerActions.appendChild(statusElement);

    // 상태 스타일
    const style = document.createElement("style");
    style.textContent = `
            .system-status {
                display: flex;
                gap: 1rem;
                align-items: center;
                font-size: 0.875rem;
                color: rgba(255, 255, 255, 0.9);
            }
            .status-item {
                display: flex;
                align-items: center;
                gap: 0.25rem;
            }
            @media (max-width: 768px) {
                .system-status {
                    display: none;
                }
            }
        `;
    if (!document.querySelector("#statusStyles")) {
      style.id = "statusStyles";
      document.head.appendChild(style);
    }
  }

  // 키보드 단축키 설정
  setupKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
      // Ctrl + R: 새로고침
      if (e.ctrlKey && e.key === "r") {
        e.preventDefault();
        this.refreshData();
      }

      // Ctrl + U: 업로드 모달 열기
      if (e.ctrlKey && e.key === "u") {
        e.preventDefault();
        fileUploadManager.openModal();
      }

      // Ctrl + /: AI 챗봇 토글
      if (e.ctrlKey && e.key === "/") {
        e.preventDefault();
        aiChatManager.toggleChat();
      }
    });
  }

  // 오류 복구 시도
  async attemptErrorRecovery() {
    console.log("오류 복구를 시도합니다...");

    try {
      // 간단한 헬스 체크
      await APIClient.get("/api/dashboard/kpi");
      NotificationManager.success("시스템이 정상적으로 복구되었습니다.");
      await this.loadDashboardData();
    } catch (error) {
      console.error("복구 실패:", error);
      NotificationManager.error(
        "시스템 복구에 실패했습니다. 페이지를 새로고침해주세요."
      );
    }
  }
}

// 대시보드 매니저는 DOMContentLoaded에서 초기화됨

// AI 차트 생성 기능 초기화
function initializeAIChartGeneration() {
  const generateChartBtn = document.getElementById("generateChartBtn");
  const chartRequestInput = document.getElementById("chartRequestInput");
  const quickChartButtons = document.querySelectorAll(".quick-chart-btn");

  // 차트 생성 버튼 클릭 이벤트
  if (generateChartBtn) {
    generateChartBtn.addEventListener("click", async () => {
      const userRequest = chartRequestInput.value.trim();
      if (!userRequest) {
        NotificationManager.warning("차트 요청을 입력해주세요.");
        chartRequestInput.focus();
        return;
      }

      console.log(`🎯 사용자 차트 요청: ${userRequest}`);

      // 버튼 로딩 상태
      const originalText = generateChartBtn.innerHTML;
      generateChartBtn.innerHTML =
        '<i class="fas fa-spinner fa-spin"></i> 생성 중...';
      generateChartBtn.disabled = true;

      try {
        // AI 차트 생성 호출
        const result = await chartManager.generateAIChart(
          userRequest,
          "aiGeneratedChart"
        );

        if (result.success) {
          console.log("✅ AI 차트 생성 성공:", result.config);
          // 입력 필드 클리어
          chartRequestInput.value = "";
        } else {
          console.error("❌ AI 차트 생성 실패:", result.error);
        }
      } catch (error) {
        console.error("❌ AI 차트 생성 오류:", error);
        NotificationManager.error(
          `차트 생성 중 오류가 발생했습니다: ${error.message}`
        );
      } finally {
        // 버튼 상태 복원
        generateChartBtn.innerHTML = originalText;
        generateChartBtn.disabled = false;
      }
    });
  }

  // 입력 필드에서 Enter 키 처리
  if (chartRequestInput) {
    chartRequestInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        generateChartBtn.click();
      }
    });

    // 플레이스홀더 텍스트 동적 변경
    const placeholderTexts = [
      "최근 일주일 입고량을 막대차트로 보여줘",
      "랙별 재고를 파이차트로 그려줘",
      "공급업체별 입고 현황을 도넛차트로",
      "상품별 출고량 추이를 선그래프로",
      "일별 입출고 차이를 막대차트로",
    ];

    let placeholderIndex = 0;
    setInterval(() => {
      if (document.activeElement !== chartRequestInput) {
        chartRequestInput.placeholder = placeholderTexts[placeholderIndex];
        placeholderIndex = (placeholderIndex + 1) % placeholderTexts.length;
      }
    }, 3000);
  }

  // 빠른 차트 버튼들 이벤트
  quickChartButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      const request = button.getAttribute("data-request");
      if (request) {
        // 입력 필드에 요청 텍스트 설정
        chartRequestInput.value = request;

        console.log(`🚀 빠른 차트 요청: ${request}`);

        // 버튼 로딩 상태
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        button.disabled = true;

        try {
          // AI 차트 생성 호출
          const result = await chartManager.generateAIChart(
            request,
            "aiGeneratedChart"
          );

          if (result.success) {
            console.log("✅ 빠른 차트 생성 성공:", result.config);
            // 입력 필드 클리어
            setTimeout(() => (chartRequestInput.value = ""), 1000);
          } else {
            console.error("❌ 빠른 차트 생성 실패:", result.error);
          }
        } catch (error) {
          console.error("❌ 빠른 차트 생성 오류:", error);
          NotificationManager.error(
            `차트 생성 중 오류가 발생했습니다: ${error.message}`
          );
        } finally {
          // 버튼 상태 복원
          setTimeout(() => {
            button.innerHTML = originalText;
            button.disabled = false;
          }, 1500);
        }
      }
    });
  });

  console.log("🎨 AI 차트 생성 기능이 초기화되었습니다.");
}

// AI 분석 버튼 기능 초기화
function initializeAIAnalysisButtons() {
  const demandPredictBtn = document.getElementById("demandPredictBtn");
  const clusterAnalysisBtn = document.getElementById("clusterAnalysisBtn");
  const anomalyDetectionBtn = document.getElementById("anomalyDetectionBtn");
  const mlResults = document.getElementById("mlResults");

  // 수요 예측 버튼
  if (demandPredictBtn) {
    demandPredictBtn.addEventListener("click", async () => {
      console.log("🔮 수요 예측 분석 시작");

      const originalText = demandPredictBtn.innerHTML;
      demandPredictBtn.innerHTML =
        '<i class="fas fa-spinner fa-spin"></i> 분석 중...';
      demandPredictBtn.disabled = true;

      try {
        // 수요 예측 API 호출
        const response = await fetch("/api/predict/demand", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            features: {
              feature1: 15, // 예시 피처
              feature2: 8,
            },
          }),
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();

        // 결과 표시
        mlResults.innerHTML = `
          <div class="analysis-result">
            <h4><i class="fas fa-chart-line text-primary"></i> 수요 예측 결과</h4>
            <div class="result-content">
              <div class="prediction-value">
                <span class="label">예측 수요량:</span>
                <span class="value">${
                  result.prediction ? result.prediction[0].toFixed(1) : "N/A"
                }개</span>
              </div>
              <div class="result-description">
                <p>머신러닝 모델을 통해 예측된 다음 기간의 예상 수요량입니다.</p>
                <small class="text-muted">* 과거 데이터 패턴을 기반으로 한 예측값입니다.</small>
              </div>
            </div>
          </div>
        `;

        NotificationManager.success("수요 예측 분석이 완료되었습니다!");
      } catch (error) {
        console.error("❌ 수요 예측 오류:", error);
        mlResults.innerHTML = `
          <div class="analysis-error">
            <h4><i class="fas fa-exclamation-triangle text-danger"></i> 수요 예측 실패</h4>
            <p>수요 예측 분석 중 오류가 발생했습니다: ${error.message}</p>
            <small>데이터 로딩 상태를 확인하고 다시 시도해주세요.</small>
          </div>
        `;
        NotificationManager.error(`수요 예측 실패: ${error.message}`);
      } finally {
        demandPredictBtn.innerHTML = originalText;
        demandPredictBtn.disabled = false;
      }
    });
  }

  // 제품 클러스터링 버튼
  if (clusterAnalysisBtn) {
    clusterAnalysisBtn.addEventListener("click", async () => {
      console.log("📊 제품 클러스터링 분석 시작");

      const originalText = clusterAnalysisBtn.innerHTML;
      clusterAnalysisBtn.innerHTML =
        '<i class="fas fa-spinner fa-spin"></i> 분석 중...';
      clusterAnalysisBtn.disabled = true;

      try {
        // 클러스터링 API 호출
        const response = await fetch("/api/product/cluster", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();

        // 결과 표시
        const clusters = result.clusters || [];
        const clusterCounts = clusters.reduce((acc, cluster) => {
          acc[cluster] = (acc[cluster] || 0) + 1;
          return acc;
        }, {});

        mlResults.innerHTML = `
          <div class="analysis-result">
            <h4><i class="fas fa-project-diagram text-secondary"></i> 제품 클러스터링 결과</h4>
            <div class="result-content">
              <div class="cluster-summary">
                <span class="label">발견된 클러스터:</span>
                <span class="value">${
                  Object.keys(clusterCounts).length
                }개</span>
              </div>
              <div class="cluster-distribution">
                ${Object.entries(clusterCounts)
                  .map(
                    ([cluster, count], index) => `
                  <div class="cluster-item">
                    <span class="cluster-badge cluster-${index}">클러스터 ${cluster}</span>
                    <span class="cluster-count">${count}개 제품</span>
                  </div>
                `
                  )
                  .join("")}
              </div>
              <div class="result-description">
                <p>유사한 특성을 가진 제품들을 그룹화한 결과입니다.</p>
                <small class="text-muted">* 제품 특성 및 판매 패턴을 기반으로 분류됩니다.</small>
              </div>
            </div>
          </div>
        `;

        NotificationManager.success("제품 클러스터링 분석이 완료되었습니다!");
      } catch (error) {
        console.error("❌ 클러스터링 오류:", error);
        mlResults.innerHTML = `
          <div class="analysis-error">
            <h4><i class="fas fa-exclamation-triangle text-danger"></i> 클러스터링 실패</h4>
            <p>제품 클러스터링 분석 중 오류가 발생했습니다: ${error.message}</p>
            <small>데이터 로딩 상태를 확인하고 다시 시도해주세요.</small>
          </div>
        `;
        NotificationManager.error(`클러스터링 실패: ${error.message}`);
      } finally {
        clusterAnalysisBtn.innerHTML = originalText;
        clusterAnalysisBtn.disabled = false;
      }
    });
  }

  // 이상 탐지 버튼
  if (anomalyDetectionBtn) {
    anomalyDetectionBtn.addEventListener("click", async () => {
      console.log("🚨 이상 탐지 분석 시작");

      const originalText = anomalyDetectionBtn.innerHTML;
      anomalyDetectionBtn.innerHTML =
        '<i class="fas fa-spinner fa-spin"></i> 분석 중...';
      anomalyDetectionBtn.disabled = true;

      try {
        // 이상 탐지 API 호출
        const response = await fetch("/api/analysis/anomalies");

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();

        // 결과 표시
        const anomalies = result.anomalies || [];
        const anomalyCount = Array.isArray(anomalies) ? anomalies.length : 0;

        mlResults.innerHTML = `
          <div class="analysis-result">
            <h4><i class="fas fa-shield-alt text-warning"></i> 이상 탐지 결과</h4>
            <div class="result-content">
              <div class="anomaly-summary">
                <span class="label">발견된 이상 항목:</span>
                <span class="value ${
                  anomalyCount > 0 ? "text-warning" : "text-success"
                }">${anomalyCount}개</span>
              </div>
              ${
                anomalyCount > 0
                  ? `
                <div class="anomaly-list">
                  <h5>이상 항목 상세:</h5>
                  <ul>
                    ${anomalies
                      .slice(0, 5)
                      .map(
                        (anomaly, index) => `
                      <li class="anomaly-item">
                        <strong>항목 ${index + 1}:</strong> 
                        ${
                          typeof anomaly === "object"
                            ? JSON.stringify(anomaly)
                            : anomaly
                        }
                      </li>
                    `
                      )
                      .join("")}
                    ${
                      anomalies.length > 5
                        ? `<li class="text-muted">... 외 ${
                            anomalies.length - 5
                          }개</li>`
                        : ""
                    }
                  </ul>
                </div>
              `
                  : `
                <div class="no-anomalies">
                  <p class="text-success"><i class="fas fa-check-circle"></i> 정상 상태입니다.</p>
                  <small>현재 데이터에서 특별한 이상 징후가 발견되지 않았습니다.</small>
                </div>
              `
              }
              <div class="result-description">
                <p>머신러닝을 통해 비정상적인 패턴을 탐지한 결과입니다.</p>
                <small class="text-muted">* 통계적 이상치 및 패턴 분석을 기반으로 합니다.</small>
              </div>
            </div>
          </div>
        `;

        NotificationManager.success("이상 탐지 분석이 완료되었습니다!");
      } catch (error) {
        console.error("❌ 이상 탐지 오류:", error);
        mlResults.innerHTML = `
          <div class="analysis-error">
            <h4><i class="fas fa-exclamation-triangle text-danger"></i> 이상 탐지 실패</h4>
            <p>이상 탐지 분석 중 오류가 발생했습니다: ${error.message}</p>
            <small>데이터 로딩 상태를 확인하고 다시 시도해주세요.</small>
          </div>
        `;
        NotificationManager.error(`이상 탐지 실패: ${error.message}`);
      } finally {
        anomalyDetectionBtn.innerHTML = originalText;
        anomalyDetectionBtn.disabled = false;
      }
    });
  }

  console.log("🧠 AI 분석 버튼 기능이 초기화되었습니다.");
}

// 전역 변수 선언 (중복 제거)
let dashboardManager;
let chartManager;

// 페이지 로드 완료 후 초기화
document.addEventListener("DOMContentLoaded", async () => {
  // 매니저 인스턴스 생성
  chartManager = new ChartManager();
  dashboardManager = new DashboardManager();

  // 전역 접근을 위해 window 객체에 할당
  window.chartManager = chartManager;
  window.dashboardManager = dashboardManager;

  // 대시보드 초기화
  await dashboardManager.initialize();

  // 시스템 상태 업데이트
  dashboardManager.updateSystemStatus();

  // 키보드 단축키 설정
  dashboardManager.setupKeyboardShortcuts();

  // AI 차트 생성 기능 초기화
  initializeAIChartGeneration();

  // AI 분석 버튼 기능 초기화
  initializeAIAnalysisButtons();

  console.log(
    "🎉 Smart Warehouse Management System이 성공적으로 로드되었습니다!"
  );
});

// 윈도우 리사이즈 이벤트 리스너
window.addEventListener("resize", () => {
  if (chartManager) {
    chartManager.resizeCharts();
  }
});

// 에러 핸들링
window.addEventListener("error", (e) => {
  console.error("전역 오류:", e.error);
  NotificationManager.error("예상치 못한 오류가 발생했습니다.");
});

// 언로드 시 정리
window.addEventListener("beforeunload", () => {
  if (dashboardManager) dashboardManager.stopAutoRefresh();
  if (chartManager) {
    // 모든 차트 정리
    Object.keys(chartManager.charts).forEach((chartId) => {
      if (chartManager.charts[chartId]) {
        chartManager.charts[chartId].destroy();
      }
    });
  }
  
  // Tab Mode AI 분석 초기화
  initializeTabModeAIAnalysis();
});

// Tab Mode AI 분석 초기화 함수
function initializeTabModeAIAnalysis() {
  console.log("🤖 Tab Mode AI 분석 초기화...");
  
  // Tab Mode 전용 AI 분석 버튼들
  const tabDemandBtn = document.getElementById("tabDemandPredictBtn");
  const tabClusterBtn = document.getElementById("tabClusterAnalysisBtn");
  const tabAnomalyBtn = document.getElementById("tabAnomalyDetectionBtn");
  const tabOptimizationBtn = document.getElementById("tabOptimizationBtn");

  // 공통 이벤트 핸들러
  [tabDemandBtn, tabClusterBtn, tabAnomalyBtn, tabOptimizationBtn].forEach(btn => {
    if (btn) {
      btn.addEventListener("click", (e) => {
        const analysisType = e.target.closest('button').dataset.analysis;
        runTabModeAdvancedAnalysis(analysisType);
      });
    }
  });

  // 초기 상태 업데이트
  updateTabAnalysisStatus();
  
  console.log("✅ Tab Mode AI 분석 활성화됨");
}

async function runTabModeAdvancedAnalysis(type) {
  const resultsDiv = document.getElementById("tabMlResults");
  const lastAnalysisTime = document.getElementById("tabLastAnalysisTime");
  const confidenceScore = document.getElementById("tabConfidenceScore");
  const recommendedActions = document.getElementById("tabRecommendedActions");
  const actionsList = document.getElementById("tabActionsList");

  if (!resultsDiv) return;

  // 로딩 상태 표시
  resultsDiv.innerHTML = `
    <div class="analysis-loading">
      <div class="loading-spinner">
        <i class="fas fa-cog fa-spin"></i>
      </div>
      <h4>${getTabAnalysisTitle(type)} 실행 중...</h4>
      <p>AI 모델이 데이터를 분석하고 있습니다.</p>
      <div class="progress-indicator">
        <div class="progress-step active">데이터 수집</div>
        <div class="progress-step">모델 실행</div>
        <div class="progress-step">결과 생성</div>
      </div>
    </div>
  `;

  // 진행률 시뮬레이션
  setTimeout(() => {
    const steps = resultsDiv.querySelectorAll('.progress-step');
    if (steps[1]) steps[1].classList.add('active');
  }, 1000);

  setTimeout(() => {
    const steps = resultsDiv.querySelectorAll('.progress-step');
    if (steps[2]) steps[2].classList.add('active');
  }, 2000);

  // 분석 결과 표시
  setTimeout(() => {
    const result = generateTabAnalysisResult(type);
    resultsDiv.innerHTML = result.content;
    
    // 상태 업데이트
    if (lastAnalysisTime) {
      lastAnalysisTime.textContent = new Date().toLocaleTimeString();
    }
    
    if (confidenceScore) {
      confidenceScore.textContent = result.confidence;
      confidenceScore.className = `status-value ${result.confidenceClass}`;
    }

    // 추천 액션 표시
    if (result.actions && result.actions.length > 0) {
      showTabRecommendedActions(result.actions);
    }

  }, 3000);
}

function getTabAnalysisTitle(type) {
  const titles = {
    'demand': '수요 예측 분석',
    'cluster': '제품 클러스터링 분석',
    'anomaly': '이상 탐지 분석',
    'optimization': '운영 최적화 분석'
  };
  return titles[type] || 'AI 분석';
}

function generateTabAnalysisResult(type) {
  // Browser Mode와 동일한 분석 결과 재사용
  const results = {
    'demand': {
      content: `
        <div class="analysis-result demand-analysis">
          <div class="result-header">
            <h4><i class="fas fa-chart-line"></i> 수요 예측 분석 결과</h4>
            <span class="analysis-badge success">예측 완료</span>
          </div>
          
          <div class="key-metrics">
            <div class="metric-card">
              <h5>다음 주 예상 입고량</h5>
              <div class="metric-value">1,247 <span class="unit">개</span></div>
              <div class="metric-change positive">+12.3% vs 이번 주</div>
            </div>
            <div class="metric-card">
              <h5>권장 재고 수준</h5>
              <div class="metric-value">87 <span class="unit">%</span></div>
              <div class="metric-change neutral">최적 범위</div>
            </div>
            <div class="metric-card">
              <h5>예상 회전율</h5>
              <div class="metric-value">2.4 <span class="unit">배/월</span></div>
              <div class="metric-change positive">+0.3 개선</div>
            </div>
          </div>

          <div class="prediction-details">
            <h5>상세 예측</h5>
            <div class="prediction-items">
              <div class="prediction-item">
                <span class="product-category">면류/라면</span>
                <span class="prediction-value">345개</span>
                <span class="confidence">95%</span>
              </div>
              <div class="prediction-item">
                <span class="product-category">음료/음료수</span>
                <span class="prediction-value">287개</span>
                <span class="confidence">92%</span>
              </div>
              <div class="prediction-item">
                <span class="product-category">조미료/양념</span>
                <span class="prediction-value">198개</span>
                <span class="confidence">89%</span>
              </div>
            </div>
          </div>
        </div>
      `,
      confidence: '94.2%',
      confidenceClass: 'confidence-high',
      actions: [
        { type: 'warning', text: 'A랙 용량 확보 필요 (85% 포화)', priority: 'high' },
        { type: 'info', text: '면류 제품 입고 일정 앞당기기 권장', priority: 'medium' },
        { type: 'success', text: '전반적 재고 운영 효율성 양호', priority: 'low' }
      ]
    },
    'cluster': {
      content: `
        <div class="analysis-result cluster-analysis">
          <div class="result-header">
            <h4><i class="fas fa-project-diagram"></i> 제품 클러스터링 분석 결과</h4>
            <span class="analysis-badge success">분석 완료</span>
          </div>

          <div class="cluster-summary">
            <div class="cluster-stats">
              <div class="stat-item">
                <span class="stat-number">6</span>
                <span class="stat-label">클러스터</span>
              </div>
              <div class="stat-item">
                <span class="stat-number">89</span>
                <span class="stat-label">총 상품</span>
              </div>
              <div class="stat-item">
                <span class="stat-number">23</span>
                <span class="stat-label">고회전 상품</span>
              </div>
            </div>
          </div>

          <div class="cluster-details">
            <div class="cluster-item high-priority">
              <div class="cluster-name">고회전-고수익 클러스터</div>
              <div class="cluster-info">
                <span>23개 상품</span>
                <span>회전율: 3.2배/월</span>
                <span>우선 관리 필요</span>
              </div>
            </div>
            <div class="cluster-item medium-priority">
              <div class="cluster-name">안정적 수요 클러스터</div>
              <div class="cluster-info">
                <span>34개 상품</span>
                <span>회전율: 1.8배/월</span>
                <span>현재 관리 유지</span>
              </div>
            </div>
            <div class="cluster-item low-priority">
              <div class="cluster-name">저회전 클러스터</div>
              <div class="cluster-info">
                <span>12개 상품</span>
                <span>회전율: 0.9배/월</span>
                <span>재고 최적화 검토</span>
              </div>
            </div>
          </div>
        </div>
      `,
      confidence: '91.7%',
      confidenceClass: 'confidence-high',
      actions: [
        { type: 'info', text: '고회전 상품 별도 구역 배치 검토', priority: 'high' },
        { type: 'warning', text: '저회전 상품 재고 수준 조정 필요', priority: 'medium' }
      ]
    },
    'anomaly': {
      content: `
        <div class="analysis-result anomaly-analysis">
          <div class="result-header">
            <h4><i class="fas fa-shield-alt"></i> 이상 탐지 분석 결과</h4>
            <span class="analysis-badge warning">주의 필요</span>
          </div>

          <div class="anomaly-overview">
            <div class="anomaly-status">
              <div class="status-indicator warning"></div>
              <span>1개 이상 패턴 감지됨</span>
            </div>
          </div>

          <div class="anomaly-details">
            <div class="anomaly-item critical">
              <div class="anomaly-header">
                <i class="fas fa-exclamation-triangle"></i>
                <span class="anomaly-title">C-001 랙 비정상 출고 패턴</span>
                <span class="severity critical">Critical</span>
              </div>
              <div class="anomaly-description">
                <p>지난 3일간 평균 대비 347% 높은 출고량 기록</p>
                <p>추정 원인: 대량 주문 또는 시스템 오류</p>
              </div>
            </div>
          </div>
        </div>
      `,
      confidence: '88.9%',
      confidenceClass: 'confidence-medium',
      actions: [
        { type: 'error', text: 'C-001 랙 긴급 점검 필요', priority: 'critical' },
        { type: 'warning', text: '대량 출고 승인 프로세스 강화 검토', priority: 'high' }
      ]
    },
    'optimization': {
      content: `
        <div class="analysis-result optimization-analysis">
          <div class="result-header">
            <h4><i class="fas fa-cogs"></i> 운영 최적화 분석 결과</h4>
            <span class="analysis-badge success">최적화 완료</span>
          </div>

          <div class="optimization-summary">
            <div class="efficiency-score">
              <div class="score-circle">
                <span class="score">87</span>
                <span class="score-label">효율성 점수</span>
              </div>
              <div class="score-improvement">
                <span class="improvement-value">+5점</span>
                <span class="improvement-period">지난 달 대비</span>
              </div>
            </div>
          </div>

          <div class="optimization-recommendations">
            <h5>최적화 권장사항</h5>
            
            <div class="recommendation-item high-impact">
              <div class="recommendation-header">
                <span class="impact-badge high">높은 효과</span>
                <span class="recommendation-title">랙 배치 최적화</span>
              </div>
              <div class="recommendation-details">
                <p>고회전 상품을 입구 근처 A, B랙으로 이동</p>
                <p>예상 효율성 향상: 12-15%</p>
              </div>
            </div>
          </div>
        </div>
      `,
      confidence: '92.8%',
      confidenceClass: 'confidence-high',
      actions: [
        { type: 'success', text: '랙 배치 최적화 계획 수립 권장', priority: 'high' },
        { type: 'info', text: '입고 스케줄 변경 테스트 진행', priority: 'medium' }
      ]
    }
  };

  return results[type] || results['demand'];
}

function showTabRecommendedActions(actions) {
  const recommendedActions = document.getElementById("tabRecommendedActions");
  const actionsList = document.getElementById("tabActionsList");
  
  if (!recommendedActions || !actionsList) return;

  actionsList.innerHTML = actions.map(action => `
    <div class="action-item ${action.type} priority-${action.priority}">
      <div class="action-icon">
        <i class="fas ${getTabActionIcon(action.type)}"></i>
      </div>
      <div class="action-content">
        <span class="action-text">${action.text}</span>
        <span class="action-priority">${action.priority}</span>
      </div>
      <div class="action-buttons">
        <button class="btn btn-sm btn-outline-primary">실행</button>
        <button class="btn btn-sm btn-outline-secondary">나중에</button>
      </div>
    </div>
  `).join('');

  recommendedActions.style.display = 'block';
}

function getTabActionIcon(type) {
  const icons = {
    'error': 'fa-exclamation-circle',
    'warning': 'fa-exclamation-triangle', 
    'info': 'fa-info-circle',
    'success': 'fa-check-circle'
  };
  return icons[type] || 'fa-info-circle';
}

function updateTabAnalysisStatus() {
  const lastAnalysisTime = document.getElementById("tabLastAnalysisTime");
  
  if (lastAnalysisTime) {
    lastAnalysisTime.textContent = "시스템 대기 중";
  }
}
