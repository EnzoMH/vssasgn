// 차트 관리 클래스
class ChartManager {
  constructor() {
    this.charts = {};
    this.isDarkMode = false;
    this.colors = {
      primary: "#3b82f6",
      secondary: "#10b981",
      warning: "#f59e0b",
      danger: "#ef4444",
      gray: "#6b7280",
    };

    // 다크모드 테마 설정
    this.lightTheme = {
      textColor: "#1f2937",
      gridColor: "#e5e7eb",
      backgroundColor: "#ffffff",
      backgroundColorSecondary: "#f9fafb",
    };

    this.darkTheme = {
      textColor: "#f9fafb",
      gridColor: "#374151",
      backgroundColor: "#1f2937",
      backgroundColorSecondary: "#111827",
    };

    this.bindThemeEvents();
  }

  // 테마 이벤트 바인딩
  bindThemeEvents() {
    // 테마 변경 이벤트 리스너
    window.addEventListener("themechange", (e) => {
      this.setTheme(e.detail.theme);
    });

    // 초기 테마 감지
    this.detectInitialTheme();
  }

  // 초기 테마 감지
  detectInitialTheme() {
    const theme =
      document.documentElement.getAttribute("data-theme") || "light";
    this.setTheme(theme);
  }

  // 테마 설정
  setTheme(theme) {
    this.isDarkMode = theme === "dark";
    this.updateChartDefaults();
    this.updateExistingCharts();
  }

  // Chart.js 기본값 업데이트
  updateChartDefaults() {
    if (!window.Chart) return;

    const currentTheme = this.getCurrentTheme();

    // Chart.js 글로벌 기본값 설정 (v3+ 호환)
    Chart.defaults.color = currentTheme.textColor;
    Chart.defaults.borderColor = currentTheme.gridColor;
    Chart.defaults.backgroundColor = currentTheme.backgroundColor;

    // 플러그인 기본값 (안전한 설정)
    if (!Chart.defaults.plugins) Chart.defaults.plugins = {};
    if (!Chart.defaults.plugins.legend) Chart.defaults.plugins.legend = {};
    if (!Chart.defaults.plugins.legend.labels)
      Chart.defaults.plugins.legend.labels = {};
    if (!Chart.defaults.plugins.tooltip) Chart.defaults.plugins.tooltip = {};

    Chart.defaults.plugins.legend.labels.color = currentTheme.textColor;
    Chart.defaults.plugins.tooltip.backgroundColor =
      currentTheme.backgroundColor;
    Chart.defaults.plugins.tooltip.titleColor = currentTheme.textColor;
    Chart.defaults.plugins.tooltip.bodyColor = currentTheme.textColor;
  }

  // 기존 차트들의 테마만 업데이트
  updateExistingCharts() {
    Object.keys(this.charts).forEach((chartId) => {
      const chart = this.charts[chartId];
      if (chart && chart.update) {
        this.updateChartTheme(chart);
      }
    });
  }

  // 모든 차트 업데이트 (데이터 포함)
  updateAllCharts() {
    this.updateExistingCharts();
  }

  // 개별 차트 테마 업데이트
  updateChartTheme(chart) {
    const currentTheme = this.getCurrentTheme();

    // 스케일 색상 업데이트
    if (chart.options.scales) {
      Object.keys(chart.options.scales).forEach((scaleId) => {
        const scale = chart.options.scales[scaleId];
        if (scale.ticks) {
          scale.ticks.color = currentTheme.textColor;
        }
        if (scale.grid) {
          scale.grid.color = currentTheme.gridColor;
        }
      });
    }

    // 범례 색상 업데이트
    if (chart.options.plugins && chart.options.plugins.legend) {
      chart.options.plugins.legend.labels.color = currentTheme.textColor;
    }

    // 툴팁 색상 업데이트
    if (chart.options.plugins && chart.options.plugins.tooltip) {
      chart.options.plugins.tooltip.backgroundColor =
        currentTheme.backgroundColor;
      chart.options.plugins.tooltip.titleColor = currentTheme.textColor;
      chart.options.plugins.tooltip.bodyColor = currentTheme.textColor;
    }

    // 데이터셋 색상 업데이트 (필요한 경우)
    if (chart.data.datasets) {
      chart.data.datasets.forEach((dataset) => {
        // 보조 색상들만 테마에 따라 변경
        if (
          dataset.backgroundColor === "#e5e7eb" ||
          dataset.backgroundColor === "#374151"
        ) {
          dataset.backgroundColor = this.isDarkMode ? "#374151" : "#e5e7eb";
        }
        if (
          dataset.borderColor === "#d1d5db" ||
          dataset.borderColor === "#4b5563"
        ) {
          dataset.borderColor = this.isDarkMode ? "#4b5563" : "#d1d5db";
        }
      });
    }

    chart.update("none");
  }

