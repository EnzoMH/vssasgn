// API 기본 URL
const API_BASE_URL = "";

// API 호출 유틸리티 함수
class APIClient {
  static async get(endpoint) {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error("API GET 요청 실패:", error);
      throw error;
    }
  }

  static async post(endpoint, data, options = {}) {
    try {
      // 기본 fetch 옵션 설정
      const fetchOptions = {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(data),
        ...options, // AbortController signal, timeout 등 추가 옵션 지원
      };

      const response = await fetch(`${API_BASE_URL}${endpoint}`, fetchOptions);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error("API POST 요청 실패:", error);
      throw error;
    }
  }

  static async uploadFile(endpoint, file) {
    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error("파일 업로드 실패:", error);
      throw error;
    }
  }
}

// 로딩 상태 관리
class LoadingManager {
  static show(message = "데이터를 불러오는 중...") {
    const overlay = document.getElementById("loadingOverlay");
    const text = overlay.querySelector("p");
    text.textContent = message;
    overlay.style.display = "flex";
  }

  static hide() {
    const overlay = document.getElementById("loadingOverlay");
    overlay.style.display = "none";
  }
}

// 알림 메시지 표시
class NotificationManager {
  static show(message, type = "info", duration = 3000) {
    // 기존 알림 제거
    const existingNotification = document.querySelector(".notification");
    if (existingNotification) {
      existingNotification.remove();
    }

    // 새 알림 생성
    const notification = document.createElement("div");
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
            <div class="notification-content">
                <span>${message}</span>
                <button class="notification-close">&times;</button>
            </div>
        `;

    // 스타일 적용
    notification.style.cssText = `
            position: fixed;
            top: 2rem;
            right: 2rem;
            background: ${
              type === "success"
                ? "var(--secondary)"
                : type === "error"
                ? "var(--danger)"
                : "var(--primary)"
            };
            color: white;
            padding: 1rem 1.5rem;
            border-radius: var(--border-radius);
            box-shadow: var(--shadow-lg);
            z-index: 4000;
            display: flex;
            align-items: center;
            gap: 1rem;
            max-width: 400px;
            animation: slideIn 0.3s ease;
        `;

    document.body.appendChild(notification);

    // 닫기 버튼 이벤트
    const closeBtn = notification.querySelector(".notification-close");
    closeBtn.addEventListener("click", () => {
      notification.remove();
    });

    // 자동 제거
    if (duration > 0) {
      setTimeout(() => {
        if (notification.parentNode) {
          notification.remove();
        }
      }, duration);
    }
  }

  static success(message, duration = 3000) {
    this.show(message, "success", duration);
  }

  static error(message, duration = 5000) {
    this.show(message, "error", duration);
  }

  static info(message, duration = 3000) {
    this.show(message, "info", duration);
  }
}

// 숫자 포맷팅 유틸리티
class NumberUtils {
  static formatNumber(num) {
    if (typeof num !== "number") return "--";
    return num.toLocaleString("ko-KR");
  }

  static formatPercentage(num) {
    if (typeof num !== "number") return "--%";
    // 백엔드에서 이미 백분율로 보내주는 경우 (77.7) 처리
    if (num > 10) {
      return `${num.toFixed(1)}%`;
    }
    // 소수로 보내주는 경우 (0.777) 처리
    return `${(num * 100).toFixed(1)}%`;
  }

  static formatDecimal(num, decimals = 1) {
    if (typeof num !== "number") return "--";
    return num.toFixed(decimals);
  }
}

// 날짜 포맷팅 유틸리티
class DateUtils {
  static formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString("ko-KR");
  }

  static formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString("ko-KR");
  }

  static getCurrentTime() {
    return new Date().toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }
}

// DOM 유틸리티
class DOMUtils {
  static $(selector) {
    return document.querySelector(selector);
  }

  static $$(selector) {
    return document.querySelectorAll(selector);
  }

  static createElement(tag, className, innerHTML) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (innerHTML) element.innerHTML = innerHTML;
    return element;
  }

  static addEventListeners(selectors, event, handler) {
    selectors.forEach((selector) => {
      const elements =
        typeof selector === "string" ? this.$$(selector) : [selector];
      elements.forEach((element) => {
        if (element) element.addEventListener(event, handler);
      });
    });
  }
}

// 데이터 검증 유틸리티
class ValidationUtils {
  static isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  static isValidFile(file, allowedTypes = [".csv", ".xlsx", ".xls"]) {
    if (!file) return false;
    const fileExtension = "." + file.name.split(".").pop().toLowerCase();
    return allowedTypes.includes(fileExtension);
  }

  static isValidFileSize(file, maxSizeMB = 10) {
    if (!file) return false;
    const maxSizeBytes = maxSizeMB * 1024 * 1024;
    return file.size <= maxSizeBytes;
  }
}

// CSS 애니메이션 추가
const style = document.createElement("style");
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    .notification-content {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        width: 100%;
    }

    .notification-close {
        background: none;
        border: none;
        color: white;
        cursor: pointer;
        font-size: 1.5rem;
        padding: 0;
        line-height: 1;
    }

    .notification-close:hover {
        opacity: 0.8;
    }
`;
document.head.appendChild(style);
