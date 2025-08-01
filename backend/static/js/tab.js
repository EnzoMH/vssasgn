// ================================
// VIEW MODE MANAGER
// ================================

class ViewModeManager {
  constructor() {
    this.currentMode = "tab"; // 'browser' or 'tab'
    this.initializeElements();
    this.bindEvents();
    this.loadSettings();
  }

  initializeElements() {
    this.browserModeBtn = document.getElementById("browserModeBtn");
    this.tabModeBtn = document.getElementById("tabModeBtn");
    this.browserModeSection = document.getElementById("browserModeSection");
    this.tabModeSection = document.getElementById("tabModeSection");
  }

  bindEvents() {
    if (this.browserModeBtn) {
      this.browserModeBtn.addEventListener("click", () => {
        this.setMode("browser");
      });
    }

    if (this.tabModeBtn) {
      this.tabModeBtn.addEventListener("click", () => {
        this.setMode("tab");
      });
    }
  }

  setMode(mode) {
    this.currentMode = mode;

    // 버튼 상태 업데이트
    if (mode === "browser") {
      this.browserModeBtn?.classList.add("active");
      this.browserModeBtn?.classList.remove("btn-outline-primary");
      this.browserModeBtn?.classList.add("btn-primary");

      this.tabModeBtn?.classList.remove("active");
      this.tabModeBtn?.classList.add("btn-outline-primary");
      this.tabModeBtn?.classList.remove("btn-primary");

      // 섹션 표시/숨김
      this.browserModeSection.style.display = "block";
      this.tabModeSection.style.display = "none";

      // Browser 모드 차트 생성
      this.createBrowserModeCharts();
    } else {
      this.tabModeBtn?.classList.add("active");
      this.tabModeBtn?.classList.remove("btn-outline-primary");
      this.tabModeBtn?.classList.add("btn-primary");

      this.browserModeBtn?.classList.remove("active");
      this.browserModeBtn?.classList.add("btn-outline-primary");
      this.browserModeBtn?.classList.remove("btn-primary");

      // 섹션 표시/숨김
      this.browserModeSection.style.display = "none";
      this.tabModeSection.style.display = "block";
    }

    this.saveSettings();

    // 커스텀 이벤트 발생
    window.dispatchEvent(
      new CustomEvent("viewmodechange", {
        detail: { mode: mode },
      })
    );
  }

  async createBrowserModeCharts() {
    if (!window.chartManager) return;

    try {
      // API에서 데이터 가져오기
      const [inventoryData, trendData, categoryData] = await Promise.all([
        fetch("/api/inventory/by-rack").then((r) => r.json()),
        fetch("/api/trends/daily").then((r) => r.json()),
        fetch("/api/product/category-distribution").then((r) => r.json()),
      ]);

      // Browser 모드용 차트 생성 (표준 ID 사용)
      chartManager.createInventoryChart(inventoryData, "inventoryChart");
      chartManager.createTrendChart(trendData, "trendChart");
      chartManager.createCategoryChart(categoryData, "categoryChart");

      // Browser 모드 추가 기능 초기화
      this.initializeBrowserModeFeatures();
    } catch (error) {
      console.warn("Browser 모드 차트 생성 중 오류:", error);
    }
  }

  initializeBrowserModeFeatures() {
    // Browser 모드 ML 클러스터링 초기화
    this.initializeBrowserMLClustering();

    // Browser 모드 CAD 뷰어 초기화
    this.initializeBrowserCADViewer();

    // Browser 모드 AI 분석 버튼 초기화
    this.initializeBrowserAIAnalysis();
  }

