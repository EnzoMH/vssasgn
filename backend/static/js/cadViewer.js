// CAD 뷰어 및 파일 업로드 관리 클래스
class CADViewer {
  constructor() {
    this.canvas = null;
    this.ctx = null;
    this.scale = 1;
    this.offsetX = 0;
    this.offsetY = 0;
    this.isDragging = false;
    this.lastMouseX = 0;
    this.lastMouseY = 0;
    this.warehouseData = null;
    this.selectedRack = null;
    this.showGrid = false;
    this.showStockOverlay = true;

    this.initializeElements();
    this.bindEvents();
  }

  initializeElements() {
    // DOM 요소들
    this.elements = {
      uploadBtn: document.getElementById("uploadCADBtn"),
      uploadArea: document.getElementById("cadUploadArea"),
      dropzone: document.getElementById("cadDropzone"),
      fileInput: document.getElementById("cadFileInput"),
      selectFileBtn: document.getElementById("selectCADFileBtn"),
      viewer: document.getElementById("cadViewer"),
      canvas: document.getElementById("warehouseCanvas"),
      loading: document.getElementById("cadLoading"),
      progress: document.getElementById("cadUploadProgress"),
      progressFill: document.getElementById("cadProgressFill"),
      progressText: document.getElementById("cadProgressText"),
      result: document.getElementById("cadAnalysisResult"),
      infoPanel: document.getElementById("selectedRackInfo"),
      toggleLayersBtn: document.getElementById("toggleLayersBtn"),
      zoomFitBtn: document.getElementById("zoomFitBtn"),
    };

    // Canvas 초기화
    if (this.elements.canvas) {
      this.canvas = this.elements.canvas;
      this.ctx = this.canvas.getContext("2d");
      this.setupCanvas();
    }
  }

  bindEvents() {
    // 업로드 버튼 클릭
    if (this.elements.uploadBtn) {
      this.elements.uploadBtn.addEventListener("click", () => {
        this.elements.fileInput.click();
      });
    }

    // 파일 선택 버튼 클릭
    if (this.elements.selectFileBtn) {
      this.elements.selectFileBtn.addEventListener("click", () => {
        this.elements.fileInput.click();
      });
    }

    // 파일 선택
    if (this.elements.fileInput) {
      this.elements.fileInput.addEventListener("change", (e) => {
        this.handleFileSelect(e.target.files[0]);
      });
    }

    // 드래그 앤 드롭
    if (this.elements.dropzone) {
      this.elements.dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        this.elements.dropzone.classList.add("dragover");
      });

      this.elements.dropzone.addEventListener("dragleave", (e) => {
        e.preventDefault();
        this.elements.dropzone.classList.remove("dragover");
      });