  // 현재 테마 가져오기
  getCurrentTheme() {
    return this.isDarkMode ? this.darkTheme : this.lightTheme;
  }

  // 테마별 옵션 생성
  getThemedOptions(baseOptions = {}) {
    const currentTheme = this.getCurrentTheme();

    const themedOptions = {
      ...baseOptions,
      plugins: {
        ...baseOptions.plugins,
        legend: {
          ...baseOptions.plugins?.legend,
          labels: {
            ...baseOptions.plugins?.legend?.labels,
            color: currentTheme.textColor,
          },
        },
        tooltip: {
          ...baseOptions.plugins?.tooltip,
          backgroundColor: currentTheme.backgroundColor,
          titleColor: currentTheme.textColor,
          bodyColor: currentTheme.textColor,
          borderColor: currentTheme.gridColor,
          borderWidth: 1,
        },
      },
      scales: {
        ...baseOptions.scales,
      },
    };

    // 스케일 테마 적용
    if (themedOptions.scales) {
      Object.keys(themedOptions.scales).forEach((scaleId) => {
        const scale = themedOptions.scales[scaleId];
        themedOptions.scales[scaleId] = {
          ...scale,
          ticks: {
            ...scale.ticks,
            color: currentTheme.textColor,
          },
          grid: {
            ...scale.grid,
            color: currentTheme.gridColor,
          },
        };
      });
    }

    return themedOptions;
  }

  // 모든 차트 리사이즈
  resizeCharts() {
    Object.keys(this.charts).forEach((chartId) => {
      const chart = this.charts[chartId];
      if (chart && chart.resize) {
        chart.resize();
      }
    });
  }

  // 차트 인스턴스 저장
  setChart(id, chart) {
    if (this.charts[id]) {
      this.charts[id].destroy();
    }
    this.charts[id] = chart;
  }

