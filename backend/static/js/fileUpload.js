// 파일 업로드 관리 클래스
class FileUploadManager {
  constructor() {
    this.initializeElements();
    this.bindEvents();
  }

  initializeElements() {
    this.uploadBtn = document.getElementById("uploadBtn");
    this.uploadModal = document.getElementById("uploadModal");
    this.closeUploadModal = document.getElementById("closeUploadModal");
    this.uploadArea = document.getElementById("uploadArea");
    this.fileInput = document.getElementById("fileInput");
    this.selectFileBtn = document.getElementById("selectFileBtn");
    this.uploadProgress = document.getElementById("uploadProgress");
    this.progressFill = document.getElementById("progressFill");
    this.progressText = document.getElementById("progressText");
    this.uploadResult = document.getElementById("uploadResult");
  }

  bindEvents() {
    // 업로드 버튼 클릭
    this.uploadBtn.addEventListener("click", () => {
      this.openModal();
    });

    // 모달 닫기
    this.closeUploadModal.addEventListener("click", () => {
      this.closeModal();
    });

    // 모달 배경 클릭 시 닫기
    this.uploadModal.addEventListener("click", (e) => {
      if (e.target === this.uploadModal) {
        this.closeModal();
      }
    });

    // 파일 선택 버튼
    this.selectFileBtn.addEventListener("click", () => {
      this.fileInput.click();
    });

    // 파일 입력 변경
    this.fileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        this.handleFile(e.target.files[0]);
      }
    });

    // 드래그 앤 드롭 이벤트
    this.setupDragAndDrop();

    // ESC 키로 모달 닫기
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.uploadModal.style.display === "flex") {
        this.closeModal();
      }
    });
  }

  setupDragAndDrop() {
    // 드래그 오버 방지 (전체 페이지)
    ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
      document.addEventListener(eventName, this.preventDefaults, false);
    });

    // 업로드 영역 드래그 이벤트
    ["dragenter", "dragover"].forEach((eventName) => {
      this.uploadArea.addEventListener(
        eventName,
        (e) => {
          this.highlight(e);
        },
        false
      );
    });

    ["dragleave", "drop"].forEach((eventName) => {
      this.uploadArea.addEventListener(
        eventName,
        (e) => {
          this.unhighlight(e);
        },
        false
      );
    });

    // 파일 드롭
    this.uploadArea.addEventListener(
      "drop",
      (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0) {
          this.handleFile(files[0]);
        }
      },
      false
    );
  }

  preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  highlight(e) {
    this.uploadArea.classList.add("dragover");
  }

  unhighlight(e) {
    this.uploadArea.classList.remove("dragover");
  }

  openModal() {
    this.uploadModal.style.display = "flex";
    this.resetModal();
  }

  closeModal() {
    this.uploadModal.style.display = "none";
    this.resetModal();
  }

  resetModal() {
    this.uploadProgress.style.display = "none";
    this.uploadResult.style.display = "none";
    this.progressFill.style.width = "0%";
    this.progressText.textContent = "업로드 중...";
    this.fileInput.value = "";
    this.uploadArea.classList.remove("dragover");
  }

  async handleFile(file) {
    // 파일 유효성 검사
    if (!this.validateFile(file)) {
      return;
    }

    // 업로드 진행 표시
    this.showProgress();

    try {
      // 파일 업로드 API 호출
      const response = await this.uploadFile(file);
      this.showResult(response, true);

      // 성공 알림
      NotificationManager.success("파일이 성공적으로 업로드되었습니다.");

      // 대시보드 데이터 새로고침
      if (window.dashboardManager) {
        await window.dashboardManager.refreshData();
      }
    } catch (error) {
      console.error("파일 업로드 오류:", error);
      this.showResult(
        {
          message: error.message || "파일 업로드 중 오류가 발생했습니다.",
        },
        false
      );

      // 오류 알림
      NotificationManager.error("파일 업로드에 실패했습니다.");
    }
  }

  validateFile(file) {
    // 파일 형식 검사
    if (!ValidationUtils.isValidFile(file)) {
      NotificationManager.error(
        "지원하지 않는 파일 형식입니다. CSV 또는 Excel 파일을 업로드해주세요."
      );
      return false;
    }

    // 파일 크기 검사 (10MB)
    if (!ValidationUtils.isValidFileSize(file, 10)) {
      NotificationManager.error(
        "파일 크기가 너무 큽니다. 10MB 이하의 파일을 업로드해주세요."
      );
      return false;
    }

    return true;
  }

  showProgress() {
    this.uploadProgress.style.display = "block";
    this.uploadResult.style.display = "none";

    // 프로그레스 바 애니메이션
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 15;
      if (progress > 90) {
        progress = 90;
        clearInterval(interval);
      }
      this.progressFill.style.width = `${progress}%`;
    }, 200);

    // 서버 응답 후 완료
    this.progressInterval = interval;
  }

  async uploadFile(file) {
    try {
      const response = await APIClient.uploadFile("/api/upload/data", file);

      // 프로그레스 완료
      if (this.progressInterval) {
        clearInterval(this.progressInterval);
      }
      this.progressFill.style.width = "100%";
      this.progressText.textContent = "업로드 완료!";

      return response;
    } catch (error) {
      if (this.progressInterval) {
        clearInterval(this.progressInterval);
      }
      throw error;
    }
  }

  showResult(response, isSuccess) {
    this.uploadProgress.style.display = "none";
    this.uploadResult.style.display = "block";

    if (isSuccess) {
      this.uploadResult.className = "upload-result success";
      this.uploadResult.innerHTML = `
                <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                    <i class="fas fa-check-circle" style="color: var(--secondary);"></i>
                    <strong>업로드 성공!</strong>
                </div>
                <p>${response.message}</p>
                ${
                  response.rows_processed
                    ? `<p><small>처리된 행 수: ${NumberUtils.formatNumber(
                        response.rows_processed
                      )}개</small></p>`
                    : ""
                }
            `;
    } else {
      this.uploadResult.className = "upload-result error";
      this.uploadResult.innerHTML = `
                <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                    <i class="fas fa-exclamation-triangle" style="color: var(--danger);"></i>
                    <strong>업로드 실패</strong>
                </div>
                <p>${response.message}</p>
            `;
    }

    // 자동 닫기 (성공 시)
    if (isSuccess) {
      setTimeout(() => {
        this.closeModal();
      }, 3000);
    }
  }

  // 지원하는 파일 형식 정보 표시
  showSupportedFormats() {
    const supportedFormats = [
      { ext: "CSV", desc: "쉼표로 구분된 값 파일" },
      { ext: "XLSX", desc: "Excel 워크북 파일" },
      { ext: "XLS", desc: "이전 버전 Excel 파일" },
    ];

    const formatInfo = document.createElement("div");
    formatInfo.className = "supported-formats";
    formatInfo.innerHTML = `
            <h4><i class="fas fa-info-circle"></i> 지원하는 파일 형식</h4>
            <ul>
                ${supportedFormats
                  .map(
                    (format) =>
                      `<li><strong>.${format.ext}</strong> - ${format.desc}</li>`
                  )
                  .join("")}
            </ul>
            <p><small>최대 파일 크기: 10MB</small></p>
        `;

    // 스타일 추가
    const style = document.createElement("style");
    style.textContent = `
            .supported-formats {
                margin-top: 1rem;
                padding: 1rem;
                background-color: var(--gray-100);
                border-radius: var(--border-radius-sm);
                border-left: 4px solid var(--primary);
            }
            .supported-formats h4 {
                margin: 0 0 0.5rem 0;
                color: var(--gray-700);
                font-size: 0.875rem;
            }
            .supported-formats ul {
                margin: 0.5rem 0;
                padding-left: 1.5rem;
            }
            .supported-formats li {
                margin-bottom: 0.25rem;
                font-size: 0.875rem;
                color: var(--gray-600);
            }
            .upload-result.success {
                border-color: var(--secondary);
                background-color: #f0fdf4;
                color: var(--secondary);
            }
            .upload-result.error {
                border-color: var(--danger);
                background-color: #fef2f2;
                color: var(--danger);
            }
        `;
    if (!document.querySelector("#uploadStyles")) {
      style.id = "uploadStyles";
      document.head.appendChild(style);
    }

    return formatInfo;
  }

  // 모달에 파일 형식 정보 추가
  addFormatInfo() {
    const modalBody = this.uploadModal.querySelector(".modal-body");
    const formatInfo = this.showSupportedFormats();
    modalBody.appendChild(formatInfo);
  }
}

// 파일 업로드 매니저 인스턴스 생성
const fileUploadManager = new FileUploadManager();

// 페이지 로드 완료 후 파일 형식 정보 추가
document.addEventListener("DOMContentLoaded", () => {
  fileUploadManager.addFormatInfo();
});
