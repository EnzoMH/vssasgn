// AI 챗봇 관리 클래스
class AIChatManager {
  constructor() {
    this.isOpen = false;
    this.isLoading = false;
    this.currentRequest = null; // 현재 진행 중인 요청
    this.lastMessageTime = 0; // 마지막 메시지 전송 시간
    this.debounceDelay = 1000; // 1초 디바운싱
    this.requestQueue = new Set(); // 중복 요청 방지용 큐
    this.initializeElements();
    this.bindEvents();
  }

  initializeElements() {
    this.chatToggle = document.getElementById("chatToggle");
    this.chatContainer = document.getElementById("chatContainer");
    this.closeChatBtn = document.getElementById("closeChatBtn");
    this.chatMessages = document.getElementById("chatMessages");
    this.chatInput = document.getElementById("chatInput");
    this.sendChatBtn = document.getElementById("sendChatBtn");
  }

  bindEvents() {
    // 채팅 토글
    this.chatToggle.addEventListener("click", () => {
      this.toggleChat();
    });

    // 채팅 닫기
    this.closeChatBtn.addEventListener("click", () => {
      this.closeChat();
    });

    // 메시지 전송 (Enter 키)
    this.chatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });

    // 메시지 전송 (버튼 클릭)
    this.sendChatBtn.addEventListener("click", () => {
      this.sendMessage();
    });

    // 채팅 컨테이너 외부 클릭 시 닫기
    document.addEventListener("click", (e) => {
      if (
        this.isOpen &&
        !this.chatContainer.contains(e.target) &&
        !this.chatToggle.contains(e.target)
      ) {
        this.closeChat();
      }
    });
  }

  toggleChat() {
    if (this.isOpen) {
      this.closeChat();
    } else {
      this.openChat();
    }
  }

  openChat() {
    this.isOpen = true;
    this.chatContainer.style.display = "flex";
    this.chatInput.focus();

    // 애니메이션 효과
    this.chatContainer.style.opacity = "0";
    this.chatContainer.style.transform = "translateY(20px)";

    setTimeout(() => {
      this.chatContainer.style.transition = "all 0.3s ease";
      this.chatContainer.style.opacity = "1";
      this.chatContainer.style.transform = "translateY(0)";
    }, 10);
  }

  closeChat() {
    this.isOpen = false;
    this.chatContainer.style.display = "none";
    this.chatContainer.style.transition = "none";
  }

  async sendMessage() {
    const message = this.chatInput.value.trim();
    const currentTime = Date.now();

    // 🔒 중복 요청 방지 체크
    if (!message || this.isLoading) {
      console.log("⚠️ 요청 차단: 빈 메시지 또는 로딩 중");
      return;
    }

    // 🔒 디바운싱 체크 (1초 내 중복 요청 방지)
    if (currentTime - this.lastMessageTime < this.debounceDelay) {
      console.log("⚠️ 요청 차단: 디바운싱 (1초 대기)");
      this.showTemporaryNotification(
        "너무 빠른 요청입니다. 잠시 후 다시 시도해주세요."
      );
      return;
    }

    // 🔒 중복 메시지 체크
    if (this.requestQueue.has(message)) {
      console.log("⚠️ 요청 차단: 동일한 메시지 처리 중");
      this.showTemporaryNotification("동일한 질문을 처리 중입니다.");
      return;
    }

    // 🔒 기존 요청 취소
    if (this.currentRequest) {
      console.log("🔄 기존 요청 취소 후 새 요청 처리");
      this.currentRequest.abort();
      this.currentRequest = null;
    }

    // 사용자 메시지 추가
    this.addMessage(message, "user");
    this.chatInput.value = "";
    this.lastMessageTime = currentTime;
    this.requestQueue.add(message);

    // 로딩 상태 설정
    this.setLoading(true);

    try {
      // AbortController로 요청 취소 가능하게 설정
      const controller = new AbortController();
      this.currentRequest = controller;

      console.log(`🚀 AI 요청 시작: "${message}"`);

      // AI API 호출 (요청 취소 가능)
      const response = await APIClient.post(
        "/api/ai/chat",
        {
          question: message,
        },
        {
          signal: controller.signal,
          timeout: 30000, // 30초 타임아웃
        }
      );

      // 요청 완료 체크 (취소되지 않았을 때만 응답 처리)
      if (!controller.signal.aborted) {
        console.log(
          `✅ AI 응답 성공: "${response.answer?.substring(0, 50)}..."`
        );
        this.addMessage(response.answer, "bot");

        // 🎯 AI 응답 기반 동적 질문 제안 업데이트
        setTimeout(() => {
          this.addQuickQuestions(response.answer);
        }, 1000);
      }
    } catch (error) {
      // 요청 취소된 경우 무시
      if (error.name === "AbortError") {
        console.log("🔄 요청이 취소되었습니다");
        return;
      }

      console.error("❌ AI 챗봇 오류:", error);

      // 🎯 스마트 에러 처리 (에러 유형별 분기)
      let errorMessage = "";
      let showRetry = true;

      if (
        error.message?.includes("429") ||
        error.message?.includes("rate limit")
      ) {
        errorMessage = "🚫 요청이 너무 많습니다. 잠시 후 다시 시도해주세요.";
        showRetry = true;
      } else if (
        error.message?.includes("timeout") ||
        error.message?.includes("Network Error")
      ) {
        errorMessage =
          "⏱️ 응답 시간이 초과되었습니다. 네트워크를 확인하고 다시 시도해주세요.";
        showRetry = true;
      } else if (error.message?.includes("500")) {
        errorMessage =
          "🔧 서버에 일시적인 문제가 있습니다. 곧 복구될 예정입니다.";
        showRetry = true;
      } else {
        errorMessage =
          "❌ AI 서비스에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.";
        showRetry = true;
      }

      this.addErrorMessage(errorMessage, message, showRetry);
    } finally {
      // 정리 작업
      this.setLoading(false);
      this.currentRequest = null;
      this.requestQueue.delete(message);
      console.log(`🏁 요청 처리 완료: "${message}"`);
    }
  }

  // 📱 임시 알림 표시 메서드 추가
  showTemporaryNotification(message) {
    // 기존 알림이 있으면 제거
    const existingNotification = document.querySelector(".chat-notification");
    if (existingNotification) {
      existingNotification.remove();
    }

    // 새 알림 생성
    const notification = document.createElement("div");
    notification.className = "chat-notification";
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: var(--warning);
      color: white;
      padding: 12px 16px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      z-index: 10000;
      font-size: 14px;
      max-width: 300px;
      transition: all 0.3s ease;
    `;

    document.body.appendChild(notification);

    // 3초 후 자동 제거
    setTimeout(() => {
      if (notification.parentNode) {
        notification.style.opacity = "0";
        notification.style.transform = "translateX(100%)";
        setTimeout(() => notification.remove(), 300);
      }
    }, 3000);
  }

  addMessage(content, type, isError = false) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${type}-message`;

    const messageContent = document.createElement("div");
    messageContent.className = "message-content";

    // 🎨 마크다운 스타일 텍스트 처리 (볼드, 이모지 등)
    if (content.includes("**")) {
      messageContent.innerHTML = content.replace(
        /\*\*(.*?)\*\*/g,
        "<strong>$1</strong>"
      );
    } else {
      messageContent.textContent = content;
    }

    if (isError) {
      messageContent.style.color = "var(--danger)";
    }

    const messageTime = document.createElement("div");
    messageTime.className = "message-time";
    messageTime.textContent = DateUtils.getCurrentTime();

    messageDiv.appendChild(messageContent);
    messageDiv.appendChild(messageTime);

    this.chatMessages.appendChild(messageDiv);
    this.scrollToBottom();
  }

  // 🚨 개선된 에러 메시지 추가 (재시도 버튼 포함)
  addErrorMessage(errorText, originalMessage, showRetry = true) {
    const messageDiv = document.createElement("div");
    messageDiv.className = "message bot-message error-message";

    const messageContent = document.createElement("div");
    messageContent.className = "message-content error-content";

    messageContent.innerHTML = `
      <div class="error-icon">⚠️</div>
      <div class="error-text">${errorText}</div>
      ${
        showRetry
          ? `
        <div class="error-actions">
          <button class="retry-btn" data-message="${originalMessage}">
            <i class="fas fa-redo"></i> 다시 시도
          </button>
          <button class="help-btn">
            <i class="fas fa-question-circle"></i> 도움말
          </button>
        </div>
      `
          : ""
      }
    `;

    const messageTime = document.createElement("div");
    messageTime.className = "message-time";
    messageTime.textContent = DateUtils.getCurrentTime();

    messageDiv.appendChild(messageContent);
    messageDiv.appendChild(messageTime);

    // 🔄 재시도 버튼 이벤트
    if (showRetry) {
      const retryBtn = messageContent.querySelector(".retry-btn");
      const helpBtn = messageContent.querySelector(".help-btn");

      if (retryBtn) {
        retryBtn.addEventListener("click", () => {
          // 에러 메시지 제거 후 재시도
          messageDiv.remove();
          this.chatInput.value = originalMessage;
          this.sendMessage();
        });
      }

      if (helpBtn) {
        helpBtn.addEventListener("click", () => {
          this.showHelpDialog();
        });
      }
    }

    this.chatMessages.appendChild(messageDiv);
    this.scrollToBottom();
  }

  setLoading(loading) {
    this.isLoading = loading;

    if (loading) {
      // 🎯 개선된 로딩 메시지 (단계별 진행 표시)
      const loadingDiv = document.createElement("div");
      loadingDiv.className = "message bot-message loading-message";
      loadingDiv.innerHTML = `
                <div class="message-content">
                    <div class="loading-container">
                        <div class="loading-spinner">
                            <i class="fas fa-brain fa-pulse"></i>
                        </div>
                        <div class="loading-text">
                            <div class="loading-stage">AI가 분석 중입니다</div>
                            <div class="loading-dots">
                                <span class="dot"></span>
                                <span class="dot"></span>
                                <span class="dot"></span>
                            </div>
                        </div>
                        <div class="loading-progress">
                            <div class="progress-bar">
                                <div class="progress-fill"></div>
                            </div>
                            <div class="progress-text">분석 진행중...</div>
                        </div>
                    </div>
                </div>
            `;

      this.chatMessages.appendChild(loadingDiv);
      this.scrollToBottom();

      // 🎨 로딩 애니메이션 시작
      this.startLoadingAnimation();

      // 입력 비활성화
      this.chatInput.disabled = true;
      this.sendChatBtn.disabled = true;
      this.sendChatBtn.innerHTML =
        '<i class="fas fa-hourglass-half fa-spin"></i>';
    } else {
      // 로딩 메시지 제거
      const loadingMessage =
        this.chatMessages.querySelector(".loading-message");
      if (loadingMessage) {
        loadingMessage.remove();
      }

      // 입력 활성화
      this.chatInput.disabled = false;
      this.sendChatBtn.disabled = false;
      this.sendChatBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
      this.chatInput.focus();
    }
  }

  // 🎨 로딩 애니메이션 제어
  startLoadingAnimation() {
    const loadingMessage = this.chatMessages.querySelector(".loading-message");
    if (!loadingMessage) return;

    let stage = 0;
    const stages = [
      "질문을 분석하고 있습니다",
      "관련 데이터를 검색 중입니다",
      "AI가 답변을 생성 중입니다",
      "응답을 정리하고 있습니다",
    ];

    const progressSteps = [20, 45, 75, 90];

    const updateStage = () => {
      const stageElement = loadingMessage.querySelector(".loading-stage");
      const progressFill = loadingMessage.querySelector(".progress-fill");
      const progressText = loadingMessage.querySelector(".progress-text");

      if (stageElement && stage < stages.length) {
        stageElement.textContent = stages[stage];
        progressFill.style.width = `${progressSteps[stage]}%`;
        progressText.textContent = `${progressSteps[stage]}%`;
        stage++;
      }
    };

    // 로딩 단계 업데이트 (2초마다)
    const stageInterval = setInterval(() => {
      if (!this.isLoading || !loadingMessage.parentNode) {
        clearInterval(stageInterval);
        return;
      }
      updateStage();
    }, 2000);

    // 초기 단계 설정
    updateStage();
  }

  scrollToBottom() {
    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
  }

  // 🎯 도움말 다이얼로그 표시
  showHelpDialog() {
    const helpDialog = document.createElement("div");
    helpDialog.className = "help-dialog-overlay";
    helpDialog.innerHTML = `
      <div class="help-dialog">
        <div class="help-header">
          <h3><i class="fas fa-question-circle"></i> AI 챗봇 사용 가이드</h3>
          <button class="help-close">&times;</button>
        </div>
        <div class="help-content">
          <div class="help-section">
            <h4>💡 질문 예시</h4>
            <ul>
              <li><strong>재고 정보:</strong> "총 재고량은?", "A랙 상태는?"</li>
              <li><strong>트렌드 분석:</strong> "입고량이 가장 높았던 날은?", "출고 트렌드는?"</li>
              <li><strong>상태 분석:</strong> "재고가 부족한 제품은?", "위험한 상품은?"</li>
              <li><strong>랙 정보:</strong> "C랙의 현재 상태는?", "전체 랙 현황은?"</li>
            </ul>
          </div>
          <div class="help-section">
            <h4>🚫 문제 해결</h4>
            <ul>
              <li><strong>응답이 느림:</strong> 네트워크 상태를 확인해주세요</li>
              <li><strong>요청 제한:</strong> 잠시 후 다시 시도해주세요</li>
              <li><strong>오류 발생:</strong> 새로고침 후 재시도해주세요</li>
            </ul>
          </div>
          <div class="help-section">
            <h4>⚡ 팁</h4>
            <ul>
              <li>구체적인 질문일수록 정확한 답변을 받을 수 있어요</li>
              <li>한 번에 하나의 질문을 하시면 더 빠른 응답이 가능해요</li>
              <li>아래 빠른 질문 버튼을 활용해보세요</li>
            </ul>
          </div>
        </div>
      </div>
    `;

    // 도움말 닫기 이벤트
    helpDialog.addEventListener("click", (e) => {
      if (
        e.target.classList.contains("help-dialog-overlay") ||
        e.target.classList.contains("help-close")
      ) {
        helpDialog.remove();
      }
    });

    document.body.appendChild(helpDialog);
  }

  // 🧠 동적 질문 제안 (AI 응답 기반)
  generateContextualQuestions(lastResponse = "") {
    const baseQuestions = [
      "오늘 총 재고량은 얼마인가요?",
      "A랙의 현재 상태는 어떤가요?",
      "재고가 부족한 제품을 알려주세요",
    ];

    const contextualQuestions = [];

    // 응답 내용에 따른 동적 질문 생성
    if (lastResponse.includes("랙") || lastResponse.includes("Rack")) {
      contextualQuestions.push(
        "다른 랙의 상태도 확인해주세요",
        "전체 랙 활용률은 어떤가요?"
      );
    }

    if (lastResponse.includes("재고") || lastResponse.includes("inventory")) {
      contextualQuestions.push(
        "재고 회전율은 어떤가요?",
        "입출고 트렌드를 분석해주세요"
      );
    }

    if (lastResponse.includes("부족") || lastResponse.includes("low")) {
      contextualQuestions.push(
        "발주가 필요한 제품은?",
        "안전 재고 수준은 어떤가요?"
      );
    }

    if (lastResponse.includes("날짜") || lastResponse.includes("date")) {
      contextualQuestions.push(
        "최근 일주일 트렌드는?",
        "이번 달 실적은 어떤가요?"
      );
    }

    // 기본 질문과 동적 질문 결합 (최대 5개)
    const allQuestions = [...baseQuestions, ...contextualQuestions];
    return allQuestions.slice(0, 5);
  }

  // 🎯 개선된 빠른 질문 생성
  addQuickQuestions(lastResponse = "") {
    // 기존 빠른 질문 제거
    const existingQuestions =
      this.chatMessages.querySelector(".quick-questions");
    if (existingQuestions) {
      existingQuestions.remove();
    }

    const quickQuestions = this.generateContextualQuestions(lastResponse);

    const quickQuestionsDiv = document.createElement("div");
    quickQuestionsDiv.className = "quick-questions";
    quickQuestionsDiv.innerHTML = `
            <div class="quick-questions-title">💡 빠른 질문</div>
            ${quickQuestions
              .map(
                (question) => `
                <button class="quick-question-btn" data-question="${question}">
                    ${question}
                </button>
            `
              )
              .join("")}
        `;

    // 스타일 추가
    const style = document.createElement("style");
    style.textContent = `
            .quick-questions {
                padding: 1rem;
                border-top: 1px solid var(--gray-200);
                background-color: var(--gray-100);
            }
            .quick-questions-title {
                font-size: 0.875rem;
                font-weight: 600;
                margin-bottom: 0.5rem;
                color: var(--gray-700);
            }
            .quick-question-btn {
                display: block;
                width: 100%;
                text-align: left;
                padding: 0.5rem;
                margin-bottom: 0.25rem;
                background: white;
                border: 1px solid var(--gray-300);
                border-radius: var(--border-radius-sm);
                font-size: 0.75rem;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .quick-question-btn:hover {
                background-color: var(--primary);
                color: white;
                border-color: var(--primary);
            }
        `;
    if (!document.querySelector("#quickQuestionsStyles")) {
      style.id = "quickQuestionsStyles";
      document.head.appendChild(style);
    }

    // 빠른 질문 클릭 이벤트
    quickQuestionsDiv.addEventListener("click", (e) => {
      if (e.target.classList.contains("quick-question-btn")) {
        const question = e.target.dataset.question;
        this.chatInput.value = question;
        this.sendMessage();
      }
    });

    return quickQuestionsDiv;
  }

  // 초기 환영 메시지와 빠른 질문 추가
  initializeChat() {
    // 기존 메시지 제거 (환영 메시지 제외)
    const messages = this.chatMessages.querySelectorAll(
      ".message:not(.bot-message)"
    );
    messages.forEach((msg) => msg.remove());

    // 빠른 질문 추가
    const quickQuestions = this.addQuickQuestions();
    this.chatMessages.appendChild(quickQuestions);

    this.scrollToBottom();
  }

  // 채팅 기록 초기화
  clearChat() {
    // 모든 메시지 제거 (환영 메시지 제외)
    const messages = this.chatMessages.querySelectorAll(
      ".message:not(:first-child)"
    );
    messages.forEach((msg) => msg.remove());

    // 빠른 질문들도 제거
    const quickQuestions = this.chatMessages.querySelector(".quick-questions");
    if (quickQuestions) {
      quickQuestions.remove();
    }
  }
}

// AI 챗봇 매니저 인스턴스 생성
const aiChatManager = new AIChatManager();

// 페이지 로드 완료 후 초기화
document.addEventListener("DOMContentLoaded", () => {
  aiChatManager.initializeChat();
});
