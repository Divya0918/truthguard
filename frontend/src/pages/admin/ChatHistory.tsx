import React, { useEffect, useState } from 'react';
import {
  MessageSquare, ChevronDown, ChevronUp, Shield,
  CheckCircle, AlertTriangle, XCircle, BookOpen, Loader2
} from 'lucide-react';
import { history } from '../../api/client';
import type { AdminMessage, AnswerStatus, ConvAdminSummary } from '../../types';
import clsx from 'clsx';
import { safeFormatDistanceToNow, safeFormatDate } from '../../utils/date';

function StatusBadge({ status }: { status: AnswerStatus | null }) {
  if (!status) return null;
  const map: Record<string, { cls: string; icon: React.ReactNode; label: string }> = {
    approved:  { cls: 'badge-approved',  icon: <CheckCircle className="w-3 h-3"/>, label: 'Verified' },
    abstained: { cls: 'badge-abstained', icon: <AlertTriangle className="w-3 h-3"/>, label: 'Abstained' },
    error:     { cls: 'badge-error',     icon: <XCircle className="w-3 h-3"/>,     label: 'Error' },
  };
  const cfg = map[status] ?? map.error;
  return <span className={cfg.cls}>{cfg.icon}{cfg.label}</span>;
}

function MessageDetail({ msg }: { msg: AdminMessage }) {
  const [showTrace, setShowTrace] = useState(false);
  const [showCits, setShowCits] = useState(false);
  const isUser = msg.role === 'user';

  return (
    <div className={clsx('flex gap-3', isUser && 'flex-row-reverse')}>
      <div className={clsx(
        'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-1',
        isUser ? 'bg-navy-900 text-white' : 'bg-teal-600 text-white'
      )}>
        {isUser ? 'U' : <Shield className="w-3.5 h-3.5" />}
      </div>
      <div className={clsx('max-w-[75%]', isUser && 'items-end flex flex-col')}>
        <div className={clsx(
          'px-3 py-2.5 rounded-xl text-sm leading-relaxed',
          isUser
            ? 'bg-navy-900 text-white rounded-tr-sm'
            : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm'
        )}>
          {msg.content}
        </div>
        {!isUser && (
          <div className="mt-1.5 flex flex-wrap gap-2 text-xs">
            <StatusBadge status={msg.answer_status} />
            {msg.retry_count > 0 && (
              <span className="badge-pending">Retried {msg.retry_count}×</span>
            )}
            {msg.citations.length > 0 && (
              <button
                onClick={() => setShowCits(!showCits)}
                className="text-teal-600 flex items-center gap-1 hover:underline"
              >
                <BookOpen className="w-3 h-3" />
                {msg.citations.length} citation{msg.citations.length !== 1 ? 's' : ''}
              </button>
            )}
            {msg.agent_trace && (
              <button
                onClick={() => setShowTrace(!showTrace)}
                className="text-gray-400 flex items-center gap-1 hover:underline"
              >
                Agent trace {showTrace ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>
            )}
            <span className="text-gray-300">{safeFormatDate(msg.created_at, 'HH:mm')}</span>
          </div>
        )}
        {showCits && (
          <div className="mt-1 space-y-1 w-full">
            {msg.citations.map((c, i) => (
              <div key={i} className="text-xs border border-gray-200 rounded-lg p-2 bg-gray-50">
                <p className="font-medium text-gray-700">{c.document_title}</p>
                {c.effective_date && <p className="text-gray-400">Effective: {c.effective_date}</p>}
                <p className="text-gray-600 mt-1">{c.excerpt}</p>
                <p className="text-gray-300 mt-1">Score: {c.relevance_score.toFixed(3)}</p>
              </div>
            ))}
          </div>
        )}
        {showTrace && msg.agent_trace && (
          <pre className="mt-1 text-xs bg-gray-900 text-green-400 rounded-lg p-3 overflow-x-auto max-h-48 w-full">
            {JSON.stringify(msg.agent_trace, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}

function ConvRow({ conv, onClick, selected }: { conv: ConvAdminSummary; onClick: () => void; selected: boolean }) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors border-b border-gray-100',
        selected && 'bg-teal-50 border-l-2 border-teal-500'
      )}
    >
      <div className="flex items-start gap-3">
        <MessageSquare className="w-4 h-4 text-gray-400 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-800 truncate">{conv.title || 'Untitled'}</p>
          <p className="text-xs text-gray-500 truncate">{conv.user_email || conv.user_id}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-gray-400">{conv.message_count} msgs</span>
            {conv.has_abstention && (
              <span className="badge-abstained text-xs py-0 px-1.5">
                <AlertTriangle className="w-2.5 h-2.5" />Abstained
              </span>
            )}
          </div>
        </div>
        <span className="text-xs text-gray-400 shrink-0" title={safeFormatDate(conv.updated_at)}>
          {safeFormatDistanceToNow(conv.updated_at)}
        </span>
      </div>
    </button>
  );
}

export default function AdminHistory() {
  const [conversations, setConversations] = useState<ConvAdminSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<AdminMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    history.listConversations().then(setConversations).finally(() => setLoading(false));
  }, []);

  const openConv = async (id: string) => {
    setSelected(id);
    setDetailLoading(true);
    try {
      const detail = await history.getConversation(id);
      setMessages(detail.messages);
    } finally { setDetailLoading(false); }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <MessageSquare className="w-6 h-6 text-teal-600" /> Chat History
        </h1>
        <p className="text-gray-500 text-sm mt-0.5">Review all customer conversations and AI responses</p>
      </div>

      <div className="card p-0 overflow-hidden flex" style={{ height: 'calc(100vh - 220px)' }}>
        {/* Left: Conversation list */}
        <div className="w-80 shrink-0 border-r border-gray-200 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin text-teal-600" />
            </div>
          ) : conversations.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p className="text-sm">No conversations yet</p>
            </div>
          ) : (
            conversations.map(conv => (
              <ConvRow
                key={conv.id}
                conv={conv}
                selected={selected === conv.id}
                onClick={() => openConv(conv.id)}
              />
            ))
          )}
        </div>

        {/* Right: Messages */}
        <div className="flex-1 overflow-y-auto">
          {!selected ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              <div className="text-center">
                <MessageSquare className="w-10 h-10 mx-auto mb-2 opacity-20" />
                <p className="text-sm">Select a conversation to inspect</p>
              </div>
            </div>
          ) : detailLoading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
            </div>
          ) : (
            <div className="p-6 space-y-4">
              {messages.map(msg => (
                <MessageDetail key={msg.id} msg={msg} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