  initializeBrowserMLClustering() {
    // ML 클러스터링 상태 로드
    this.loadMLClusteringStatus("browser");

    // 버튼 이벤트 바인딩
    const refreshBtn = document.getElementById("browserRefreshClustersBtn");
    const retrainBtn = document.getElementById("browserRetrainModelBtn");
    const exportBtn = document.getElementById("browserExportClustersBtn");

    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => {
        this.loadMLClusteringStatus("browser");
      });
    }

    if (retrainBtn) {
      retrainBtn.addEventListener("click", () => {
        this.retrainMLModel("browser");
      });
    }

    if (exportBtn) {
      exportBtn.addEventListener("click", () => {
        this.exportMLResults("browser");
      });
    }
  }

  async loadMLClusteringStatus(prefix = "") {
    try {
      const response = await fetch("/api/ml/product-clustering/status");
      const data = await response.json();

      const statusText = document.getElementById(`${prefix}ModelStatusText`);
      const trainedAt = document.getElementById(`${prefix}ModelTrainedAt`);
      const clusters = document.getElementById(`${prefix}ModelClusters`);
      const products = document.getElementById(`${prefix}ModelProducts`);

      if (statusText)
        statusText.textContent = data.is_trained ? "훈련됨" : "미훈련";
      if (trainedAt) trainedAt.textContent = data.trained_at || "-";
      if (clusters) clusters.textContent = data.n_clusters || "-";
      if (products) products.textContent = data.n_products || "-";

      // 클러스터 차트 로드
      if (data.is_trained) {
        this.loadClusterChart(prefix);
      }
    } catch (error) {
      console.warn("ML 클러스터링 상태 로드 실패:", error);
    }
  }

  async loadClusterChart(prefix = "") {
    try {
      console.log("🔄 브라우저 모드 클러스터 차트 로딩...");
      const response = await fetch("/api/ml/product-clustering/clusters");

      if (!response.ok) {
        console.warn("❌ 클러스터 API 오류:", response.status);
        this.showBrowserClusterError(
          prefix,
          "클러스터 데이터를 불러올 수 없습니다."
        );
        return;
      }

      const data = await response.json();
      console.log("✅ 브라우저 모드 클러스터 데이터:", data);

      if (data.clusters && data.clusters.length > 0) {
        const chartData = {
          labels: data.clusters.map(
            (c) => c.cluster_name || `클러스터 ${c.cluster_id}`
          ),
          datasets: [
            {
              data: data.clusters.map((c) => c.size),
              backgroundColor: data.clusters.map((c, index) => {
                // API에서 color 제공하면 사용, 아니면 기본 색상 배열
                return (
                  c.color ||
                  [
                    "rgba(59, 130, 246, 0.8)",
                    "rgba(16, 185, 129, 0.8)",
                    "rgba(245, 158, 11, 0.8)",
                    "rgba(239, 68, 68, 0.8)",
                    "rgba(139, 92, 246, 0.8)",
                    "rgba(236, 72, 153, 0.8)",
                  ][index % 6]
                );
              }),
              borderColor: "#ffffff",
              borderWidth: 2,
            },
          ],
        };

        const ctx = document.getElementById(
          prefix ? `${prefix}ClusterDistributionChart` : "clusterDistributionChart"
        );
        if (ctx) {
          // 기존 차트가 있으면 제거
          if (ctx.chart) {
            ctx.chart.destroy();
          }

          ctx.chart = new Chart(ctx, {
            type: "doughnut",
            data: chartData,
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: {
                  position: "bottom",
                  labels: {
                    padding: 20,
                    usePointStyle: true,
                  },
                },
                tooltip: {
                  callbacks: {
                    label: function (context) {
                      const cluster = data.clusters[context.dataIndex];
                      return `${context.label}: ${context.parsed}개 (${cluster.percentage}%)`;
                    },
                  },
                },
              },
            },
          });
        }

        // 클러스터 개요 정보도 업데이트
        this.updateBrowserClusterOverview(prefix, data);
      } else {
        this.showBrowserClusterError(
          prefix,
          "표시할 클러스터 데이터가 없습니다."
        );
      }
    } catch (error) {
      console.error("❌ 클러스터 차트 로드 실패:", error);
      this.showBrowserClusterError(prefix, `차트 로드 실패: ${error.message}`);
    }
  }

  showBrowserClusterError(prefix, message) {
    const overviewElement = document.getElementById(
      `${prefix}ClustersOverview`
    );
    if (overviewElement) {
      overviewElement.innerHTML = `
        <div class="alert alert-warning text-center">
          <i class="fas fa-exclamation-triangle"></i> 
          ${message}
        </div>
      `;
    }
  }

  updateBrowserClusterOverview(prefix, data) {
    const overviewElement = document.getElementById(
      `${prefix}ClustersOverview`
    );
    if (!overviewElement || !data.clusters) return;

    const clusterCards = data.clusters
      .map(
        (cluster) => `
      <div class="cluster-overview-card">
        <div class="cluster-header">
          <h5>${cluster.cluster_name}</h5>
          <span class="cluster-size">${cluster.size}개</span>
        </div>
        <div class="cluster-info">
          <p class="cluster-percentage">${cluster.percentage}%</p>
          <p class="cluster-strategy">${cluster.strategy}</p>
        </div>
      </div>
    `
      )
      .join("");

    overviewElement.innerHTML = `
      <div class="clusters-grid">
        ${clusterCards}
      </div>
      <div class="cluster-summary">
        <p class="text-muted">총 ${data.total_products}개 상품이 ${data.clusters.length}개 클러스터로 분류되었습니다.</p>
      </div>
    `;
  }

  async retrainMLModel(prefix = "") {
    try {
      console.log(`🔄 ${prefix} 모드 ML 모델 재훈련 시작...`);

      const retrainBtn = document.getElementById(`${prefix}RetrainModelBtn`);
      if (retrainBtn) {
        retrainBtn.disabled = true;
        retrainBtn.innerHTML =
          '<i class="fas fa-spinner fa-spin"></i> 훈련 중...';
      }

      const response = await fetch("/api/ml/product-clustering/retrain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) {
        throw new Error(`훈련 실패: HTTP ${response.status}`);
      }

      const result = await response.json();
      console.log("✅ 모델 재훈련 완료:", result);

      // 재훈련 완료 후 상태와 차트 다시 로드
      await this.loadMLClusteringStatus(prefix);

      NotificationManager.success("모델 재훈련이 완료되었습니다.");
    } catch (error) {
      console.error("❌ 모델 재훈련 실패:", error);
      NotificationManager.error(`모델 재훈련 실패: ${error.message}`);
    } finally {
      const retrainBtn = document.getElementById(`${prefix}RetrainModelBtn`);
      if (retrainBtn) {
        retrainBtn.disabled = false;
        retrainBtn.innerHTML = '<i class="fas fa-brain"></i> 모델 재훈련';
      }
    }
  }

  exportMLResults(prefix = "") {
    // 결과 내보내기 로직 (구현 예정)
    console.log(`${prefix} 모드 ML 결과 내보내기`);
  }

  initializeBrowserCADViewer() {
    const uploadBtn = document.getElementById("browserUploadCADBtn");
    const selectBtn = document.getElementById("browserSelectCADFileBtn");
    const fileInput = document.getElementById("browserCadFileInput");
    const dropzone = document.getElementById("browserCadDropzone");

    if (uploadBtn) {
      uploadBtn.addEventListener("click", () => {
        fileInput?.click();
      });
    }

    if (selectBtn) {
      selectBtn.addEventListener("click", () => {
        fileInput?.click();
      });
    }

    if (fileInput) {
      fileInput.addEventListener("change", (e) => {
        this.handleCADFileUpload(e.target.files[0], "browser");
      });
    }

    if (dropzone) {
      dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("drag-over");
      });

      dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("drag-over");
      });

      dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("drag-over");
        this.handleCADFileUpload(e.dataTransfer.files[0], "browser");
      });
    }
  }

  async handleCADFileUpload(file, prefix = "") {
    if (!file) return;

    console.log(`${prefix} 모드 CAD 파일 업로드:`, file.name);

    const uploadArea = document.getElementById(`${prefix}CadUploadArea`);
    const viewer = document.getElementById(`${prefix}CadViewer`);

    if (uploadArea) uploadArea.style.display = "none";
    if (viewer) viewer.style.display = "block";

    // CAD 파일 분석 시뮬레이션
    setTimeout(() => {
      const canvas = document.getElementById(`${prefix}WarehouseCanvas`);
      if (canvas) {
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#f3f4f6";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#1f2937";
        ctx.font = "16px Arial";
        ctx.textAlign = "center";
        ctx.fillText(
          "CAD 뷰어 (시뮬레이션)",
          canvas.width / 2,
          canvas.height / 2
        );
        ctx.fillText(
          `파일: ${file.name}`,
          canvas.width / 2,
          canvas.height / 2 + 30
        );
      }
    }, 1000);
  }

  initializeBrowserAIAnalysis() {
    const demandBtn = document.getElementById("browserDemandPredictBtn");
    const clusterBtn = document.getElementById("browserClusterAnalysisBtn");
    const anomalyBtn = document.getElementById("browserAnomalyDetectionBtn");
    const resultsDiv = document.getElementById("browserMlResults");

    if (demandBtn) {
      demandBtn.addEventListener("click", async () => {
        if (resultsDiv) {
          resultsDiv.innerHTML =
            '<i class="fas fa-spinner fa-spin"></i> 수요 예측 분석 중...';
        }

        setTimeout(() => {
          if (resultsDiv) {
            resultsDiv.innerHTML = `
              <div class="ai-result">
                <h5>수요 예측 결과</h5>
                <p>다음 주 예상 입고량: <strong>1,250개</strong></p>
                <p>권장 재고 수준: <strong>85%</strong></p>
              </div>
            `;
          }
        }, 2000);
      });
    }

    if (clusterBtn) {
      clusterBtn.addEventListener("click", () => {
        if (resultsDiv) {
          resultsDiv.innerHTML = `
            <div class="ai-result">
              <h5>제품 클러스터링 결과</h5>
              <p>총 6개 클러스터로 분류됨</p>
              <p>고회전 제품: <strong>23개</strong></p>
            </div>
          `;
        }
      });
    }

    if (anomalyBtn) {
      anomalyBtn.addEventListener("click", () => {
        if (resultsDiv) {
          resultsDiv.innerHTML = `
            <div class="ai-result">
              <h5>이상 탐지 결과</h5>
              <p>정상 범위 내 운영 중</p>
              <p>주의 필요 랙: <strong>C-001</strong></p>
            </div>
          `;
        }
      });
    }
  }

  saveSettings() {
    localStorage.setItem("warehouse_view_mode", this.currentMode);
  }

  loadSettings() {
    const saved = localStorage.getItem("warehouse_view_mode");
    if (saved && ["browser", "tab"].includes(saved)) {
      this.setMode(saved);
    }
  }

  getCurrentMode() {
    return this.currentMode;
  }
}

