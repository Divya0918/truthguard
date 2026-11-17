import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Send, Plus, Shield, CheckCircle, AlertTriangle,
  XCircle, ChevronDown, ChevronUp, LogOut, Loader2,
  MessageSquare, BookOpen
} from 'lucide-react';
import { chat } from '../../api/client';
import { useAuth } from '../../hooks/useAuth';
import type { AnswerStatus, Citation, ConversationSummary, Message } from '../../types';
import clsx from 'clsx';
import { safeFormatDistanceToNow, safeFormatDate } from '../../utils/date';

// ─── Status badge ────────────────────────────────────────
function StatusBadge({ status }: { status: AnswerStatus | null }) {
  if (!status) return null;
  const map: Record<string, { cls: string; icon: React.ReactNode; label: string }> = {
    approved:  { cls: 'badge-approved',  icon: <CheckCircle  className="w-3 h-3" />, label: 'Verified' },
    abstained: { cls: 'badge-abstained', icon: <AlertTriangle className="w-3 h-3" />, label: 'Needs Review' },
    error:     { cls: 'badge-error',     icon: <XCircle      className="w-3 h-3" />, label: 'Error' },
  };
  const cfg = map[status] ?? map.error;
  return <span className={cfg.cls}>{cfg.icon}{cfg.label}</span>;
}

// ─── Citation card ────────────────────────────────────────
function CitationCard({ cit }: { cit: Citation }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden text-xs">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <span className="font-medium text-gray-700 truncate">{cit.document_title}</span>
        {cit.effective_date && (
          <span className="text-gray-400 shrink-0 ml-2">{cit.effective_date}</span>
        )}
        {open ? <ChevronUp className="w-3 h-3 ml-2 shrink-0" /> : <ChevronDown className="w-3 h-3 ml-2 shrink-0" />}
      </button>
      {open && (
        <div className="px-3 py-2 bg-white border-t border-gray-100 text-gray-600 leading-relaxed">
          {cit.excerpt}
        </div>
      )}
    </div>
  );
}

