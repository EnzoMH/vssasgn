// ML Product Clustering 관리 클래스
class MLClusteringManager {
  constructor() {
    this.clustersData = null;
    this.clusterChart = null;
    this.modelStatus = null;

    this.initializeElements();
    this.bindEvents();
    this.loadInitialData();
  }

  initializeElements() {
    // DOM 요소들
    this.statusPanel = document.getElementById("mlModelStatus");
    this.clustersOverview = document.getElementById("clustersOverview");
    this.highTurnoverGrid = document.getElementById("highTurnoverProducts");
    this.productSearchBtn = document.getElementById("searchProductBtn");
    this.productCodeInput = document.getElementById("productCodeInput");
    this.productAnalysisResult = document.getElementById(
      "productAnalysisResult"
    );
    this.clusterCanvas = document.getElementById("clusterDistributionChart");

    // 컨트롤 버튼들
    this.refreshBtn = document.getElementById("refreshClustersBtn");
    this.retrainBtn = document.getElementById("retrainModelBtn");
    this.exportBtn = document.getElementById("exportClustersBtn");
  }

  bindEvents() {
    // 버튼 이벤트
    if (this.refreshBtn) {
      this.refreshBtn.addEventListener("click", () => this.refreshData());
    }

    if (this.retrainBtn) {
      this.retrainBtn.addEventListener("click", () => this.retrainModel());
    }

    if (this.exportBtn) {
      this.exportBtn.addEventListener("click", () => this.exportResults());
    }

    // 상품 검색
    if (this.productSearchBtn) {
      this.productSearchBtn.addEventListener("click", () =>
        this.searchProduct()
      );
    }

    if (this.productCodeInput) {
      this.productCodeInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
          this.searchProduct();
        }
      });
    }
  }

  async loadInitialData() {
    try {
      await this.loadModelStatus();
      await this.loadClusters();
      await this.loadHighTurnoverProducts();
    } catch (error) {
      console.error("초기 데이터 로딩 실패:", error);
      this.showError("데이터 로딩에 실패했습니다.");
    }
  }

  async loadModelStatus() {
    try {
      const response = await fetch("/api/ml/product-clustering/status");

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      this.modelStatus = await response.json();
      this.updateStatusPanel();
    } catch (error) {
      console.error("모델 상태 로딩 실패:", error);
      this.updateStatusPanel({
        model_trained: false,
        error: error.message,
      });
    }
  }

  updateStatusPanel(status = null) {
    const data = status || this.modelStatus;

    if (!data) {
      this.updateStatusText("modelStatusText", "로딩 실패", "error");
      return;
    }

    // 모델 상태
    if (data.model_trained && data.model_available) {
      this.updateStatusText("modelStatusText", "✅ 활성화", "success");
    } else if (data.error) {
      this.updateStatusText("modelStatusText", "❌ 오류", "error");
    } else {
      this.updateStatusText("modelStatusText", "⚠️ 비활성화", "warning");
    }

    // 기타 정보
    this.updateStatusText(
      "modelTrainedAt",
      data.trained_at ? new Date(data.trained_at).toLocaleString("ko-KR") : "-"
    );
    this.updateStatusText("modelClusters", data.n_clusters || "-");
    this.updateStatusText("modelProducts", data.total_products || "-");
  }

  updateStatusText(elementId, text, className = "") {
    const element = document.getElementById(elementId);
    if (element) {
      element.textContent = text;

      // 클래스 초기화 후 새 클래스 추가
      element.className = "status-value";
      if (className) {
        element.classList.add(className);
      }
    }
  }

  async loadClusters() {
    try {
      const response = await fetch("/api/ml/product-clustering/clusters");

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      this.clustersData = await response.json();
      this.renderClustersOverview();
      this.renderClusterChart();
    } catch (error) {
      console.error("클러스터 데이터 로딩 실패:", error);
      this.showClustersError(error.message);
    }
  }

  renderClustersOverview() {
    if (!this.clustersData || !this.clustersOverview) return;

    const clusters = this.clustersData.clusters;

    this.clustersOverview.innerHTML = clusters
      .map(
        (cluster) => `
      <div class="cluster-card ${this.getClusterPriorityClass(
        cluster.cluster_name
      )}" 
           data-cluster-id="${cluster.cluster_id}">
        <div class="cluster-header">
          <div class="cluster-name">${cluster.cluster_name}</div>
          <div class="cluster-badge" style="background-color: ${
            cluster.color
          };">
            ${cluster.size}개 상품
          </div>
        </div>
        
        <div class="cluster-metrics">
          <div class="metric-item">
            <span class="metric-value">${cluster.percentage}%</span>
            <span class="metric-label">비율</span>
          </div>
          <div class="metric-item">
            <span class="metric-value">${
              cluster.metrics?.avg_turnover?.toFixed(2) || "-"
            }</span>
            <span class="metric-label">평균 회전율</span>
          </div>
        </div>
        
        <div class="cluster-strategy">
          💡 ${cluster.strategy}
        </div>
        
        ${
          cluster.key_products?.length > 0
            ? `
          <div class="key-products mt-2">
            <strong>주요 상품:</strong>
            ${cluster.key_products
              .slice(0, 2)
              .map(
                (product) => `
              <div class="text-muted">${product.product_name?.substring(
                0,
                25
              )}...</div>
            `
              )
              .join("")}
          </div>
        `
            : ""
        }
      </div>
    `
      )
      .join("");

    // 클러스터 카드 클릭 이벤트
    this.clustersOverview.querySelectorAll(".cluster-card").forEach((card) => {
      card.addEventListener("click", (e) => {
        const clusterId = e.currentTarget.dataset.clusterId;
        this.showClusterDetails(clusterId);
      });
    });
  }

  getClusterPriorityClass(clusterName) {
    if (clusterName.includes("프리미엄 고회전")) {
      return "high-priority";
    } else if (clusterName.includes("주력 상품")) {
      return "medium-priority";
    } else {
      return "low-priority";
    }
  }

  renderClusterChart() {
    if (!this.clustersData || !this.clusterCanvas) return;

    const ctx = this.clusterCanvas.getContext("2d");

    // 기존 차트 제거
    if (this.clusterChart) {
      this.clusterChart.destroy();
    }

    const clusters = this.clustersData.clusters;

    this.clusterChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: clusters.map((c) => c.cluster_name),
        datasets: [
          {
            data: clusters.map((c) => c.size),
            backgroundColor: clusters.map((c) => c.color),
            borderColor: "#ffffff",
            borderWidth: 3,
            hoverOffset: 10,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: {
            display: true,
            text: `제품 클러스터 분포 (총 ${this.clustersData.total_products}개 상품)`,
            font: { size: 16, weight: "bold" },
          },
          legend: {
            position: "bottom",
            labels: {
              padding: 20,
              usePointStyle: true,
              font: { size: 12 },
            },
          },
          tooltip: {
            callbacks: {
              label: (context) => {
                const cluster = clusters[context.dataIndex];
                return [
                  `${cluster.cluster_name}: ${cluster.size}개 상품`,
                  `비율: ${cluster.percentage.toFixed(1)}%`,
                  `평균 회전율: ${
                    cluster.metrics?.avg_turnover?.toFixed(2) || "-"
                  }`,
                ];
              },
            },
          },
        },
        onClick: (event, activeElements) => {
          if (activeElements.length > 0) {
            const index = activeElements[0].index;
            const clusterId = clusters[index].cluster_id;
            this.showClusterDetails(clusterId);
          }
        },
      },
    });
  }

  async loadHighTurnoverProducts() {
    try {
      const response = await fetch("/api/ml/product-clustering/high-turnover");

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.renderHighTurnoverProducts(data);
    } catch (error) {
      console.error("고회전 상품 로딩 실패:", error);
      this.showHighTurnoverError(error.message);
    }
  }

  renderHighTurnoverProducts(data) {
    if (!data || !this.highTurnoverGrid) return;

    if (data.high_turnover_products?.length === 0) {
      this.highTurnoverGrid.innerHTML = `
        <div class="text-center text-muted">
          고회전 상품이 없습니다.
        </div>
      `;
      return;
    }

    this.highTurnoverGrid.innerHTML = data.high_turnover_products
      .map(
        (product) => `
      <div class="turnover-product-card" data-product-code="${
        product.product_code
      }">
        <div class="product-header">
          <span class="product-code">${product.product_code}</span>
          <span class="turnover-badge">${product.turnover_ratio.toFixed(
            1
          )}배</span>
        </div>
        <div class="product-name">${product.product_name}</div>
        <div class="product-metrics">
          <span>클러스터: ${product.cluster_name}</span>
          <span>중요도: ${product.business_importance?.toFixed(2) || "-"}</span>
        </div>
      </div>
    `
      )
      .join("");

    // 상품 카드 클릭 이벤트
    this.highTurnoverGrid
      .querySelectorAll(".turnover-product-card")
      .forEach((card) => {
        card.addEventListener("click", (e) => {
          const productCode = e.currentTarget.dataset.productCode;
          this.searchSpecificProduct(productCode);
        });
      });
  }

  async searchProduct() {
    const productCode = this.productCodeInput?.value?.trim();

    if (!productCode) {
      alert("상품 코드를 입력해주세요.");
      return;
    }

    await this.searchSpecificProduct(productCode);
  }

  async searchSpecificProduct(productCode) {
    try {
      this.showProductSearchLoading(true);

      const response = await fetch(
        `/api/ml/product-clustering/product/${productCode}`
      );

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error(`상품 코드 '${productCode}'를 찾을 수 없습니다.`);
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const productData = await response.json();
      this.renderProductAnalysis(productData);
    } catch (error) {
      console.error("상품 검색 실패:", error);
      this.showProductSearchError(error.message);
    } finally {
      this.showProductSearchLoading(false);
    }
  }

  renderProductAnalysis(productData) {
    if (!this.productAnalysisResult) return;

    this.productAnalysisResult.style.display = "block";
    this.productAnalysisResult.innerHTML = `
      <div class="analysis-header">
        <div>
          <h5 class="mb-1">${productData.product_name}</h5>
          <span class="text-muted">${productData.product_code}</span>
        </div>
        <div class="analysis-cluster-badge" style="background-color: ${
          productData.color
        };">
          ${productData.cluster_name}
        </div>
      </div>
      
      <div class="analysis-strategy">
        <strong>관리 전략:</strong> ${productData.strategy}
      </div>
      
      <div class="analysis-metrics">
        <div class="analysis-metric">
          <div class="analysis-metric-value">${
            productData.product_metrics?.turnover_ratio?.toFixed(2) || "-"
          }</div>
          <div class="analysis-metric-label">회전율</div>
        </div>
        <div class="analysis-metric">
          <div class="analysis-metric-value">${
            productData.product_metrics?.current_stock || "-"
          }</div>
          <div class="analysis-metric-label">현재고</div>
        </div>
        <div class="analysis-metric">
          <div class="analysis-metric-value">${
            productData.product_metrics?.rack_name || "-"
          }</div>
          <div class="analysis-metric-label">랙 위치</div>
        </div>
        <div class="analysis-metric">
          <div class="analysis-metric-value">${
            productData.product_metrics?.stock_status || "-"
          }</div>
          <div class="analysis-metric-label">재고 상태</div>
        </div>
      </div>
    `;
  }

  showProductSearchLoading(show) {
    if (!this.productSearchBtn) return;

    if (show) {
      this.productSearchBtn.disabled = true;
      this.productSearchBtn.innerHTML =
        '<i class="fas fa-spinner fa-spin"></i> 분석 중...';
    } else {
      this.productSearchBtn.disabled = false;
      this.productSearchBtn.innerHTML = '<i class="fas fa-search"></i> 분석';
    }
  }

  showProductSearchError(message) {
    if (!this.productAnalysisResult) return;

    this.productAnalysisResult.style.display = "block";
    this.productAnalysisResult.innerHTML = `
      <div class="alert alert-danger">
        <i class="fas fa-exclamation-triangle"></i> ${message}
      </div>
    `;
  }

  async showClusterDetails(clusterId) {
    try {
      const response = await fetch(
        `/api/ml/product-clustering/cluster/${clusterId}`
      );

      if (!response.ok) {
        throw new Error(
          `클러스터 정보를 가져올 수 없습니다: ${response.statusText}`
        );
      }

      const clusterData = await response.json();

      // 간단한 모달이나 알림으로 표시 (실제로는 더 정교한 UI 필요)
      alert(`
클러스터: ${clusterData.cluster_name}
상품 수: ${clusterData.size}개 (${clusterData.percentage.toFixed(1)}%)
관리 전략: ${clusterData.strategy}
평균 회전율: ${clusterData.metrics?.avg_turnover?.toFixed(2) || "-"}
      `);
    } catch (error) {
      console.error("클러스터 상세 조회 실패:", error);
      alert("클러스터 정보를 가져오는데 실패했습니다.");
    }
  }

  async refreshData() {
    this.showRefreshLoading(true);
    try {
      await this.loadInitialData();
      this.showMessage("데이터를 성공적으로 새로고침했습니다.", "success");
    } catch (error) {
      this.showMessage("데이터 새로고침에 실패했습니다.", "error");
    } finally {
      this.showRefreshLoading(false);
    }
  }

  async retrainModel() {
    if (!confirm("모델을 재훈련하시겠습니까? 시간이 소요될 수 있습니다.")) {
      return;
    }

    this.showRetrainLoading(true);
    try {
      const response = await fetch("/api/ml/product-clustering/retrain", {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error(`재훈련 실패: ${response.statusText}`);
      }

      const result = await response.json();
      this.showMessage("모델이 성공적으로 재훈련되었습니다.", "success");

      // 데이터 새로고침
      await this.loadInitialData();
    } catch (error) {
      console.error("모델 재훈련 실패:", error);
      this.showMessage(`모델 재훈련에 실패했습니다: ${error.message}`, "error");
    } finally {
      this.showRetrainLoading(false);
    }
  }

  async exportResults() {
    try {
      if (!this.clustersData) {
        throw new Error("내보낼 데이터가 없습니다.");
      }

      const dataStr = JSON.stringify(this.clustersData, null, 2);
      const dataBlob = new Blob([dataStr], { type: "application/json" });

      const link = document.createElement("a");
      link.href = URL.createObjectURL(dataBlob);
      link.download = `product_clusters_${
        new Date().toISOString().split("T")[0]
      }.json`;
      link.click();

      this.showMessage("클러스터 결과를 성공적으로 내보냈습니다.", "success");
    } catch (error) {
      console.error("결과 내보내기 실패:", error);
      this.showMessage("결과 내보내기에 실패했습니다.", "error");
    }
  }

  showRefreshLoading(show) {
    if (!this.refreshBtn) return;

    if (show) {
      this.refreshBtn.disabled = true;
      this.refreshBtn.innerHTML =
        '<i class="fas fa-spinner fa-spin"></i> 새로고침 중...';
    } else {
      this.refreshBtn.disabled = false;
      this.refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> 새로고침';
    }
  }

  showRetrainLoading(show) {
    if (!this.retrainBtn) return;

    if (show) {
      this.retrainBtn.disabled = true;
      this.retrainBtn.innerHTML =
        '<i class="fas fa-spinner fa-spin"></i> 재훈련 중...';
    } else {
      this.retrainBtn.disabled = false;
      this.retrainBtn.innerHTML = '<i class="fas fa-brain"></i> 모델 재훈련';
    }
  }

  showClustersError(message) {
    if (!this.clustersOverview) return;

    this.clustersOverview.innerHTML = `
      <div class="alert alert-danger text-center">
        <i class="fas fa-exclamation-triangle"></i> 
        클러스터 데이터 로딩 실패: ${message}
      </div>
    `;
  }

  showHighTurnoverError(message) {
    if (!this.highTurnoverGrid) return;

    this.highTurnoverGrid.innerHTML = `
      <div class="alert alert-warning text-center">
        <i class="fas fa-exclamation-triangle"></i> 
        고회전 상품 로딩 실패: ${message}
      </div>
    `;
  }

  showError(message) {
    console.error("ML 클러스터링 오류:", message);
    // 전역 에러 표시 (실제로는 토스트나 알림 시스템 사용)
  }

  showMessage(message, type = "info") {
    // 간단한 알림 (실제로는 토스트 시스템 사용)
    console.log(`[${type.toUpperCase()}] ${message}`);

    if (type === "error") {
      alert(`오류: ${message}`);
    } else if (type === "success") {
      alert(`성공: ${message}`);
    }
  }
}

// DOM 로드 완료 시 초기화
document.addEventListener("DOMContentLoaded", () => {
  // ML 클러스터링 매니저 초기화
  if (document.getElementById("mlModelStatus")) {
    window.mlClusteringManager = new MLClusteringManager();
  }
});