// ================================
// TAB NAVIGATION & DARK MODE MANAGER
// ================================

class TabManager {
  constructor() {
    this.activeTab = "inventory";
    this.tabOrder = [
      "inventory",
      "trends",
      "ai-analysis",
      "ai-charts",
      "cad-viewer",
      "ml-clustering",
    ];
    this.isDragging = false;
    this.draggedElement = null;

    this.initializeElements();
    this.bindEvents();
    this.loadSettings();
    this.showTab(this.activeTab);
  }

  initializeElements() {
    this.tabNavigation = document.getElementById("tabNavigation");
    this.tabButtons = document.querySelectorAll(".tab-button");
    this.tabContents = document.querySelectorAll(".tab-content");
    this.tabContainer = document.getElementById("tabContentContainer");
  }

  bindEvents() {
    // 탭 버튼 클릭 이벤트
    this.tabButtons.forEach((button) => {
      button.addEventListener("click", (e) => {
        e.preventDefault();
        const tabId = button.getAttribute("data-tab");
        this.showTab(tabId);
      });

      // 드래그 앤 드롭 이벤트
      button.addEventListener("dragstart", this.handleDragStart.bind(this));
      button.addEventListener("dragover", this.handleDragOver.bind(this));
      button.addEventListener("drop", this.handleDrop.bind(this));
      button.addEventListener("dragend", this.handleDragEnd.bind(this));
    });

    // 키보드 네비게이션
    this.tabNavigation.addEventListener(
      "keydown",
      this.handleKeyNavigation.bind(this)
    );

    // 모바일 스와이프 지원
    if (this.isMobile()) {
      this.setupMobileSwipe();
    }

    // 윈도우 리사이즈 이벤트
    window.addEventListener("resize", this.handleResize.bind(this));
  }

