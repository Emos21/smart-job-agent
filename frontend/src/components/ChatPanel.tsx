import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { Bot, ArrowUp, Mic, MicOff, Briefcase, FileText, Target, MessageSquare } from "lucide-react";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import type { ChatMessage } from "../types";

const suggestions = [
  { icon: Briefcase, label: "Search for jobs", prompt: "Search for senior React developer jobs" },
  { icon: FileText, label: "Analyze my resume", prompt: "How can I improve my resume for tech roles?" },
  { icon: Target, label: "Interview prep", prompt: "Help me prepare for a frontend engineer interview" },
  { icon: MessageSquare, label: "Career advice", prompt: "What skills should I learn for 2026?" },
];

export default function ChatPanel({ fresh = false }: { fresh?: boolean }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const {
    isListening,
    transcript,
    startListening,
    stopListening,
    isSupported,
    setTranscript,
  } = useSpeechRecognition();

  useEffect(() => {
    if (!fresh) {
      fetch("/api/chat/history")
        .then((r) => r.json())
        .then(setMessages)
        .catch(() => {});
    }
  }, [fresh]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (transcript) {
      setInput(transcript);
      setTranscript("");
    }
  }, [transcript, setTranscript]);

  async function sendMessage(text?: string) {
    const userMsg = (text || input).trim();
    if (!userMsg || loading) return;

    setInput("");
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        role: "user",
        content: userMsg,
        created_at: new Date().toISOString(),
      },
    ]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: data.response,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          content: "Sorry, something went wrong. Is the backend running?",
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendMessage();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function handleSuggestion(prompt: string) {
    sendMessage(prompt);
  }

  // Auto-resize textarea
  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          /* Empty state — centered welcome */
          <div className="flex flex-col items-center justify-center h-full px-6">
            <div className="w-12 h-12 rounded-full bg-teal-500/10 flex items-center justify-center mb-6">
              <Bot size={24} className="text-teal-400" />
            </div>
            <h2 className="text-xl font-semibold text-zinc-100 mb-1">
              How can I help you today?
            </h2>
            <p className="text-sm text-zinc-500 mb-8">
              Search jobs, analyze roles, prep for interviews
            </p>
            <div className="grid grid-cols-2 gap-3 max-w-lg w-full">
              {suggestions.map((s) => {
                const Icon = s.icon;
                return (
                  <button
                    key={s.label}
                    onClick={() => handleSuggestion(s.prompt)}
                    className="flex items-center gap-3 p-4 rounded-xl border border-zinc-800 bg-zinc-900/50 text-sm text-zinc-300 text-left hover:border-zinc-700 hover:bg-zinc-800/50"
                  >
                    <Icon size={16} className="text-zinc-500 shrink-0" />
                    <span>{s.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          /* Message list */
          <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
            {messages.map((msg) => (
              <div key={msg.id} className="flex gap-3">
                {msg.role === "assistant" ? (
                  <>
                    <div className="w-7 h-7 rounded-full bg-teal-500/10 flex items-center justify-center shrink-0 mt-0.5">
                      <Bot size={14} className="text-teal-400" />
                    </div>
                    <div className="flex-1 text-sm text-zinc-200 leading-relaxed prose prose-invert prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0 prose-headings:text-zinc-100 prose-strong:text-zinc-100 prose-code:text-teal-300 prose-code:bg-zinc-800 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-zinc-800">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </>
                ) : (
                  <div className="ml-auto max-w-[80%]">
                    <div className="bg-teal-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm">
                      {msg.content}
                    </div>
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-full bg-teal-500/10 flex items-center justify-center shrink-0">
                  <Bot size={14} className="text-teal-400" />
                </div>
                <div className="text-sm text-zinc-500 py-2">
                  <span className="inline-flex gap-1">
                    <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full" />
                    <span className="w-1.5 h-1.5 bg-zinc-600 rounded-full" />
                    <span className="w-1.5 h-1.5 bg-zinc-700 rounded-full" />
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="px-6 pb-5 pt-2">
        <form
          onSubmit={handleSubmit}
          className="max-w-3xl mx-auto relative flex items-end gap-2 bg-zinc-900 border border-zinc-800 rounded-2xl px-4 py-2 focus-within:border-zinc-700"
        >
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Message KaziAI..."
            rows={1}
            className="flex-1 bg-transparent text-sm text-zinc-100 placeholder-zinc-600 resize-none outline-none py-1.5 max-h-40"
          />
          <div className="flex items-center gap-1 shrink-0">
            {isSupported && (
              <button
                type="button"
                onClick={isListening ? stopListening : startListening}
                className={`p-2 rounded-lg ${
                  isListening
                    ? "text-red-400 bg-red-500/10"
                    : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
                }`}
                title={isListening ? "Stop listening" : "Voice input"}
              >
                {isListening ? <MicOff size={16} /> : <Mic size={16} />}
              </button>
            )}
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="p-2 rounded-lg bg-teal-600 text-white disabled:opacity-30 disabled:cursor-not-allowed hover:bg-teal-500"
            >
              <ArrowUp size={16} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