// ─── Message bubble ───────────────────────────────────────
function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user';
  const [showCits, setShowCits] = useState(false);
  return (
    <div className={clsx('msg-appear flex gap-3 mb-4', isUser && 'flex-row-reverse')}>
      <div className={clsx(
        'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-1',
        isUser ? 'bg-navy-900 text-white' : 'bg-teal-600 text-white'
      )}>
        {isUser ? 'U' : <Shield className="w-4 h-4" />}
      </div>

      <div className={clsx('max-w-[80%] flex flex-col gap-1.5', isUser && 'items-end')}>
        <div className={clsx(
          'px-4 py-3 rounded-2xl text-sm leading-relaxed',
          isUser
            ? 'bg-navy-900 text-white rounded-tr-sm'
            : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm shadow-sm'
        )}>
          {msg.content}
        </div>

        {!isUser && (
          <div className="flex flex-col gap-2 w-full">
            <div className="flex items-center gap-2">
              <StatusBadge status={msg.answer_status} />
              {msg.citations.length > 0 && (
                <button
                  onClick={() => setShowCits(!showCits)}
                  className="flex items-center gap-1 text-xs text-teal-600 hover:text-teal-700 font-medium"
                >
                  <BookOpen className="w-3 h-3" />
                  {msg.citations.length} source{msg.citations.length !== 1 ? 's' : ''}
                  {showCits ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                </button>
              )}
              <span className="text-xs text-gray-400 ml-auto" title={safeFormatDate(msg.created_at)}>
                {safeFormatDistanceToNow(msg.created_at)}
              </span>
            </div>

            {showCits && msg.citations.length > 0 && (
              <div className="space-y-1">
                {msg.citations.map((cit, i) => (
                  <CitationCard key={i} cit={cit} />
                ))}
              </div>
            )}

            {msg.answer_status === 'abstained' && (
              <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                This question has been escalated for admin review. You'll receive an official clarification soon.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Typing indicator ─────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="flex gap-3 mb-4 msg-appear">
      <div className="w-8 h-8 rounded-full bg-teal-600 flex items-center justify-center shrink-0 mt-1">
        <Shield className="w-4 h-4 text-white" />
      </div>
      <div className="bg-white border border-gray-200 shadow-sm rounded-2xl rounded-tl-sm px-4 py-3 flex gap-1.5 items-center">
        <span className="typing-dot w-2 h-2 rounded-full bg-gray-400" />
        <span className="typing-dot w-2 h-2 rounded-full bg-gray-400" />
        <span className="typing-dot w-2 h-2 rounded-full bg-gray-400" />
        <span className="text-xs text-gray-400 ml-1">Agents processing…</span>
      </div>
    </div>
  );
}

const SUGGESTIONS = [
  'What are the current FD interest rates for senior citizens?',
  'What documents are required for a gold loan?',
  'What is the minimum balance for a savings account?',
  'How is the gold loan LTV ratio calculated?',
];

// ─── Main Chat Page ───────────────────────────────────────
export default function ChatPage() {
  const { convId } = useParams();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentConvId, setCurrentConvId] = useState<string | undefined>(convId);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { loadConversations(); }, []);
  useEffect(() => { if (convId) loadConversation(convId); }, [convId]);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);

  const loadConversations = async () => {
    try { setConversations(await chat.listConversations()); } catch { /* ignore */ }
  };

  const loadConversation = async (id: string) => {
    try {
      const detail = await chat.getConversation(id);
      setMessages(detail.messages);
      setCurrentConvId(id);
    } catch { /* ignore */ }
  };

  const handleSend = async (question: string = input.trim()) => {
    if (!question || loading) return;
    setInput('');

    // Optimistically add user message
    const tempId = `tmp-${Date.now()}`;
    setMessages(prev => [...prev, {
      id: tempId, role: 'user', content: question,
      answer_status: null, created_at: new Date().toISOString(), citations: []
    }]);
    setLoading(true);

    try {
      const res = await chat.ask(question, currentConvId);
      setCurrentConvId(res.conversation_id);
      navigate(`/chat/${res.conversation_id}`, { replace: true });

      // Replace temp + add assistant
      setMessages(prev => [
        ...prev.filter(m => m.id !== tempId),
        { id: `u-${res.message_id}`, role: 'user', content: question, answer_status: null,
          created_at: new Date().toISOString(), citations: [] },
        { id: res.message_id, role: 'assistant', content: res.answer,
          answer_status: res.answer_status, created_at: new Date().toISOString(),
          citations: res.citations }
      ]);
      await loadConversations();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Error connecting to server';
      setMessages(prev => [
        ...prev.filter(m => m.id !== tempId),
        { id: `u-${Date.now()}`, role: 'user', content: question, answer_status: null,
          created_at: new Date().toISOString(), citations: [] },
        { id: `err-${Date.now()}`, role: 'assistant',
          content: `⚠ ${detail}`, answer_status: 'error',
          created_at: new Date().toISOString(), citations: [] }
      ]);
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  };

  const startNew = () => {
    setMessages([]);
    setCurrentConvId(undefined);
    navigate('/chat', { replace: true });
  };

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-navy-900 flex flex-col shrink-0 hidden md:flex">
        <div className="flex items-center gap-2 px-4 py-4 border-b border-white/10">
          <Shield className="w-5 h-5 text-teal-400" />
          <span className="text-white font-bold text-sm">TruthGuard</span>
        </div>

        <div className="px-3 py-3 border-b border-white/10">
          <button
            onClick={startNew}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-600 text-white text-sm font-medium hover:bg-teal-700 transition-colors"
          >
            <Plus className="w-4 h-4" /> New Conversation
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
          {conversations.length === 0 ? (
            <p className="text-white/30 text-xs px-2 py-3 text-center">No conversations yet</p>
          ) : conversations.map(conv => (
            <button
              key={conv.id}
              onClick={() => loadConversation(conv.id)}
              className={clsx(
                'w-full text-left px-3 py-2 rounded-lg text-xs transition-colors',
                conv.id === currentConvId
                  ? 'bg-white/15 text-white'
                  : 'text-white/50 hover:bg-white/10 hover:text-white/80'
              )}
            >
              <div className="flex items-center gap-2">
                <MessageSquare className="w-3 h-3 shrink-0" />
                <span className="truncate">{conv.title || 'Untitled'}</span>
              </div>
              <div className="text-white/30 text-xs mt-0.5 pl-5">
                {conv.message_count} message{conv.message_count !== 1 ? 's' : ''}
              </div>
            </button>
          ))}
        </div>

        {/* User */}
        <div className="px-4 py-3 border-t border-white/10 flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-teal-500 flex items-center justify-center text-white text-xs font-bold">
            {user?.full_name?.[0]?.toUpperCase() ?? 'U'}
          </div>
          <span className="text-white/60 text-xs truncate flex-1">{user?.full_name}</span>
          <button onClick={() => { logout(); navigate('/login'); }} className="text-white/30 hover:text-red-400">
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </aside>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-14 bg-white border-b border-gray-200 flex items-center px-4 shrink-0 gap-3">
          <Shield className="w-5 h-5 text-teal-600 md:hidden" />
          <div>
            <h1 className="text-sm font-semibold text-gray-800">Banking Intelligence Assistant</h1>
            <p className="text-xs text-gray-400">Meridian National Bank — Answers verified by AI agents</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full font-medium">Synthetic Demo</span>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {messages.length === 0 && !loading && (
            <div className="flex flex-col items-center justify-center h-full gap-6 text-center">
              <div className="w-16 h-16 rounded-2xl bg-teal-50 border border-teal-100 flex items-center justify-center">
                <Shield className="w-8 h-8 text-teal-500" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-gray-800">Ask about banking policies</h2>
                <p className="text-gray-500 mt-1 text-sm max-w-md">
                  Our AI agents retrieve, synthesize, and verify answers from official bank documents.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(s)}
                    className="text-left px-4 py-3 rounded-xl border border-gray-200 bg-white text-sm text-gray-600 hover:border-teal-300 hover:bg-teal-50 hover:text-teal-700 transition-all"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
          {loading && <TypingIndicator />}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="shrink-0 bg-white border-t border-gray-200 px-4 py-3">
          <div className="flex items-end gap-2 max-w-4xl mx-auto">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
              }}
              placeholder="Ask a banking policy question… (Enter to send, Shift+Enter for new line)"
              rows={1}
              disabled={loading}
              className="flex-1 resize-none input-field min-h-[42px] max-h-32 overflow-y-auto"
              style={{ height: 'auto' }}
              onInput={(e) => {
                const t = e.target as HTMLTextAreaElement;
                t.style.height = 'auto';
                t.style.height = Math.min(t.scrollHeight, 128) + 'px';
              }}
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || loading}
              className="btn-teal h-[42px] px-4 shrink-0"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-xs text-gray-400 text-center mt-1.5">
            Answers are AI-generated from synthetic banking documents. Always verify with official sources.
          </p>
        </div>
      </div>
    </div>
  );
}
