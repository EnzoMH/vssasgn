import React, { useState, useRef, useEffect } from "react";
import axios from "axios";

const API_BASE_URL = "http://localhost:8000/api";

interface ChatMessage {
  text: string;
  sender: "user" | "ai";
}

const AIChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (inputMessage.trim() === "") return;

    const newUserMessage: ChatMessage = { text: inputMessage, sender: "user" };
    setMessages((prevMessages) => [...prevMessages, newUserMessage]);
    setInputMessage("");
    setLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/ai/chat`, {
        question: inputMessage,
      });
      const aiResponse: ChatMessage = {
        text: response.data.answer,
        sender: "ai",
      };
      setMessages((prevMessages) => [...prevMessages, aiResponse]);
    } catch (error) {
      console.error("AI Chat error:", error);
      const errorMessage: ChatMessage = {
        text: "죄송합니다. AI 응답을 가져오는 데 실패했습니다.",
        sender: "ai",
      };
      setMessages((prevMessages) => [...prevMessages, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSendMessage();
    }
  };

  return (
    <div className="ai-chat flex flex-col h-full bg-white rounded-lg shadow-md">
      <h3 className="text-lg font-semibold p-4 border-b border-gray-200">
        AI Chatbot
      </h3>
      <div className="chat-messages flex-1 p-4 overflow-y-auto space-y-2">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`p-2 rounded-lg max-w-[80%] ${
              msg.sender === "user"
                ? "bg-blue-100 self-end ml-auto"
                : "bg-gray-100 self-start mr-auto"
            }`}
          >
            {msg.text}
          </div>
        ))}
        {loading && (
          <div className="p-2 rounded-lg bg-gray-100 self-start mr-auto">
            AI가 답변을 생성 중입니다...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="chat-input p-4 border-t border-gray-200 flex">
        <input
          type="text"
          className="flex-1 p-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="AI에게 질문하세요..."
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={loading}
        />
        <button
          className="ml-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          onClick={handleSendMessage}
          disabled={loading}
        >
          전송
        </button>
      </div>
    </div>
  );
};

export default AIChat;