  showTab(tabId) {
    // 기존 활성 상태 제거
    this.tabButtons.forEach((btn) => btn.classList.remove("active"));
    this.tabContents.forEach((content) => {
      content.classList.remove("active");
      content.style.display = "none";
    });

    // 새로운 탭 활성화
    const targetButton = document.querySelector(`[data-tab="${tabId}"]`);
    const targetContent = document.getElementById(`${tabId}-tab`);

    if (targetButton && targetContent) {
      targetButton.classList.add("active");
      targetContent.style.display = "block";
      setTimeout(() => {
        targetContent.classList.add("active");
      }, 10);

      this.activeTab = tabId;
      this.saveSettings();

      // 탭 변경 후 차트 리사이즈 (Chart.js 대응)
      this.resizeChartsInTab(tabId);

      // 스크롤을 탭 네비게이션으로 이동
      this.scrollToActiveTab();

      // 커스텀 이벤트 발생
      this.dispatchTabChangeEvent(tabId);
    }
  }

  // 드래그 앤 드롭 핸들러들
  handleDragStart(e) {
    this.isDragging = true;
    this.draggedElement = e.target;
    e.target.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/html", e.target.outerHTML);
  }

  handleDragOver(e) {
    if (this.isDragging) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";

      // 드래그 오버 시각적 피드백
      const targetButton = e.target.closest(".tab-button");
      if (targetButton && targetButton !== this.draggedElement) {
        targetButton.classList.add("drag-over");
      }
    }
  }

  handleDrop(e) {
    if (this.isDragging) {
      e.preventDefault();

      const targetButton = e.target.closest(".tab-button");
      if (targetButton && targetButton !== this.draggedElement) {
        const draggedTabId = this.draggedElement.getAttribute("data-tab");
        const targetTabId = targetButton.getAttribute("data-tab");

        this.reorderTabs(draggedTabId, targetTabId);
      }
    }
  }

  handleDragEnd(e) {
    this.isDragging = false;
    e.target.classList.remove("dragging");

    // 모든 드래그 오버 클래스 제거
    this.tabButtons.forEach((btn) => btn.classList.remove("drag-over"));

    this.draggedElement = null;
  }

  reorderTabs(draggedTabId, targetTabId) {
    const draggedIndex = this.tabOrder.indexOf(draggedTabId);
    const targetIndex = this.tabOrder.indexOf(targetTabId);

    if (draggedIndex !== -1 && targetIndex !== -1) {
      // 배열에서 순서 변경
      this.tabOrder.splice(draggedIndex, 1);
      this.tabOrder.splice(targetIndex, 0, draggedTabId);

      // DOM에서 순서 변경
      const draggedButton = document.querySelector(
        `[data-tab="${draggedTabId}"]`
      );
      const targetButton = document.querySelector(
        `[data-tab="${targetTabId}"]`
      );

      if (draggedIndex < targetIndex) {
        targetButton.parentNode.insertBefore(
          draggedButton,
          targetButton.nextSibling
        );
      } else {
        targetButton.parentNode.insertBefore(draggedButton, targetButton);
      }

      this.saveSettings();

      // 순서 변경 알림
      this.showNotification("탭 순서가 변경되었습니다.", "success");
    }
  }

  // 키보드 네비게이션
  handleKeyNavigation(e) {
    const currentIndex = this.tabOrder.indexOf(this.activeTab);
    let newIndex = currentIndex;

    switch (e.key) {
      case "ArrowLeft":
        e.preventDefault();
        newIndex =
          currentIndex > 0 ? currentIndex - 1 : this.tabOrder.length - 1;
        break;
      case "ArrowRight":
        e.preventDefault();
        newIndex =
          currentIndex < this.tabOrder.length - 1 ? currentIndex + 1 : 0;
        break;
      case "Home":
        e.preventDefault();
        newIndex = 0;
        break;
      case "End":
        e.preventDefault();
        newIndex = this.tabOrder.length - 1;
        break;
      default:
        return;
    }

    if (newIndex !== currentIndex) {
      this.showTab(this.tabOrder[newIndex]);
    }
  }

  // 모바일 스와이프 설정
  setupMobileSwipe() {
    let startX = 0;
    let startY = 0;
    let endX = 0;
    let endY = 0;

    this.tabContainer.addEventListener(
      "touchstart",
      (e) => {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
      },
      { passive: true }
    );

    this.tabContainer.addEventListener(
      "touchend",
      (e) => {
        endX = e.changedTouches[0].clientX;
        endY = e.changedTouches[0].clientY;

        const deltaX = endX - startX;
        const deltaY = endY - startY;

        // 수평 스와이프가 수직 스와이프보다 클 때만 처리
        if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > 50) {
          const currentIndex = this.tabOrder.indexOf(this.activeTab);

          if (deltaX > 0 && currentIndex > 0) {
            // 오른쪽 스와이프 - 이전 탭
            this.showTab(this.tabOrder[currentIndex - 1]);
          } else if (deltaX < 0 && currentIndex < this.tabOrder.length - 1) {
            // 왼쪽 스와이프 - 다음 탭
            this.showTab(this.tabOrder[currentIndex + 1]);
          }
        }
      },
      { passive: true }
    );
  }

  // 활성 탭으로 스크롤
  scrollToActiveTab() {
    const activeButton = document.querySelector(".tab-button.active");
    if (activeButton && this.isMobile()) {
      activeButton.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "center",
      });
    }
  }

  // 탭 내 차트 리사이즈
  resizeChartsInTab(tabId) {
    setTimeout(() => {
      const tabContent = document.getElementById(`${tabId}-tab`);
      if (tabContent) {
        const canvases = tabContent.querySelectorAll("canvas");
        canvases.forEach((canvas) => {
          if (canvas.chart) {
            canvas.chart.resize();
          }
        });
      }
    }, 100);
  }

  // 윈도우 리사이즈 핸들러
  handleResize() {
    // 현재 활성 탭의 차트들 리사이즈
    this.resizeChartsInTab(this.activeTab);
  }

  // 모바일 감지
  isMobile() {
    return window.innerWidth <= 768;
  }

  // 설정 저장
  saveSettings() {
    const settings = {
      activeTab: this.activeTab,
      tabOrder: this.tabOrder,
      timestamp: Date.now(),
    };
    localStorage.setItem("warehouse_tab_settings", JSON.stringify(settings));
  }

  // 설정 로드
  loadSettings() {
    try {
      const stored = localStorage.getItem("warehouse_tab_settings");
      if (stored) {
        const settings = JSON.parse(stored);

        // 유효성 검사
        if (settings.tabOrder && Array.isArray(settings.tabOrder)) {
          this.tabOrder = settings.tabOrder;
          this.reorderTabsDOM();
        }

        if (settings.activeTab && this.tabOrder.includes(settings.activeTab)) {
          this.activeTab = settings.activeTab;
        }
      }
    } catch (error) {
      console.warn("탭 설정 로드 실패:", error);
    }
  }

  // DOM에서 탭 순서 재정렬
  reorderTabsDOM() {
    const fragment = document.createDocumentFragment();

    this.tabOrder.forEach((tabId) => {
      const button = document.querySelector(`[data-tab="${tabId}"]`);
      if (button) {
        fragment.appendChild(button);
      }
    });

    this.tabNavigation.appendChild(fragment);

    // 참조 업데이트
    this.tabButtons = document.querySelectorAll(".tab-button");
  }

  // 탭 변경 이벤트 발생
  dispatchTabChangeEvent(tabId) {
    const event = new CustomEvent("tabchange", {
      detail: {
        tabId: tabId,
        previousTab: this.previousTab || null,
      },
    });
    window.dispatchEvent(event);
    this.previousTab = tabId;
  }

  // 알림 표시
  showNotification(message, type = "info") {
    // 간단한 토스트 알림 (기존 스타일 활용)
    const notification = document.createElement("div");
    notification.className = `alert alert-${type}`;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 9999;
      max-width: 300px;
      animation: slideInRight 0.3s ease-out;
    `;
    notification.innerHTML = `
      <i class="fas fa-info-circle"></i>
      <span>${message}</span>
    `;

    document.body.appendChild(notification);

    // 3초 후 자동 제거
    setTimeout(() => {
      notification.style.animation = "slideOutRight 0.3s ease-in";
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }, 3000);
  }

  // 공개 메서드들
  getCurrentTab() {
    return this.activeTab;
  }

  getTabOrder() {
    return [...this.tabOrder];
  }

  setTabOrder(newOrder) {
    if (Array.isArray(newOrder) && newOrder.length === this.tabOrder.length) {
      this.tabOrder = newOrder;
      this.reorderTabsDOM();
      this.saveSettings();
      return true;
    }
    return false;
  }
}

// ================================
// DARK MODE MANAGER
// ================================

class DarkModeManager {
  constructor() {
    this.isDarkMode = false;
    this.themeToggle = document.getElementById("themeToggle");

    this.loadTheme();
    this.bindEvents();
    this.updateChartThemes();
  }

  bindEvents() {
    if (this.themeToggle) {
      this.themeToggle.addEventListener("click", () => {
        this.toggleTheme();
      });
    }

    // 시스템 테마 변경 감지
    if (window.matchMedia) {
      window
        .matchMedia("(prefers-color-scheme: dark)")
        .addEventListener("change", (e) => {
          if (!localStorage.getItem("warehouse_theme_preference")) {
            this.setTheme(e.matches ? "dark" : "light");
          }
        });
    }
  }

  toggleTheme() {
    this.setTheme(this.isDarkMode ? "light" : "dark");
  }

  setTheme(theme) {
    this.isDarkMode = theme === "dark";

    // HTML 데이터 속성 업데이트
    document.documentElement.setAttribute("data-theme", theme);

    // 토글 버튼 업데이트
    this.updateToggleButton();

    // 차트 테마 업데이트
    this.updateChartThemes();

    // 설정 저장
    localStorage.setItem("warehouse_theme_preference", theme);

    // 커스텀 이벤트 발생
    window.dispatchEvent(
      new CustomEvent("themechange", {
        detail: { theme: theme },
      })
    );
  }

  updateToggleButton() {
    if (!this.themeToggle) return;

    const icon = this.themeToggle.querySelector("i");
    const text = this.themeToggle.querySelector("span");

    if (this.isDarkMode) {
      icon.className = "fas fa-sun";
      text.textContent = "라이트모드";
      this.themeToggle.classList.remove("light-mode");
      this.themeToggle.classList.add("dark-mode");
    } else {
      icon.className = "fas fa-moon";
      text.textContent = "다크모드";
      this.themeToggle.classList.remove("dark-mode");
      this.themeToggle.classList.add("light-mode");
    }
  }

  updateChartThemes() {
    // Chart.js 글로벌 기본값 업데이트는 ChartManager에서 처리
    if (window.chartManager && window.chartManager.setTheme) {
      window.chartManager.setTheme(this.isDarkMode ? "dark" : "light");
    }
  }

  loadTheme() {
    // 저장된 테마 확인
    const savedTheme = localStorage.getItem("warehouse_theme_preference");

    if (savedTheme) {
      this.setTheme(savedTheme);
    } else {
      // 시스템 테마 사용
      const prefersDark =
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches;
      this.setTheme(prefersDark ? "dark" : "light");
    }
  }

  getCurrentTheme() {
    return this.isDarkMode ? "dark" : "light";
  }
}

// ================================
// LOI TABLE MANAGER
// ================================

class LOIChartManager {
  constructor() {
    this.isLoading = false;
    this.refreshInterval = null;
    this.currentView = "chart"; // 'chart' or 'table'
    this.loiChart = null;

    this.initializeElements();
    this.bindEvents();
    this.loadData();
    this.setupAutoRefresh();
  }

  initializeElements() {
    this.loiLoading = document.getElementById("loiLoading");
    this.loiTable = document.getElementById("loiTable");
    this.loiTableBody = document.getElementById("loiTableBody");
    this.loiCards = document.getElementById("loiCards");
    this.loiChartView = document.getElementById("loiChartView");
    this.loiTableView = document.getElementById("loiTableView");
    this.refreshBtn = document.getElementById("refreshLOIBtn");
    this.exportBtn = document.getElementById("exportLOIBtn");
    this.switchViewBtn = document.getElementById("switchLOIViewBtn");
  }

  bindEvents() {
    if (this.refreshBtn) {
      this.refreshBtn.addEventListener("click", () => {
        this.loadData(true);
      });
    }

    if (this.exportBtn) {
      this.exportBtn.addEventListener("click", () => {
        this.exportData();
      });
    }

    if (this.switchViewBtn) {
      this.switchViewBtn.addEventListener("click", () => {
        this.toggleView();
      });
    }

    // 윈도우 리사이즈 시 테이블/카드 모드 전환
    window.addEventListener("resize", () => {
      this.updateDisplayMode();
    });
  }

  async loadData(force = false) {
    if (this.isLoading && !force) return;

    this.isLoading = true;
    this.showLoading(true);

    try {
      console.log("📦 실제 rawdata 기반 LOI 데이터 로딩 시작...");

      // 실제 rawdata 기반 API 호출
      const response = await fetch("/api/inventory/by-rack");

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const inventoryData = await response.json();

      // 데이터 유효성 검증
      if (!Array.isArray(inventoryData)) {
        throw new Error("서버에서 잘못된 데이터 형식을 반환했습니다.");
      }

      if (inventoryData.length === 0) {
        console.warn("⚠️ 랙 데이터가 비어있습니다. 데이터 로딩을 확인하세요.");
        this.showError("랙 데이터가 없습니다. 데이터 로딩 상태를 확인하세요.");
        return;
      }

      console.log(`✅ LOI 데이터 로드 성공: ${inventoryData.length}개 랙`);
      console.log("샘플 데이터:", inventoryData.slice(0, 3));

      // 실제 데이터로 차트 및 테이블 렌더링
      this.renderChart(inventoryData);
      this.renderTable(inventoryData);
      this.renderCards(inventoryData);
      this.updateDisplayMode();
    } catch (error) {
      console.error("❌ LOI 데이터 로드 실패:", error);
      this.showError(`데이터 로딩 실패: ${error.message}`);
    } finally {
      this.isLoading = false;
      this.showLoading(false);
    }
  }

  renderChart(data) {
    if (!window.Chart || !data || data.length === 0) return;

    const ctx = document.getElementById("loiChart");
    if (!ctx) return;

    // 기존 차트 파괴
    if (this.loiChart) {
      this.loiChart.destroy();
    }

    // 차트 데이터 준비
    const chartData = {
      labels: data.map((item) => item.rackName),
      datasets: [
        {
          label: "현재 재고",
          data: data.map((item) => item.currentStock),
          backgroundColor: "rgba(59, 130, 246, 0.8)",
          borderColor: "rgba(59, 130, 246, 1)",
          borderWidth: 2,
          borderRadius: 6,
        },
        {
          label: "최대 용량",
          data: data.map((item) => item.capacity),
          backgroundColor: "rgba(156, 163, 175, 0.5)",
          borderColor: "rgba(156, 163, 175, 1)",
          borderWidth: 2,
          borderRadius: 6,
        },
      ],
    };

    // 차트 옵션
    const options = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: "랙별 재고 현황",
          font: { size: 16, weight: "bold" },
        },
        legend: {
          position: "top",
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              const value =
                window.NumberUtils?.formatNumber(context.parsed.y) ||
                context.parsed.y.toLocaleString();
              return `${context.dataset.label}: ${value}개`;
            },
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: function (value) {
              return (
                window.NumberUtils?.formatNumber(value) ||
                value.toLocaleString()
              );
            },
          },
        },
      },
    };

    // 차트 생성
    this.loiChart = new Chart(ctx, {
      type: "bar",
      data: chartData,
      options: options,
    });
  }

  toggleView() {
    this.currentView = this.currentView === "chart" ? "table" : "chart";
    this.updateDisplayMode();

    // 버튼 텍스트 업데이트
    if (this.switchViewBtn) {
      const icon = this.switchViewBtn.querySelector("i");
      const text =
        this.switchViewBtn.querySelector("span") || this.switchViewBtn;

      if (this.currentView === "chart") {
        icon.className = "fas fa-table";
        if (text.tagName === "SPAN") text.textContent = " 테이블 보기";
        else text.innerHTML = '<i class="fas fa-table"></i> 테이블 보기';
      } else {
        icon.className = "fas fa-chart-bar";
        if (text.tagName === "SPAN") text.textContent = " 차트 보기";
        else text.innerHTML = '<i class="fas fa-chart-bar"></i> 차트 보기';
      }
    }
  }

  renderTable(data) {
    if (!this.loiTableBody) return;

    this.loiTableBody.innerHTML = data
      .map((item) => {
        // 실제 데이터에서 활용률 사용 (이미 계산되어 제공됨)
        const utilizationPercent = Math.round(item.utilizationRate || 0);
        const status = this.getStatus(utilizationPercent);

        return `
        <tr>
          <td><strong>${item.rackName}</strong></td>
                     <td>${
                       window.NumberUtils?.formatNumber(item.currentStock) ||
                       item.currentStock.toLocaleString()
                     }</td>
           <td>${
             window.NumberUtils?.formatNumber(item.capacity) ||
             item.capacity.toLocaleString()
           }</td>
          <td>
            <div class="utilization-bar">
              <div class="utilization-fill ${
                status.class
              }" style="width: ${utilizationPercent}%"></div>
            </div>
            <small>${utilizationPercent}%</small>
          </td>
          <td>
            <span class="status-indicator ${status.class}">
              <i class="fas ${status.icon}"></i>
              ${status.text}
            </span>
          </td>
          <td>
            <button class="btn btn-sm btn-outline-primary" onclick="loiManager.viewDetails('${
              item.rackName
            }')">
              <i class="fas fa-eye"></i>
            </button>
            <button class="btn btn-sm btn-outline-secondary" onclick="loiManager.updateStock('${
              item.rackName
            }')">
              <i class="fas fa-edit"></i>
            </button>
          </td>
        </tr>
      `;
      })
      .join("");
  }

  renderCards(data) {
    if (!this.loiCards) return;

    this.loiCards.innerHTML = data
      .map((item) => {
        const utilizationPercent = Math.round(
          (item.currentStock / item.capacity) * 100
        );
        const status = this.getStatus(utilizationPercent);

        return `
        <div class="loi-card">
          <div class="loi-card-header">
            <div class="loi-card-title">${item.rackName}</div>
            <span class="status-indicator ${status.class}">
              <i class="fas ${status.icon}"></i>
              ${status.text}
            </span>
          </div>
          <div class="loi-card-content">
            <div class="loi-card-item">
              <div class="loi-card-label">현재재고</div>
                             <div class="loi-card-value">${
                               window.NumberUtils?.formatNumber(
                                 item.currentStock
                               ) || item.currentStock.toLocaleString()
                             }</div>
             </div>
             <div class="loi-card-item">
               <div class="loi-card-label">최대용량</div>
               <div class="loi-card-value">${
                 window.NumberUtils?.formatNumber(item.capacity) ||
                 item.capacity.toLocaleString()
               }</div>
            </div>
            <div class="loi-card-item">
              <div class="loi-card-label">활용률</div>
              <div class="loi-card-value">${utilizationPercent}%</div>
            </div>
            <div class="loi-card-item">
              <div class="loi-card-label">액션</div>
              <div class="loi-card-value">
                <button class="btn btn-sm btn-outline-primary" onclick="loiManager.viewDetails('${
                  item.rackName
                }')">
                  <i class="fas fa-eye"></i>
                </button>
                <button class="btn btn-sm btn-outline-secondary" onclick="loiManager.updateStock('${
                  item.rackName
                }')">
                  <i class="fas fa-edit"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      `;
      })
      .join("");
  }

  getStatus(utilizationPercent) {
    if (utilizationPercent >= 90) {
      return {
        class: "critical",
        icon: "fa-exclamation-triangle",
        text: "위험",
      };
    } else if (utilizationPercent >= 70) {
      return { class: "warning", icon: "fa-exclamation", text: "주의" };
    } else {
      return { class: "optimal", icon: "fa-check-circle", text: "양호" };
    }
  }

  updateDisplayMode() {
    const isMobile = window.innerWidth <= 768;

    // 차트/테이블 뷰 전환
    if (this.currentView === "chart") {
      this.loiChartView.style.display = "block";
      this.loiTableView.style.display = "none";
    } else {
      this.loiChartView.style.display = "none";
      this.loiTableView.style.display = "block";

      // 테이블 모드에서 모바일/데스크톱 전환
      if (isMobile) {
        this.loiTable.style.display = "none";
        this.loiCards.style.display = "grid";
      } else {
        this.loiTable.style.display = "table";
        this.loiCards.style.display = "none";
      }
    }

    // 차트 리사이즈 (차트 모드일 때)
    if (this.currentView === "chart" && this.loiChart) {
      setTimeout(() => {
        this.loiChart.resize();
      }, 100);
    }
  }

  showLoading(show) {
    if (this.loiLoading) {
      this.loiLoading.style.display = show ? "flex" : "none";
    }
  }

  showError(message) {
    console.error("LOI Error:", message);
    // 에러 표시 로직 (기존 알림 시스템 활용)
    if (window.tabManager) {
      tabManager.showNotification(message, "danger");
    }
  }

  setupAutoRefresh() {
    // 5분마다 자동 새로고침
    this.refreshInterval = setInterval(() => {
      this.loadData();
    }, 5 * 60 * 1000);
  }

  viewDetails(rackName) {
    // 상세 정보 모달 표시 (구현 예정)
    console.log("View details for:", rackName);
  }

  updateStock(rackName) {
    // 재고 업데이트 모달 표시 (구현 예정)
    console.log("Update stock for:", rackName);
  }

  exportData() {
    // CSV 내보내기 (구현 예정)
    console.log("Export LOI data");
  }

  generateDummyData() {
    // 기존 백엔드 API 형식에 맞춘 더미 데이터 생성
    return [
      { rackName: "A랙", currentStock: 850, capacity: 1020 },
      { rackName: "B랙", currentStock: 720, capacity: 964 },
      { rackName: "C랙", currentStock: 950, capacity: 1240 },
      { rackName: "D랙", currentStock: 680, capacity: 916 },
      { rackName: "E랙", currentStock: 520, capacity: 724 },
      { rackName: "F랙", currentStock: 890, capacity: 1168 },
      { rackName: "G랙", currentStock: 760, capacity: 1012 },
      { rackName: "H랙", currentStock: 650, capacity: 880 },
    ];
  }

  destroy() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }
}

// ================================
// INITIALIZATION
// ================================

// 전역 변수로 매니저들 선언
let viewModeManager;
let tabManager;
let darkModeManager;
let loiManager;

// DOM 로드 완료 시 초기화
document.addEventListener("DOMContentLoaded", () => {
  // chartManager가 준비될 때까지 대기 후 초기화
  setTimeout(() => {
    // 순서 중요: 뷰모드, 다크모드, 탭, LOI 순
    viewModeManager = new ViewModeManager();
    darkModeManager = new DarkModeManager();
    tabManager = new TabManager();
    loiManager = new LOIChartManager();
  }, 100);

  // 기존 dashboard.js와의 연동을 위한 이벤트 리스너
  window.addEventListener("tabchange", (e) => {
    console.log("Tab changed to:", e.detail.tabId);
  });

  window.addEventListener("themechange", (e) => {
    console.log("Theme changed to:", e.detail.theme);
  });

  // CSS 애니메이션 추가
  const style = document.createElement("style");
  style.textContent = `
    @keyframes slideInRight {
      from { transform: translateX(100%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOutRight {
      from { transform: translateX(0); opacity: 1; }
      to { transform: translateX(100%); opacity: 0; }
    }
  `;
  document.head.appendChild(style);
});

// 페이지 언로드 시 정리
window.addEventListener("beforeunload", () => {
  if (loiManager) {
    loiManager.destroy();
  }
});

// 전역 접근을 위한 export (모듈화된 환경에서 사용)
if (typeof module !== "undefined" && module.exports) {
  module.exports = { TabManager, DarkModeManager, LOITableManager };
}
