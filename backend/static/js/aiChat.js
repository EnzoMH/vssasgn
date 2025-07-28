// AI 챗봇 관리 클래스
class AIChatManager {
  constructor() {
    this.isOpen = false;
    this.isLoading = false;
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
    if (!message || this.isLoading) return;

    // 사용자 메시지 추가
    this.addMessage(message, "user");
    this.chatInput.value = "";

    // 로딩 상태 설정
    this.setLoading(true);

    try {
      // AI API 호출
      const response = await APIClient.post("/api/ai/chat", {
        question: message,
      });

      // AI 응답 추가
      this.addMessage(response.answer, "bot");
    } catch (error) {
      console.error("AI 챗봇 오류:", error);
      this.addMessage(
        "죄송합니다. 현재 AI 서비스에 문제가 있습니다. 잠시 후 다시 시도해주세요.",
        "bot",
        true
      );
    } finally {
      this.setLoading(false);
    }
  }

  addMessage(content, type, isError = false) {
    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${type}-message`;

    const messageContent = document.createElement("div");
    messageContent.className = "message-content";
    messageContent.textContent = content;

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

  setLoading(loading) {
    this.isLoading = loading;

    if (loading) {
      // 로딩 메시지 추가
      const loadingDiv = document.createElement("div");
      loadingDiv.className = "message bot-message loading-message";
      loadingDiv.innerHTML = `
                <div class="message-content">
                    <i class="fas fa-spinner fa-spin"></i> AI가 생각하고 있습니다...
                </div>
            `;
      this.chatMessages.appendChild(loadingDiv);
      this.scrollToBottom();

      // 입력 비활성화
      this.chatInput.disabled = true;
      this.sendChatBtn.disabled = true;
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
      this.chatInput.focus();
    }
  }

  scrollToBottom() {
    this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
  }

  // 미리 정의된 질문 제안
  addQuickQuestions() {
    const quickQuestions = [
      "오늘 총 재고량은 얼마인가요?",
      "A랙의 현재 상태는 어떤가요?",
      "어제와 비교해서 입출고량이 어떻게 변했나요?",
      "재고가 부족한 제품을 알려주세요",
      "이상 징후가 발견된 데이터가 있나요?",
    ];

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