      this.elements.dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        this.elements.dropzone.classList.remove("dragover");
        const files = e.dataTransfer.files;
        if (files.length > 0) {
          this.handleFileSelect(files[0]);
        }
      });
    }

    // Canvas 이벤트
    if (this.canvas) {
      this.canvas.addEventListener("mousedown", (e) => this.handleMouseDown(e));
      this.canvas.addEventListener("mousemove", (e) => this.handleMouseMove(e));
      this.canvas.addEventListener("mouseup", (e) => this.handleMouseUp(e));
      this.canvas.addEventListener("wheel", (e) => this.handleWheel(e));
      this.canvas.addEventListener("click", (e) => this.handleCanvasClick(e));
    }

    // 컨트롤 버튼들
    if (this.elements.zoomFitBtn) {
      this.elements.zoomFitBtn.addEventListener("click", () => {
        this.zoomToFit();
      });
    }

    if (this.elements.toggleLayersBtn) {
      this.elements.toggleLayersBtn.addEventListener("click", () => {
        this.toggleLayers();
      });
    }
  }

  setupCanvas() {
    // Canvas 크기 설정
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = rect.width;
    this.canvas.height = rect.height;

    // 초기 배경 그리기
    this.drawBackground();
  }

  drawBackground() {
    this.ctx.fillStyle = "#f8fafc";
    this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    // 그리드 그리기 (데이터가 있을 때만)
    if (this.warehouseData && this.showGrid) {
      this.drawGrid();
    }
  }

  drawGrid() {
    // 그리드는 showGrid 옵션이 활성화되어야만 그림
    if (!this.showGrid) {
      return;
    }

    const gridSize = 20 * this.scale;
    this.ctx.strokeStyle = "#e2e8f0";
    this.ctx.lineWidth = 1;

    this.ctx.beginPath();

    // 수직선
    for (
      let x = this.offsetX % gridSize;
      x < this.canvas.width;
      x += gridSize
    ) {
      this.ctx.moveTo(x, 0);
      this.ctx.lineTo(x, this.canvas.height);
    }

    // 수평선
    for (
      let y = this.offsetY % gridSize;
      y < this.canvas.height;
      y += gridSize
    ) {
      this.ctx.moveTo(0, y);
      this.ctx.lineTo(this.canvas.width, y);
    }

    this.ctx.stroke();
  }

  async handleFileSelect(file) {
    if (!file) return;

    // 파일 검증
    const validExtensions = [".dwg", ".dxf", ".dwf"];
    const fileExtension = "." + file.name.split(".").pop().toLowerCase();

    if (!validExtensions.includes(fileExtension)) {
      this.showError(
        "지원하지 않는 파일 형식입니다. DWG, DXF, DWF 파일만 업로드 가능합니다."
      );
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      // 50MB 제한
      this.showError(
        "파일 크기가 너무 큽니다. 50MB 이하의 파일만 업로드 가능합니다."
      );
      return;
    }

    try {
      // 업로드 시작
      this.showProgress(0, "파일 업로드 중...");

      // FormData 생성
      const formData = new FormData();
      formData.append("file", file);

      // 파일 업로드
      const response = await fetch("/api/cad/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`업로드 실패: ${response.statusText}`);
      }

      const result = await response.json();

      if (result.success) {
        this.showProgress(100, "분석 완료!");
        await this.loadWarehouseData(result.data);
        this.showSuccess(`파일 "${file.name}"이 성공적으로 분석되었습니다.`);
      } else {
        throw new Error(result.error || "파일 처리 중 오류가 발생했습니다.");
      }
    } catch (error) {
      console.error("CAD 파일 업로드 오류:", error);
      this.showError(error.message);
    }
  }

  async loadWarehouseData(data) {
    this.warehouseData = data;

    // 업로드 영역 숨기고 뷰어 표시
    this.elements.uploadArea.style.display = "none";
    this.elements.viewer.style.display = "block";

    // 컨트롤 버튼 활성화
    this.elements.toggleLayersBtn.disabled = false;
    this.elements.zoomFitBtn.disabled = false;

    // Canvas 크기 재조정
    this.setupCanvas();

    // 창고 레이아웃 그리기
    this.drawWarehouse();
  }

  drawWarehouse() {
    if (!this.warehouseData) return;

    // 배경 지우기
    this.drawBackground();

    // 변환 매트릭스 적용
    this.ctx.save();
    this.ctx.translate(this.offsetX, this.offsetY);
    this.ctx.scale(this.scale, this.scale);

    // 그리드 그리기 (옵션) - 데이터 기반 그리드
    if (this.showGrid && this.warehouseData.outline) {
      this.drawDataBasedGrid();
    }

    // 창고 외곽선 그리기
    if (this.warehouseData.outline) {
      this.drawWarehouseOutline(this.warehouseData.outline);
    }

    // 통로 그리기 (랙보다 먼저)
    if (this.warehouseData.aisles) {
      this.warehouseData.aisles.forEach((aisle) => {
        this.drawAisle(aisle);
      });
    }

    // 랙 그리기
    if (this.warehouseData.racks) {
      this.warehouseData.racks.forEach((rack) => {
        this.drawRack(rack);
      });
    }

    // 출입구 그리기
    if (this.warehouseData.gates) {
      this.warehouseData.gates.forEach((gate) => {
        this.drawGate(gate);
      });
    }

    // 레이블 그리기
    this.drawLabels();

    // 선택된 랙 하이라이트
    if (this.selectedRack) {
      this.highlightRack(this.selectedRack);
    }

    // 재고 오버레이 (옵션)
    if (this.showStockOverlay) {
      this.drawStockOverlay();
    }

    this.ctx.restore();

    // 정보 패널 업데이트
    this.updateInfoPanel();
  }

  drawDataBasedGrid() {
    // 창고 데이터 기반 그리드 그리기
    if (!this.warehouseData || !this.warehouseData.outline) {
      return;
    }

    const gridSize = 50;
    this.ctx.strokeStyle = "#f0f0f0";
    this.ctx.lineWidth = 0.5;

    const bounds = this.warehouseData.outline;
    for (let x = bounds.x; x <= bounds.x + bounds.width; x += gridSize) {
      this.ctx.beginPath();
      this.ctx.moveTo(x, bounds.y);
      this.ctx.lineTo(x, bounds.y + bounds.height);
      this.ctx.stroke();
    }

    for (let y = bounds.y; y <= bounds.y + bounds.height; y += gridSize) {
      this.ctx.beginPath();
      this.ctx.moveTo(bounds.x, y);
      this.ctx.lineTo(bounds.x + bounds.width, y);
      this.ctx.stroke();
    }
  }

  drawLabels() {
    if (!this.warehouseData || !this.warehouseData.racks) return;

    this.ctx.font = "12px Arial";
    this.ctx.textAlign = "center";
    this.ctx.textBaseline = "middle";

    this.warehouseData.racks.forEach((rack) => {
      // 랙 ID 라벨
      this.ctx.fillStyle = "#333";
      this.ctx.fillText(
        rack.id,
        rack.x + rack.width / 2,
        rack.y + rack.height / 2
      );

      // 재고율 표시
      if (rack.currentStock !== null && rack.capacity) {
        const stockRatio = Math.round(
          (rack.currentStock / rack.capacity) * 100
        );
        this.ctx.fillStyle = "#666";
        this.ctx.font = "10px Arial";
        this.ctx.fillText(
          `${stockRatio}%`,
          rack.x + rack.width / 2,
          rack.y + rack.height / 2 + 15
        );
      }
    });
  }

  drawStockOverlay() {
    if (!this.warehouseData || !this.warehouseData.racks) return;

    this.warehouseData.racks.forEach((rack) => {
      if (rack.currentStock !== null && rack.capacity) {
        const stockRatio = rack.currentStock / rack.capacity;

        // 색상 계산 (초록 → 노랑 → 빨강)
        let color;
        if (stockRatio < 0.5) {
          color = `rgb(${Math.round(255 * stockRatio * 2)}, 255, 0)`;
        } else {
          color = `rgb(255, ${Math.round(255 * (1 - stockRatio) * 2)}, 0)`;
        }

        // 반투명 오버레이
        this.ctx.fillStyle = color;
        this.ctx.globalAlpha = 0.3;
        this.ctx.fillRect(rack.x, rack.y, rack.width, rack.height);
        this.ctx.globalAlpha = 1.0;
      }
    });
  }

  drawWarehouseOutline(outline) {
    this.ctx.strokeStyle = "#374151";
    this.ctx.lineWidth = 3;
    this.ctx.setLineDash([]);

    this.ctx.beginPath();
    this.ctx.rect(outline.x, outline.y, outline.width, outline.height);
    this.ctx.stroke();
  }

  drawRack(rack) {
    const isSelected = this.selectedRack && this.selectedRack.id === rack.id;

    // 랙 박스 그리기
    this.ctx.fillStyle = isSelected
      ? "rgba(59, 130, 246, 0.3)"
      : "rgba(16, 185, 129, 0.2)";
    this.ctx.strokeStyle = isSelected ? "#3b82f6" : "#10b981";
    this.ctx.lineWidth = isSelected ? 3 : 2;
    this.ctx.setLineDash([]);

    this.ctx.beginPath();
    this.ctx.rect(rack.x, rack.y, rack.width, rack.height);
    this.ctx.fill();
    this.ctx.stroke();

    // 랙 ID 텍스트
    this.ctx.fillStyle = "#374151";
    this.ctx.font = "14px sans-serif";
    this.ctx.textAlign = "center";
    this.ctx.textBaseline = "middle";

    const centerX = rack.x + rack.width / 2;
    const centerY = rack.y + rack.height / 2;
    this.ctx.fillText(rack.id, centerX, centerY);

    // 재고 정보 표시 (있는 경우)
    if (rack.currentStock !== undefined) {
      this.ctx.font = "10px sans-serif";
      this.ctx.fillText(
        `${rack.currentStock}/${rack.capacity}`,
        centerX,
        centerY + 15
      );
    }
  }

  drawAisle(aisle) {
    this.ctx.strokeStyle = "#e5e7eb";
    this.ctx.lineWidth = aisle.width;
    this.ctx.setLineDash([5, 5]);

    this.ctx.beginPath();
    this.ctx.moveTo(aisle.startX, aisle.startY);
    this.ctx.lineTo(aisle.endX, aisle.endY);
    this.ctx.stroke();
  }

  drawGate(gate) {
    this.ctx.fillStyle = "rgba(239, 68, 68, 0.3)";
    this.ctx.strokeStyle = "#ef4444";
    this.ctx.lineWidth = 2;
    this.ctx.setLineDash([]);

    this.ctx.beginPath();
    this.ctx.rect(gate.x, gate.y, gate.width, gate.height);
    this.ctx.fill();
    this.ctx.stroke();

    // 출입구 표시
    this.ctx.fillStyle = "#dc2626";
    this.ctx.font = "12px sans-serif";
    this.ctx.textAlign = "center";
    this.ctx.textBaseline = "middle";
    this.ctx.fillText(
      "출입구",
      gate.x + gate.width / 2,
      gate.y + gate.height / 2
    );
  }

  // 마우스 이벤트 처리
  handleMouseDown(e) {
    this.isDragging = true;
    this.lastMouseX = e.clientX;
    this.lastMouseY = e.clientY;
    this.canvas.style.cursor = "grabbing";
  }

  handleMouseMove(e) {
    if (this.isDragging) {
      const deltaX = e.clientX - this.lastMouseX;
      const deltaY = e.clientY - this.lastMouseY;

      this.offsetX += deltaX;
      this.offsetY += deltaY;

      this.lastMouseX = e.clientX;
      this.lastMouseY = e.clientY;

      this.drawWarehouse();
    }
  }

  handleMouseUp(e) {
    this.isDragging = false;
    this.canvas.style.cursor = "grab";
  }

  handleWheel(e) {
    e.preventDefault();

    const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
    const rect = this.canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // 마우스 위치를 중심으로 줌
    this.offsetX = mouseX - (mouseX - this.offsetX) * zoomFactor;
    this.offsetY = mouseY - (mouseY - this.offsetY) * zoomFactor;
    this.scale *= zoomFactor;

    // 줌 제한
    this.scale = Math.max(0.1, Math.min(5, this.scale));

    this.drawWarehouse();
  }

  handleCanvasClick(e) {
    if (!this.warehouseData || !this.warehouseData.racks) return;

    const rect = this.canvas.getBoundingClientRect();
    const mouseX = (e.clientX - rect.left - this.offsetX) / this.scale;
    const mouseY = (e.clientY - rect.top - this.offsetY) / this.scale;

    // 클릭된 랙 찾기
    for (const rack of this.warehouseData.racks) {
      if (
        mouseX >= rack.x &&
        mouseX <= rack.x + rack.width &&
        mouseY >= rack.y &&
        mouseY <= rack.y + rack.height
      ) {
        this.selectRack(rack);
        return;
      }
    }

    // 빈 공간 클릭 시 선택 해제
    this.selectRack(null);
  }

  selectRack(rack) {
    this.selectedRack = rack;
    this.drawWarehouse();
    this.updateInfoPanel(rack);
  }

  updateInfoPanel(rack) {
    if (!rack) {
      this.elements.infoPanel.innerHTML =
        "<p>랙을 클릭하면 상세 정보가 표시됩니다.</p>";
      return;
    }

    // 재고율 계산
    const stockRatio =
      rack.capacity && rack.currentStock !== undefined
        ? Math.round((rack.currentStock / rack.capacity) * 100)
        : 0;

    // 상태 색상 결정
    let statusColor = "#10b981"; // 초록
    let statusText = "정상";
    if (stockRatio > 80) {
      statusColor = "#f59e0b";
      statusText = "주의";
    }
    if (stockRatio > 95) {
      statusColor = "#ef4444";
      statusText = "위험";
    }
    if (stockRatio < 10) {
      statusColor = "#6b7280";
      statusText = "부족";
    }

    const html = `
      <div class="rack-details">
        <h6><strong>랙 ${rack.id}</strong></h6>
        <p><strong>위치:</strong> (${rack.x.toFixed(1)}, ${rack.y.toFixed(
      1
    )})</p>
        <p><strong>크기:</strong> ${rack.width.toFixed(
          1
        )} × ${rack.height.toFixed(1)}</p>
        ${
          rack.capacity
            ? `<p><strong>용량:</strong> ${rack.capacity}개</p>`
            : ""
        }
        ${
          rack.currentStock !== undefined
            ? `<p><strong>현재고:</strong> ${rack.currentStock}개</p>`
            : ""
        }
        ${
          rack.capacity && rack.currentStock !== undefined
            ? `
          <p><strong>재고율:</strong> <span style="color: ${statusColor}">${stockRatio}% (${statusText})</span></p>
          <div class="stock-progress">
            <div class="progress-bar">
              <div class="progress-fill" style="width: ${stockRatio}%; background-color: ${statusColor}"></div>
            </div>
          </div>
        `
            : ""
        }
        <div class="rack-actions" style="margin-top: 10px;">
          <button onclick="cadViewer.refreshRackData('${
            rack.id
          }')" class="btn btn-sm" style="font-size: 12px;">
            <i class="fas fa-sync"></i> 새로고침
          </button>
          <button onclick="cadViewer.showRackHistory('${
            rack.id
          }')" class="btn btn-sm" style="font-size: 12px;">
            <i class="fas fa-chart-line"></i> 이력
          </button>
        </div>
      </div>
    `;

    this.elements.infoPanel.innerHTML = html;
  }

  async refreshRackData(rackId) {
    try {
      console.log(`랙 ${rackId} 데이터 새로고침 중...`);

      // 실시간 재고 데이터 요청 (현재는 모의 데이터)
      const response = await fetch(`/api/warehouse/racks/${rackId}/stock`);
      if (response.ok) {
        const stockData = await response.json();

        // 랙 데이터 업데이트
        const rack = this.warehouseData.racks.find((r) => r.id === rackId);
        if (rack) {
          rack.currentStock = stockData.currentStock;
          rack.capacity = stockData.capacity || rack.capacity;
          rack.lastUpdate = new Date().toISOString();

          // 화면 다시 그리기
          this.drawWarehouse();

          console.log(`랙 ${rackId} 데이터 업데이트 완료`);
        }
      } else {
        // 실제 API가 없는 경우 모의 데이터로 시뮬레이션
        const rack = this.warehouseData.racks.find((r) => r.id === rackId);
        if (rack) {
          rack.currentStock = Math.floor(
            Math.random() * (rack.capacity || 100)
          );
          rack.lastUpdate = new Date().toISOString();
          this.drawWarehouse();

          console.log(`랙 ${rackId} 모의 데이터로 업데이트`);
        }
      }
    } catch (error) {
      console.error("재고 데이터 업데이트 실패:", error);

      // 오류 시 모의 데이터로 대체
      const rack = this.warehouseData.racks.find((r) => r.id === rackId);
      if (rack) {
        rack.currentStock = Math.floor(Math.random() * (rack.capacity || 100));
        this.drawWarehouse();
      }
    }
  }

  showRackHistory(rackId) {
    // 랙 이력 조회 기능 (모달 등으로 구현 예정)
    console.log(`랙 ${rackId} 이력 조회 - 향후 구현 예정`);
    alert(`랙 ${rackId}의 이력 조회 기능은 향후 구현될 예정입니다.`);
  }

  async syncWithRealData() {
    try {
      console.log("실시간 데이터 동기화 중...");

      // ChromaDB에서 실시간 데이터 가져오기
      const response = await fetch("/api/warehouse/data/current");
      if (response.ok) {
        const warehouseData = await response.json();

        // 랙별 재고 데이터 매핑
        if (warehouseData.inventory && this.warehouseData.racks) {
          this.warehouseData.racks.forEach((rack) => {
            const stockInfo = warehouseData.inventory.find(
              (item) => item.location && item.location.includes(rack.id)
            );

            if (stockInfo) {
              rack.currentStock = stockInfo.quantity;
              rack.lastUpdate = new Date().toISOString();
            }
          });

          // 화면 업데이트
          this.drawWarehouse();
          console.log("실시간 데이터 동기화 완료");
        }
      } else {
        console.log("실시간 데이터 API 미구현 - 모의 데이터 사용");
      }
    } catch (error) {
      console.error("실시간 데이터 동기화 실패:", error);
    }
  }

  zoomToFit() {
    if (!this.warehouseData || !this.warehouseData.outline) return;

    const outline = this.warehouseData.outline;
    const padding = 50;

    const scaleX = (this.canvas.width - padding * 2) / outline.width;
    const scaleY = (this.canvas.height - padding * 2) / outline.height;

    this.scale = Math.min(scaleX, scaleY);
    this.offsetX =
      (this.canvas.width - outline.width * this.scale) / 2 -
      outline.x * this.scale;
    this.offsetY =
      (this.canvas.height - outline.height * this.scale) / 2 -
      outline.y * this.scale;

    this.drawWarehouse();
  }

  toggleLayers() {
    // 레이어 토글 기능 (향후 구현)
    console.log("레이어 토글 기능은 향후 구현 예정입니다.");
  }

  showProgress(percent, message) {
    this.elements.uploadArea.style.display = "none";
    this.elements.progress.style.display = "block";
    this.elements.progressFill.style.width = `${percent}%`;
    this.elements.progressText.textContent = message;
  }

  showError(message) {
    this.elements.progress.style.display = "none";
    this.elements.result.style.display = "block";
    this.elements.result.className = "upload-result error";
    this.elements.result.innerHTML = `
      <div class="error-message">
        <i class="fas fa-exclamation-triangle"></i>
        <strong>오류:</strong> ${message}
      </div>
      <button onclick="cadViewer.resetUpload()" class="btn btn-primary" style="margin-top: 1rem;">
        <i class="fas fa-redo"></i> 다시 시도
      </button>
    `;
  }

  showSuccess(message) {
    this.elements.progress.style.display = "none";
    this.elements.result.style.display = "block";
    this.elements.result.className = "upload-result success";
    this.elements.result.innerHTML = `
      <div class="success-message">
        <i class="fas fa-check-circle"></i>
        <strong>성공:</strong> ${message}
      </div>
    `;

    // 3초 후 결과 메시지 숨김
    setTimeout(() => {
      this.elements.result.style.display = "none";
    }, 3000);
  }

  resetUpload() {
    this.elements.uploadArea.style.display = "block";
    this.elements.viewer.style.display = "none";
    this.elements.progress.style.display = "none";
    this.elements.result.style.display = "none";
    this.elements.fileInput.value = "";

    // 컨트롤 버튼 비활성화
    this.elements.toggleLayersBtn.disabled = true;
    this.elements.zoomFitBtn.disabled = true;

    // 데이터 초기화
    this.warehouseData = null;
    this.selectedRack = null;
  }
}

// 전역 CAD 뷰어 인스턴스
let cadViewer;

// DOM 로드 완료 시 초기화
document.addEventListener("DOMContentLoaded", () => {
  cadViewer = new CADViewer();
});
