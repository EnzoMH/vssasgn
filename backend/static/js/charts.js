// 차트 관리 클래스
class ChartManager {
  constructor() {
    this.charts = {};
    this.colors = {
      primary: "#3b82f6",
      secondary: "#10b981",
      warning: "#f59e0b",
      danger: "#ef4444",
      gray: "#6b7280",
    };
  }

  // 차트 인스턴스 저장
  setChart(id, chart) {
    if (this.charts[id]) {
      this.charts[id].destroy();
    }
    this.charts[id] = chart;
  }

  // 랙별 재고 현황 바 차트
  createInventoryChart(data) {
    const ctx = document.getElementById("inventoryChart");
    if (!ctx) return;

    const chart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((item) => item.rackName),
        datasets: [
          {
            label: "현재 재고",
            data: data.map((item) => item.currentStock),
            backgroundColor: this.colors.primary,
            borderColor: this.colors.primary,
            borderWidth: 1,
            borderRadius: 4,
          },
          {
            label: "최대 용량",
            data: data.map((item) => item.capacity),
            backgroundColor: "#e5e7eb",
            borderColor: "#d1d5db",
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: {
            display: false,
          },
          legend: {
            position: "top",
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                return `${context.dataset.label}: ${NumberUtils.formatNumber(
                  context.parsed.y
                )}개`;
              },
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: function (value) {
                return NumberUtils.formatNumber(value);
              },
            },
          },
        },
      },
    });

    this.setChart("inventory", chart);
    return chart;
  }

  // 일별 입출고 트렌드 라인 차트
  createTrendChart(data) {
    const ctx = document.getElementById("trendChart");
    if (!ctx) return;

    const chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: data.map((item) => DateUtils.formatDate(item.date)),
        datasets: [
          {
            label: "입고량",
            data: data.map((item) => item.inbound || 0),
            borderColor: this.colors.secondary,
            backgroundColor: this.colors.secondary + "20",
            borderWidth: 3,
            fill: false,
            tension: 0.1,
            pointBackgroundColor: this.colors.secondary,
            pointBorderColor: "#ffffff",
            pointBorderWidth: 2,
            pointRadius: 6,
          },
          {
            label: "출고량",
            data: data.map((item) => item.outbound || 0),
            borderColor: this.colors.danger,
            backgroundColor: this.colors.danger + "20",
            borderWidth: 3,
            fill: false,
            tension: 0.1,
            pointBackgroundColor: this.colors.danger,
            pointBorderColor: "#ffffff",
            pointBorderWidth: 2,
            pointRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "top",
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                return `${context.dataset.label}: ${NumberUtils.formatNumber(
                  context.parsed.y
                )}건`;
              },
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: function (value) {
                return NumberUtils.formatNumber(value);
              },
            },
          },
        },
        interaction: {
          intersect: false,
          mode: "index",
        },
      },
    });

    this.setChart("trend", chart);
    return chart;
  }

  // 제품 카테고리 분포 파이 차트
  createCategoryChart(data) {
    const ctx = document.getElementById("categoryChart");
    if (!ctx) return;

    // 색상 배열 생성
    const backgroundColors = [
      this.colors.primary,
      this.colors.secondary,
      this.colors.warning,
      this.colors.danger,
      "#8b5cf6",
      "#f97316",
      "#06b6d4",
      "#84cc16",
    ];

    const chart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: data.map((item) => item.name),
        datasets: [
          {
            data: data.map((item) => item.value),
            backgroundColor: backgroundColors.slice(0, data.length),
            borderWidth: 2,
            borderColor: "#ffffff",
            hoverBorderWidth: 3,
            hoverBorderColor: "#ffffff",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "right",
            labels: {
              usePointStyle: true,
              padding: 20,
            },
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                const percentage = ((context.parsed / total) * 100).toFixed(1);
                return `${context.label}: ${NumberUtils.formatNumber(
                  context.parsed
                )}개 (${percentage}%)`;
              },
            },
          },
        },
        cutout: "50%",
      },
    });

    this.setChart("category", chart);
    return chart;
  }

  // ML 결과를 위한 바 차트 (수요 예측 등)
  createMLResultChart(data, type) {
    const container = document.getElementById("mlResults");
    if (!container) return;

    // 기존 차트 제거
    container.innerHTML = "";

    if (type === "demand") {
      this.createDemandPredictionChart(container, data);
    } else if (type === "cluster") {
      this.createClusterAnalysisChart(container, data);
    } else if (type === "anomaly") {
      this.createAnomalyDetectionChart(container, data);
    }
  }

  // 수요 예측 차트
  createDemandPredictionChart(container, data) {
    const canvas = document.createElement("canvas");
    canvas.id = "demandChart";
    container.appendChild(canvas);

    const chart = new Chart(canvas, {
      type: "bar",
      data: {
        labels: ["예측 수요량"],
        datasets: [
          {
            label: "예측값",
            data: data.prediction || [0],
            backgroundColor: this.colors.warning,
            borderColor: this.colors.warning,
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            callbacks: {
              label: function (context) {
                return `예측 수요량: ${NumberUtils.formatNumber(
                  context.parsed.y
                )}개`;
              },
            },
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: function (value) {
                return NumberUtils.formatNumber(value);
              },
            },
          },
        },
      },
    });

    this.setChart("demand", chart);
  }

  // 클러스터 분석 차트
  createClusterAnalysisChart(container, data) {
    const chartDiv = document.createElement("div");
    chartDiv.innerHTML = `
            <h4><i class="fas fa-layer-group"></i> 제품 클러스터링 결과</h4>
            <div class="cluster-results">
                ${
                  data.clusters
                    ? data.clusters
                        .map(
                          (cluster, index) => `
                    <div class="cluster-item">
                        <span class="cluster-badge" style="background-color: ${this.getClusterColor(
                          cluster
                        )}">
                            클러스터 ${cluster}
                        </span>
                        <span>제품 ${index + 1}</span>
                    </div>
                `
                        )
                        .join("")
                    : "<p>클러스터링 데이터가 없습니다.</p>"
                }
            </div>
        `;
    container.appendChild(chartDiv);

    // 클러스터 결과 스타일
    const style = document.createElement("style");
    style.textContent = `
            .cluster-results {
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                margin-top: 1rem;
            }
            .cluster-item {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.5rem;
                background-color: var(--gray-100);
                border-radius: var(--border-radius-sm);
            }
            .cluster-badge {
                padding: 0.25rem 0.5rem;
                border-radius: var(--border-radius-sm);
                color: white;
                font-size: 0.75rem;
                font-weight: 500;
            }
        `;
    if (!document.querySelector("#clusterStyles")) {
      style.id = "clusterStyles";
      document.head.appendChild(style);
    }
  }

  // 이상 탐지 차트
  createAnomalyDetectionChart(container, data) {
    const chartDiv = document.createElement("div");
    chartDiv.innerHTML = `
            <h4><i class="fas fa-exclamation-triangle"></i> 이상 탐지 결과</h4>
            <div class="anomaly-results">
                ${
                  data.anomalies && data.anomalies.length > 0
                    ? `
                    <div class="anomaly-summary">
                        <span class="anomaly-count">${
                          data.anomalies.length
                        }개의 이상 징후 발견</span>
                    </div>
                    <div class="anomaly-list">
                        ${data.anomalies
                          .slice(0, 5)
                          .map(
                            (anomaly, index) => `
                            <div class="anomaly-item">
                                <i class="fas fa-warning" style="color: var(--danger);"></i>
                                <span>이상 데이터 ${index + 1}</span>
                                <span class="anomaly-score">점수: ${NumberUtils.formatDecimal(
                                  anomaly.score || Math.random(),
                                  2
                                )}</span>
                            </div>
                        `
                          )
                          .join("")}
                    </div>
                `
                    : '<p style="color: var(--secondary);"><i class="fas fa-check-circle"></i> 이상 징후가 발견되지 않았습니다.</p>'
                }
            </div>
        `;
    container.appendChild(chartDiv);

    // 이상 탐지 결과 스타일
    const style = document.createElement("style");
    style.textContent = `
            .anomaly-summary {
                padding: 1rem;
                background-color: var(--danger);
                color: white;
                border-radius: var(--border-radius-sm);
                margin-bottom: 1rem;
                text-align: center;
            }
            .anomaly-count {
                font-weight: 600;
            }
            .anomaly-list {
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
            }
            .anomaly-item {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.75rem;
                background-color: var(--gray-100);
                border-radius: var(--border-radius-sm);
                border-left: 4px solid var(--danger);
            }
            .anomaly-score {
                font-size: 0.875rem;
                color: var(--gray-500);
            }
        `;
    if (!document.querySelector("#anomalyStyles")) {
      style.id = "anomalyStyles";
      document.head.appendChild(style);
    }
  }

  // 클러스터 색상 가져오기
  getClusterColor(cluster) {
    const colors = [
      this.colors.primary,
      this.colors.secondary,
      this.colors.warning,
      this.colors.danger,
    ];
    return colors[cluster % colors.length];
  }

  // 모든 차트 업데이트
  updateAllCharts(dashboardData) {
    try {
      if (dashboardData.inventoryData) {
        this.createInventoryChart(dashboardData.inventoryData);
      }
      if (dashboardData.trendData) {
        this.createTrendChart(dashboardData.trendData);
      }
      if (dashboardData.categoryData) {
        this.createCategoryChart(dashboardData.categoryData);
      }
    } catch (error) {
      console.error("차트 업데이트 오류:", error);
      NotificationManager.error("차트를 업데이트하는 중 오류가 발생했습니다.");
    }
  }

  // 차트 크기 조정
  resizeCharts() {
    Object.values(this.charts).forEach((chart) => {
      if (chart && typeof chart.resize === "function") {
        chart.resize();
      }
    });
  }

  // 모든 차트 제거
  destroyAllCharts() {
    Object.values(this.charts).forEach((chart) => {
      if (chart && typeof chart.destroy === "function") {
        chart.destroy();
      }
    });
    this.charts = {};
  }
}

// 전역 차트 매니저 인스턴스
const chartManager = new ChartManager();

// 윈도우 리사이즈 이벤트 리스너
window.addEventListener("resize", () => {
  chartManager.resizeCharts();
});