  // 랙별 재고 현황 바 차트 (실제 rawdata 기반)
  createInventoryChart(data, canvasId = "inventoryChart") {
    console.log("📦 재고 차트 데이터:", data);

    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const currentTheme = this.getCurrentTheme();

    const baseOptions = {
      responsive: true,
      maintainAspectRatio: false,
      aspectRatio: 2,
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
          max: function (context) {
            const max = Math.max(
              ...context.chart.data.datasets.flatMap((dataset) => dataset.data)
            );
            return Math.ceil(max * 1.2);
          },
          ticks: {
            callback: function (value) {
              return NumberUtils.formatNumber(value);
            },
            maxTicksLimit: 8,
          },
        },
      },
      layout: {
        padding: 10,
      },
    };

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
            backgroundColor: this.isDarkMode ? "#374151" : "#e5e7eb",
            borderColor: this.isDarkMode ? "#4b5563" : "#d1d5db",
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      },
      options: this.getThemedOptions(baseOptions),
    });

    this.setChart(canvasId, chart);
    return chart;
  }

  // 일별 입출고 트렌드 라인 차트
  createTrendChart(data, canvasId = "trendChart") {
    console.log("📈 트렌드 차트 데이터:", data);

    const ctx = document.getElementById(canvasId);
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
        aspectRatio: 2, // 명시적 비율 설정
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
            max: function (context) {
              // Y축 최대값을 데이터 최대값의 1.2배로 제한
              const max = Math.max(
                ...context.chart.data.datasets.flatMap(
                  (dataset) => dataset.data
                )
              );
              return Math.ceil(max * 1.2);
            },
            ticks: {
              callback: function (value) {
                return NumberUtils.formatNumber(value);
              },
              maxTicksLimit: 8, // 최대 틱 개수 제한
            },
          },
        },
        interaction: {
          intersect: false,
          mode: "index",
        },
        layout: {
          padding: 10,
        },
      },
    });

    this.setChart(canvasId, chart);
    return chart;
  }

  // 제품 카테고리 분포 파이 차트 (실제 rawdata 기반)
  createCategoryChart(data, canvasId = "categoryChart") {
    console.log("📊 카테고리 차트 데이터:", data);

    const ctx = document.getElementById(canvasId);
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

    this.setChart(canvasId, chart);
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

  // LLM을 활용한 차트 생성
  async generateAIChart(userRequest, containerId = "aiGeneratedChart") {
    try {
      // 로딩 상태 표시
      this.showChartLoading(containerId);

      console.log(`🤖 AI 차트 생성 요청: ${userRequest}`);

      // API 호출
      const response = await fetch("/api/ai/generate-chart", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_request: userRequest,
          context: "",
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();

      // 로딩 상태 제거
      this.hideChartLoading(containerId);

      if (result.success || result.chart_config) {
        const chartConfig = result.chart_config;
        console.log("✅ AI 차트 설정 수신:", chartConfig);

        // 차트 생성
        const chart = this.createDynamicChart(containerId, chartConfig);

        if (chart) {
          // 성공 메시지 표시
          if (!result.success) {
            NotificationManager.warning(
              `차트를 생성했지만 일부 문제가 있었습니다: ${result.message}`
            );
          } else {
            NotificationManager.success("AI가 차트를 성공적으로 생성했습니다!");
          }

          return {
            success: true,
            chart: chart,
            config: chartConfig,
            message: result.message,
          };
        } else {
          throw new Error("차트 생성에 실패했습니다");
        }
      } else {
        throw new Error(result.error || result.message || "알 수 없는 오류");
      }
    } catch (error) {
      console.error("❌ AI 차트 생성 오류:", error);
      this.hideChartLoading(containerId);
      this.showChartError(containerId, error.message);
      NotificationManager.error(`AI 차트 생성 실패: ${error.message}`);

      return {
        success: false,
        error: error.message,
      };
    }
  }

  // 동적 차트 생성 (AI가 생성한 설정 사용)
  createDynamicChart(containerId, chartConfig) {
    try {
      const canvas = document.getElementById(containerId);
      if (!canvas) {
        console.error(`차트 컨테이너를 찾을 수 없습니다: ${containerId}`);
        return null;
      }

      // 기존 차트가 있다면 제거
      if (this.charts[containerId]) {
        this.charts[containerId].destroy();
      }

      // Chart.js 설정 생성 (안전한 기본값 적용)
      const safeOptions = {
        responsive: true,
        maintainAspectRatio: false,
        aspectRatio: 2, // 명시적 비율 설정
        layout: {
          padding: 10,
        },
        ...chartConfig.options,
      };

      // Y축 스케일에 안전한 제한 추가
      if (safeOptions.scales && safeOptions.scales.y) {
        safeOptions.scales.y = {
          beginAtZero: true,
          maxTicksLimit: 8,
          ...safeOptions.scales.y,
        };
      } else if (
        chartConfig.chart_type !== "pie" &&
        chartConfig.chart_type !== "doughnut"
      ) {
        safeOptions.scales = {
          y: {
            beginAtZero: true,
            maxTicksLimit: 8,
            ticks: {
              callback: function (value) {
                return typeof value === "number"
                  ? value.toLocaleString()
                  : value;
              },
            },
          },
          ...safeOptions.scales,
        };
      }

      const config = {
        type: chartConfig.chart_type,
        data: chartConfig.data,
        options: safeOptions,
      };

      // 차트 생성
      const chart = new Chart(canvas, config);
      this.setChart(containerId, chart);

      console.log(
        `✅ 동적 차트 생성 완료: ${chartConfig.chart_type} - ${chartConfig.title}`
      );
      return chart;
    } catch (error) {
      console.error("동적 차트 생성 오류:", error);
      return null;
    }
  }

  // 차트 로딩 상태 표시
  showChartLoading(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
      container.style.position = "relative";
      container.innerHTML = `
        <div class="chart-loading" style="
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          text-align: center;
          z-index: 1000;
        ">
          <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
            <span class="visually-hidden">로딩중...</span>
          </div>
          <div class="mt-2 text-muted">AI가 차트를 생성하고 있습니다...</div>
        </div>
      `;
    }
  }

  // 차트 로딩 상태 제거
  hideChartLoading(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
      const loading = container.querySelector(".chart-loading");
      if (loading) {
        loading.remove();
      }
    }
  }

  // 차트 오류 표시
  showChartError(containerId, errorMessage) {
    const container = document.getElementById(containerId);
    if (container) {
      container.innerHTML = `
        <div class="chart-error text-center p-4" style="color: #dc3545;">
          <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
          <div class="fw-bold">차트 생성 실패</div>
          <div class="small text-muted mt-1">${errorMessage}</div>
          <button class="btn btn-outline-primary btn-sm mt-2" onclick="location.reload()">
            다시 시도
          </button>
        </div>
      `;
    }
  }
}

// 차트 매니저는 dashboard.js에서 초기화됨
