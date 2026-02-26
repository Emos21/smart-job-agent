import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import { Bot, ArrowUp, Mic, MicOff, Briefcase, FileText, Target, MessageSquare, Paperclip, X, CheckCircle2, XCircle, Loader2, Lightbulb, Square, ChevronDown, ChevronRight, ThumbsUp, ThumbsDown } from "lucide-react";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { apiFetch, getToken } from "../lib/api";
import type { ChatMessage, AgentActivity, EvaluatorEvent, AgentReasoningEvent, NegotiationRoundEvent, NegotiationResultEvent, Suggestion } from "../types";

const defaultSuggestions = [
  { icon: Briefcase, label: "Search for jobs", prompt: "Search for senior React developer jobs" },
  { icon: FileText, label: "Analyze my resume", prompt: "How can I improve my resume for tech roles?" },
  { icon: Target, label: "Interview prep", prompt: "Help me prepare for a frontend engineer interview" },
  { icon: MessageSquare, label: "Career advice", prompt: "What skills should I learn for 2026?" },
];

interface ChatPanelProps {
  conversationId: number | null;
  onConversationCreated: (id: number) => void;
}

export default function ChatPanel({ conversationId, onConversationCreated }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [toolStatus, setToolStatus] = useState<string | null>(null);
  const [agentActivities, setAgentActivities] = useState<AgentActivity[]>([]);
  const [attachedFile, setAttachedFile] = useState<{ name: string; content: string } | null>(null);
  const [dynamicSuggestions, setDynamicSuggestions] = useState<Suggestion[]>([]);
  const [evaluatorDecisions, setEvaluatorDecisions] = useState<EvaluatorEvent[]>([]);
  const [agentReasoning, setAgentReasoning] = useState<AgentReasoningEvent[]>([]);
  const [reasoningExpanded, setReasoningExpanded] = useState(false);
  const [negotiationRounds, setNegotiationRounds] = useState<NegotiationRoundEvent[]>([]);
  const [negotiationResult, setNegotiationResult] = useState<NegotiationResultEvent | null>(null);
  const [debateExpanded, setDebateExpanded] = useState(false);
  const [pendingTraceIds, setPendingTraceIds] = useState<number[]>([]);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<number, string>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const convIdRef = useRef<number | null>(conversationId);
  const {
    isListening,
    transcript,
    startListening,
    stopListening,
    isSupported,
    setTranscript,
  } = useSpeechRecognition();

  // Keep ref in sync with prop
  useEffect(() => {
    convIdRef.current = conversationId;
  }, [conversationId]);

  // Load messages for existing conversation, or start empty
  useEffect(() => {
    if (conversationId) {
      apiFetch(`/api/conversations/${conversationId}/messages`)
        .then((r) => r.json())
        .then(setMessages)
        .catch(() => {});
    } else {
      setMessages([]);
    }
  }, [conversationId]);

  // Fetch dynamic suggestions for empty state
  useEffect(() => {
    if (!conversationId) {
      apiFetch("/api/suggestions")
        .then((r) => r.json())
        .then(setDynamicSuggestions)
        .catch(() => {});
    }
  }, [conversationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (transcript) {
      setInput(transcript);
      setTranscript("");
    }
  }, [transcript, setTranscript]);

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";

    const ext = file.name.split(".").pop()?.toLowerCase();

    if (ext === "pdf") {
      const formData = new FormData();
      formData.append("file", file);
      try {
        const res = await apiFetch("/api/extract-text", { method: "POST", body: formData });
        const data = await res.json();
        if (data.text) {
          setAttachedFile({ name: file.name, content: data.text });
        }
      } catch {
        // silently fail
      }
    } else {
      const text = await file.text();
      setAttachedFile({ name: file.name, content: text });
    }
  }

  const updateStreamingMessage = useCallback((text: string) => {
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.role === "assistant" && last.id === -1) {
        return [...prev.slice(0, -1), { ...last, content: last.content + text }];
      }
      return [
        ...prev,
        { id: -1, role: "assistant", content: text, created_at: new Date().toISOString() },
      ];
    });
  }, []);

  async function sendMessage(text?: string) {
    const userMsg = (text || input).trim();
    if (!userMsg || loading) return;

    const currentFile = attachedFile;
    setInput("");
    setAttachedFile(null);
    setToolStatus(null);
    setAgentActivities([]);
    setEvaluatorDecisions([]);
    setAgentReasoning([]);
    setReasoningExpanded(false);
    setNegotiationRounds([]);
    setNegotiationResult(null);
    setDebateExpanded(false);
    setPendingTraceIds([]);

    const displayContent = currentFile
      ? `\u{1F4CE} ${currentFile.name}\n\n${userMsg}`
      : userMsg;

    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        role: "user",
        content: displayContent,
        created_at: new Date().toISOString(),
      },
    ]);
    setLoading(true);

    try {
      const body: Record<string, unknown> = {
        message: userMsg,
        conversation_id: convIdRef.current,
      };
      if (currentFile) {
        body.file_content = currentFile.content;
        body.file_name = currentFile.name;
      }

      const token = getToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/api/chat/stream", {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No reader");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === "conversation_id") {
              if (event.conversation_id !== convIdRef.current) {
                convIdRef.current = event.conversation_id;
                onConversationCreated(event.conversation_id);
              }
            } else if (event.type === "routing") {
              // Router classified the intent — if agents will run, show them
              if (event.agents && event.agents.length > 0) {
                setAgentActivities(
                  event.agents.map((a: string) => ({
                    agent: a,
                    status: "running" as const,
                    message: `${a.charAt(0).toUpperCase() + a.slice(1)} Agent queued`,
                  }))
                );
              }
            } else if (event.type === "agent_status") {
              setAgentActivities((prev) => {
                const idx = prev.findIndex((a) => a.agent === event.agent);
                const updated: AgentActivity = {
                  agent: event.agent,
                  status: event.status,
                  message: event.message,
                };
                if (idx >= 0) {
                  return [...prev.slice(0, idx), updated, ...prev.slice(idx + 1)];
                }
                return [...prev, updated];
              });
            } else if (event.type === "evaluator") {
              setEvaluatorDecisions((prev) => [...prev, event as EvaluatorEvent]);
            } else if (event.type === "agent_reasoning") {
              setAgentReasoning((prev) => [...prev, event as AgentReasoningEvent]);
            } else if (event.type === "tool_status") {
              setToolStatus(event.status);
            } else if (event.type === "trace_ids") {
              setPendingTraceIds(event.ids || []);
            } else if (event.type === "negotiation_round") {
              setNegotiationRounds((prev) => [...prev, event as NegotiationRoundEvent]);
            } else if (event.type === "negotiation_result") {
              setNegotiationResult(event as NegotiationResultEvent);
            } else if (event.type === "content") {
              setToolStatus(null);
              updateStreamingMessage(event.text);
            } else if (event.type === "done") {
              setAgentActivities([]);
              setEvaluatorDecisions([]);
              setAgentReasoning([]);
              // Finalize: replace the streaming placeholder ID
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last && last.id === -1) {
                  return [...prev.slice(0, -1), { ...last, id: Date.now() + 1 }];
                }
                return prev;
              });
            }
          } catch {
            // skip malformed events
          }
        }
      }
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
      setToolStatus(null);
    }
  }

  async function handleCancel() {
    if (!convIdRef.current) return;
    try {
      await apiFetch(`/api/chat/${convIdRef.current}/cancel`, { method: "POST" });
    } catch {
      // ignore
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

  async function handleFeedback(traceId: number, rating: "positive" | "negative") {
    try {
      await apiFetch(`/api/traces/${traceId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating }),
      });
      setFeedbackGiven((prev) => ({ ...prev, [traceId]: rating }));
    } catch {
      // ignore
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          /* Empty state — centered welcome */
          <div className="flex flex-col items-center justify-center h-full px-6">
            <div className="w-12 h-12 rounded-full bg-cyan-500/10 flex items-center justify-center mb-6">
              <Bot size={24} className="text-cyan-400" />
            </div>
            <h2 className="text-xl font-semibold text-zinc-100 mb-1">
              How can I help you today?
            </h2>
            <p className="text-sm text-zinc-500 mb-8">
              Search jobs, analyze roles, prep for interviews
            </p>
            {/* Dynamic suggestions from API */}
            {dynamicSuggestions.length > 0 && (
              <div className="w-full max-w-lg space-y-2 mb-4">
                {dynamicSuggestions.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => {
                      if (s.action.startsWith("chat:")) {
                        handleSuggestion(s.action.slice(5));
                      } else {
                        handleSuggestion(s.message);
                      }
                    }}
                    className="w-full flex items-center gap-3 p-3 rounded-xl border border-cyan-500/20 bg-cyan-500/5 text-sm text-zinc-200 text-left hover:bg-cyan-500/10"
                  >
                    <Lightbulb size={14} className="text-cyan-400 shrink-0" />
                    <span>{s.message}</span>
                  </button>
                ))}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3 max-w-lg w-full">
              {defaultSuggestions.map((s) => {
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
            {messages.map((msg, idx) => {
              const isLastAssistant =
                msg.role === "assistant" &&
                msg.id !== -1 &&
                idx === messages.length - 1;
              const showFeedback =
                isLastAssistant &&
                pendingTraceIds.length > 0 &&
                !loading;

              return (
                <div key={msg.id} className="flex gap-3">
                  {msg.role === "assistant" ? (
                    <>
                      <div className="w-7 h-7 rounded-full bg-cyan-500/10 flex items-center justify-center shrink-0 mt-0.5">
                        <Bot size={14} className="text-cyan-400" />
                      </div>
                      <div className="flex-1">
                        <div className="text-sm text-zinc-200 leading-relaxed prose prose-invert prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0 prose-headings:text-zinc-100 prose-strong:text-zinc-100 prose-code:text-cyan-300 prose-code:bg-zinc-800 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-zinc-800">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                        {showFeedback && (
                          <div className="flex items-center gap-1 mt-2">
                            {pendingTraceIds.map((tid) => {
                              const given = feedbackGiven[tid];
                              return (
                                <div key={tid} className="flex items-center gap-1">
                                  <button
                                    onClick={() => handleFeedback(tid, "positive")}
                                    className={`p-1 rounded ${
                                      given === "positive"
                                        ? "text-emerald-400 bg-emerald-500/10"
                                        : "text-zinc-600 hover:text-zinc-400 hover:bg-zinc-800"
                                    }`}
                                    title="Helpful"
                                    disabled={!!given}
                                  >
                                    <ThumbsUp size={14} />
                                  </button>
                                  <button
                                    onClick={() => handleFeedback(tid, "negative")}
                                    className={`p-1 rounded ${
                                      given === "negative"
                                        ? "text-red-400 bg-red-500/10"
                                        : "text-zinc-600 hover:text-zinc-400 hover:bg-zinc-800"
                                    }`}
                                    title="Not helpful"
                                    disabled={!!given}
                                  >
                                    <ThumbsDown size={14} />
                                  </button>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </>
                  ) : (
                    <div className="ml-auto max-w-[80%]">
                      <div className="bg-indigo-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm">
                        {msg.content}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            {loading && !messages.some((m) => m.id === -1) && (
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-full bg-cyan-500/10 flex items-center justify-center shrink-0">
                  <Bot size={14} className="text-cyan-400" />
                </div>
                <div className="text-sm text-zinc-500 py-2 space-y-2">
                  {agentActivities.length > 0 ? (
                    <div className="space-y-1.5">
                      {agentActivities.map((a) => (
                        <div key={a.agent} className="flex items-center gap-2">
                          {a.status === "running" && <Loader2 size={12} className="text-cyan-400" />}
                          {a.status === "complete" && <CheckCircle2 size={12} className="text-emerald-400" />}
                          {a.status === "failed" && <XCircle size={12} className="text-red-400" />}
                          <span className={
                            a.status === "running" ? "text-cyan-400" :
                            a.status === "complete" ? "text-emerald-400" :
                            "text-red-400"
                          }>
                            {a.message}...
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : toolStatus ? (
                    <span className="text-cyan-400">{toolStatus}...</span>
                  ) : (
                    <span className="inline-flex gap-1">
                      <span className="w-1.5 h-1.5 bg-zinc-500 rounded-full" />
                      <span className="w-1.5 h-1.5 bg-zinc-600 rounded-full" />
                      <span className="w-1.5 h-1.5 bg-zinc-700 rounded-full" />
                    </span>
                  )}
                  {/* Evaluator decisions */}
                  {evaluatorDecisions.map((ev, i) => (
                    ev.decision !== "continue" && (
                      <div key={i} className="text-xs text-amber-400/80 bg-amber-500/5 border border-amber-500/10 rounded px-2 py-1">
                        {ev.decision === "skip_next" && `Skipping next step — ${ev.reason}`}
                        {ev.decision === "loop_back" && `Re-running ${ev.target_agent} — ${ev.reason}`}
                        {ev.decision === "stop" && `Stopping early — ${ev.reason}`}
                        {ev.decision === "add_agent" && `Adding ${ev.target_agent} — ${ev.reason}`}
                      </div>
                    )
                  ))}
                  {/* Agent reasoning (collapsible) */}
                  {agentReasoning.length > 0 && (
                    <button
                      onClick={() => setReasoningExpanded(!reasoningExpanded)}
                      className="flex items-center gap-1 text-xs text-zinc-600 hover:text-zinc-400"
                    >
                      {reasoningExpanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                      Agent thinking ({agentReasoning.length} steps)
                    </button>
                  )}
                  {reasoningExpanded && agentReasoning.length > 0 && (
                    <div className="space-y-1 pl-3 border-l border-zinc-800">
                      {agentReasoning.slice(-5).map((r, i) => (
                        <div key={i} className="text-xs text-zinc-600">
                          <span className="text-zinc-500 capitalize">{r.agent}</span>: {r.thought.slice(0, 150)}
                          {r.tool && <span className="text-zinc-700 ml-1">→ {r.tool}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                  {/* Agent Debate (Negotiation) */}
                  {negotiationRounds.length > 0 && (
                    <div className="space-y-1">
                      <button
                        onClick={() => setDebateExpanded(!debateExpanded)}
                        className="flex items-center gap-1 text-xs text-amber-400/80 hover:text-amber-300"
                      >
                        {debateExpanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                        Agent Debate ({negotiationRounds.length} positions)
                      </button>
                      {debateExpanded && (
                        <div className="space-y-1 pl-3 border-l border-amber-500/20">
                          {negotiationRounds.map((nr, i) => (
                            <div key={i} className="text-xs bg-amber-500/5 border border-amber-500/10 rounded px-2 py-1">
                              <span className="text-amber-400 capitalize font-medium">R{nr.round} {nr.agent}</span>
                              <span className="text-zinc-500 ml-1">[{nr.response_type}]</span>
                              <span className="text-zinc-600 ml-1">({Math.round(nr.confidence * 100)}%)</span>
                              <p className="text-zinc-400 mt-0.5">{nr.position.slice(0, 200)}</p>
                            </div>
                          ))}
                        </div>
                      )}
                      {negotiationResult && (
                        <div className={`text-xs rounded px-2 py-1.5 ${
                          negotiationResult.consensus_reached
                            ? "bg-emerald-500/5 border border-emerald-500/20 text-emerald-400"
                            : "bg-amber-500/5 border border-amber-500/20 text-amber-400"
                        }`}>
                          {negotiationResult.consensus_reached
                            ? `Consensus reached (${negotiationResult.rounds_taken} rounds, ${Math.round(negotiationResult.confidence * 100)}% confidence)`
                            : `No consensus after ${negotiationResult.rounds_taken} rounds — using highest confidence position`
                          }
                          {negotiationResult.dissenting_views.length > 0 && (
                            <p className="text-zinc-500 mt-0.5 text-[10px]">
                              Dissent: {negotiationResult.dissenting_views.join("; ").slice(0, 200)}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="px-6 pb-5 pt-2">
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.md,.text,.pdf"
          className="hidden"
          onChange={handleFileSelect}
        />
        {attachedFile && (
          <div className="max-w-3xl mx-auto mb-2 flex items-center gap-2 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-300">
            <Paperclip size={14} className="text-zinc-500 shrink-0" />
            <span className="truncate flex-1">{attachedFile.name}</span>
            <button
              type="button"
              onClick={() => setAttachedFile(null)}
              className="p-0.5 rounded text-zinc-500 hover:text-zinc-200"
            >
              <X size={14} />
            </button>
          </div>
        )}
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
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-2 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
              title="Attach file"
            >
              <Paperclip size={16} />
            </button>
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
            {loading && agentActivities.length > 0 ? (
              <button
                type="button"
                onClick={handleCancel}
                className="p-2 rounded-lg bg-red-600 text-white hover:bg-red-500"
                title="Stop agents"
              >
                <Square size={16} />
              </button>
            ) : (
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="p-2 rounded-lg bg-indigo-600 text-white disabled:opacity-30 disabled:cursor-not-allowed hover:bg-indigo-500"
              >
                <ArrowUp size={16} />
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
