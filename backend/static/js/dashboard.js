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
    this.refreshBtn.addEventListener("click", () => {
      this.refreshData();
    });

    // ML 분석 버튼들
    this.demandPredictBtn.addEventListener("click", () => {
      this.runDemandPrediction();
    });

    this.clusterAnalysisBtn.addEventListener("click", () => {
      this.runClusterAnalysis();
    });

    this.anomalyDetectionBtn.addEventListener("click", () => {
      this.runAnomalyDetection();
    });

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
      chartManager.updateAllCharts({
        inventoryData,
        trendData,
        categoryData,
      });

      return { kpiData, inventoryData, trendData, categoryData };
    } catch (error) {
      console.error("대시보드 데이터 로드 오류:", error);
      throw error;
    }
  }

  // KPI 업데이트
  updateKPIs(data) {
    if (this.kpiElements.totalInventory) {
      this.kpiElements.totalInventory.textContent = NumberUtils.formatNumber(
        data.total_inventory
      );
    }
    if (this.kpiElements.dailyThroughput) {
      this.kpiElements.dailyThroughput.textContent = NumberUtils.formatNumber(
        data.daily_throughput
      );
    }
    if (this.kpiElements.rackUtilization) {
      this.kpiElements.rackUtilization.textContent =
        NumberUtils.formatPercentage(data.rack_utilization);
    }
    if (this.kpiElements.inventoryTurnover) {
      this.kpiElements.inventoryTurnover.textContent =
        NumberUtils.formatDecimal(data.inventory_turnover);
    }

    // KPI 카드 애니메이션 효과
    this.animateKPICards();
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

  // 클러스터 분석 실행
  async runClusterAnalysis() {
    try {
      this.setMLButtonLoading(this.clusterAnalysisBtn, true);

      const response = await APIClient.post("/api/product/cluster");
      chartManager.createMLResultChart(response, "cluster");

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

  // ML 버튼 로딩 상태
  setMLButtonLoading(button, loading) {
    const icon = button.querySelector("i");
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

// 전역 대시보드 매니저 인스턴스
const dashboardManager = new DashboardManager();

// 전역에서 접근 가능하도록 설정
window.dashboardManager = dashboardManager;

// 페이지 로드 완료 후 초기화
document.addEventListener("DOMContentLoaded", async () => {
  // 대시보드 초기화
  await dashboardManager.initialize();

  // 시스템 상태 업데이트
  dashboardManager.updateSystemStatus();

  // 키보드 단축키 설정
  dashboardManager.setupKeyboardShortcuts();

  console.log(
    "🎉 Smart Warehouse Management System이 성공적으로 로드되었습니다!"
  );
});

// 에러 핸들링
window.addEventListener("error", (e) => {
  console.error("전역 오류:", e.error);
  NotificationManager.error("예상치 못한 오류가 발생했습니다.");
});

// 언로드 시 정리
window.addEventListener("beforeunload", () => {
  dashboardManager.stopAutoRefresh();
  chartManager.destroyAllCharts();
});
