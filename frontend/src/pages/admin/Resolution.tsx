import { useState, useEffect } from 'react';
import {
  AlertTriangle, CheckCircle, FileText, Loader2,
  ChevronDown, ChevronUp, Eye, Star, Upload
} from 'lucide-react';
import { resolution } from '../../api/client';
import type { EvidenceItem, ResolutionTask, TaskStatus } from '../../types';
import clsx from 'clsx';
import { safeFormatDistanceToNow, safeFormatDate } from '../../utils/date';

function TaskStatusBadge({ status }: { status: TaskStatus }) {
  const map: Record<TaskStatus, { cls: string; label: string }> = {
    open:      { cls: 'badge-error',     label: '● Open' },
    in_review: { cls: 'badge-abstained', label: '● In Review' },
    resolved:  { cls: 'badge-approved',  label: '● Resolved' },
  };
  const cfg = map[status] || map.open;
  return <span className={cfg.cls}>{cfg.label}</span>;
}

function EvidencePanel({ evidence }: { evidence: EvidenceItem[] }) {
  const [open, setOpen] = useState(false);
  if (!evidence.length) return null;
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 hover:bg-gray-100 text-sm font-medium text-gray-700"
      >
        <span className="flex items-center gap-2"><FileText className="w-4 h-4 text-gray-400" />Retrieved Evidence ({evidence.length})</span>
        {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {open && (
        <div className="divide-y divide-gray-100">
          {evidence.map((ev, i) => (
            <div key={i} className="px-4 py-3">
              <p className="text-xs font-semibold text-teal-700">{ev.document_title}</p>
              <p className="text-xs text-gray-600 mt-1 leading-relaxed">{ev.excerpt}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TaskDetail({
  task: initialTask,
  onClose,
  onResolved,
}: {
  task: ResolutionTask;
  onClose: () => void;
  onResolved: () => void;
}) {
  const [task, setTask] = useState<ResolutionTask>(initialTask);
  const [activeTab, setActiveTab] = useState<'priority_text' | 'upload_doc'>('priority_text');

  // Field 1: Priority Text
  const [answerText, setAnswerText] = useState('');
  const [timestamp, setTimestamp] = useState(() => {
    return new Date().toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
  });
  const [submittingPriority, setSubmittingPriority] = useState(false);
  const [prioritySuccess, setPrioritySuccess] = useState('');
  const [priorityError, setPriorityError] = useState('');

  // Field 2: Upload Doc
  const [docTitle, setDocTitle] = useState('');
  const [docEffectiveDate, setDocEffectiveDate] = useState('');
  const [docFile, setDocFile] = useState<File | null>(null);
  const [submittingDoc, setSubmittingDoc] = useState(false);
  const [docSuccess, setDocSuccess] = useState('');
  const [docError, setDocError] = useState('');

  const handleResolvePriority = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!answerText.trim()) return;
    setSubmittingPriority(true);
    setPrioritySuccess('');
    setPriorityError('');
    try {
      const updated = await resolution.resolvePriority(task.id, answerText.trim(), timestamp);
      setTask(updated);
      setPrioritySuccess('Successfully stored answer in Priority Document with timestamp and marked task as Resolved!');
      onResolved();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to resolve task';
      setPriorityError(msg);
    } finally {
      setSubmittingPriority(false);
    }
  };

  const handleUploadPolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docFile || !docTitle.trim()) return;
    setSubmittingDoc(true);
    setDocSuccess('');
    setDocError('');
    try {
      const fd = new FormData();
      fd.append('title', docTitle.trim());
      fd.append('effective_date', docEffectiveDate);
      fd.append('file', docFile);
      await resolution.uploadPolicy(task.id, fd);
      setDocSuccess('New policy document uploaded to knowledge base and task marked as Resolved!');
      setTask(p => ({ ...p, status: 'resolved' }));
      onResolved();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to upload document';
      setDocError(msg);
    } finally {
      setSubmittingDoc(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl my-8 border border-gray-100 max-h-[90vh] flex flex-col">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            <h2 className="font-bold text-gray-800 text-lg">Resolution Task Review</h2>
          </div>
          <div className="flex items-center gap-3">
            <TaskStatusBadge status={task.status} />
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
          </div>
        </div>

        {/* Modal Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          {/* Question Box */}
          <div>
            <p className="text-xs font-bold uppercase text-gray-400 mb-1.5">Customer Question</p>
            <div className="text-gray-900 font-semibold bg-amber-50/70 border border-amber-200 rounded-xl px-4 py-3 text-sm leading-relaxed">
              "{task.question}"
            </div>
          </div>

          {/* Why abstained / Policy Files Checked */}
          <div>
            <p className="text-xs font-bold uppercase text-gray-400 mb-1.5">Agent Abstention Reason &amp; Files Checked</p>
            <div className="text-xs text-gray-700 bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 leading-relaxed whitespace-pre-wrap">
              {task.abstention_reason}
            </div>
          </div>

          {/* Evidence if any */}
          <EvidencePanel evidence={task.retrieved_evidence} />

          {/* Resolution Options Container */}
          <div className="border border-teal-200 rounded-2xl overflow-hidden bg-white shadow-xs">
            <div className="bg-teal-50/70 border-b border-teal-100 px-5 py-3">
              <h3 className="text-sm font-bold text-teal-900">Choose Resolution Method</h3>
              <p className="text-xs text-teal-700 mt-0.5">
                Answer via Priority Document (fastest, high precedence) or upload a new policy document.
              </p>
            </div>

            {/* Sub-Tabs */}
            <div className="flex border-b border-gray-200 bg-gray-50/50">
              <button
                type="button"
                onClick={() => setActiveTab('priority_text')}
                className={`flex-1 py-3 px-4 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition-colors ${
                  activeTab === 'priority_text'
                    ? 'border-amber-500 text-amber-900 bg-white'
                    : 'border-transparent text-gray-500 hover:text-gray-800'
                }`}
              >
                <Star className="w-4 h-4 fill-amber-500 text-amber-500" />
                Field 1: Text Answer (Save to Priority Document)
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('upload_doc')}
                className={`flex-1 py-3 px-4 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition-colors ${
                  activeTab === 'upload_doc'
                    ? 'border-teal-600 text-teal-900 bg-white'
                    : 'border-transparent text-gray-500 hover:text-gray-800'
                }`}
              >
                <Upload className="w-4 h-4 text-teal-600" />
                Field 2: Upload New Document (Add to Library)
              </button>
            </div>

            <div className="p-5">
              {/* Field 1: Priority Text Area */}
              {activeTab === 'priority_text' && (
                <form onSubmit={handleResolvePriority} className="space-y-4">
                  <div className="p-3 bg-amber-50/60 rounded-xl border border-amber-200 text-xs text-amber-900 leading-relaxed">
                    <strong>Priority Document Storage:</strong> Saving here adds this Q&amp;A pair to the central Priority Document with a verified timestamp. On future inquiries, TruthGuard will immediately retrieve this verified answer (and compare timestamps against newer documents).
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
                      Official Admin Answer *
                    </label>
                    <textarea
                      rows={4}
                      className="input-field text-sm resize-none"
                      placeholder="Type the official answer that should resolve this customer question..."
                      value={answerText}
                      onChange={(e) => setAnswerText(e.target.value)}
                      required
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
                        Resolution Timestamp (UTC)
                      </label>
                      <input
                        className="input-field text-xs font-mono"
                        value={timestamp}
                        onChange={(e) => setTimestamp(e.target.value)}
                        placeholder="YYYY-MM-DD HH:mm:ss UTC"
                      />
                    </div>
                  </div>

                  {prioritySuccess && (
                    <div className="p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg text-xs flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 shrink-0" />
                      {prioritySuccess}
                    </div>
                  )}

                  {priorityError && (
                    <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      {priorityError}
                    </div>
                  )}

                  <div className="flex justify-end pt-2">
                    <button
                      type="submit"
                      disabled={submittingPriority || !answerText.trim()}
                      className="btn-teal flex items-center gap-2 px-5 py-2"
                    >
                      {submittingPriority ? <Loader2 className="w-4 h-4 animate-spin" /> : <Star className="w-4 h-4 fill-amber-300" />}
                      {submittingPriority ? 'Saving & Re-indexing…' : 'Save to Priority Document & Resolve'}
                    </button>
                  </div>
                </form>
              )}

              {/* Field 2: Upload New Document */}
              {activeTab === 'upload_doc' && (
                <form onSubmit={handleUploadPolicy} className="space-y-4">
                  <div className="p-3 bg-teal-50/60 rounded-xl border border-teal-200 text-xs text-teal-900 leading-relaxed">
                    <strong>Document Library Addition:</strong> Uploading here registers a new policy document into the bank's general knowledge library, automatically chunks and embeds the text, and resolves this task.
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
                      Document Title *
                    </label>
                    <input
                      className="input-field text-sm"
                      placeholder="e.g. Meridian Education Loan Policy v1.0"
                      value={docTitle}
                      onChange={(e) => setDocTitle(e.target.value)}
                      required
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
                        Effective Date
                      </label>
                      <input
                        type="date"
                        className="input-field text-sm"
                        value={docEffectiveDate}
                        onChange={(e) => setDocEffectiveDate(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
                        Document File * (.txt, .md, .pdf, .docx)
                      </label>
                      <input
                        type="file"
                        accept=".pdf,.docx,.txt,.md"
                        onChange={(e) => setDocFile(e.target.files?.[0] || null)}
                        className="block w-full text-xs text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-teal-50 file:text-teal-700 hover:file:bg-teal-100 cursor-pointer"
                        required
                      />
                    </div>
                  </div>

                  {docSuccess && (
                    <div className="p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg text-xs flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 shrink-0" />
                      {docSuccess}
                    </div>
                  )}

                  {docError && (
                    <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      {docError}
                    </div>
                  )}

                  <div className="flex justify-end pt-2">
                    <button
                      type="submit"
                      disabled={submittingDoc || !docFile || !docTitle.trim()}
                      className="btn-teal flex items-center gap-2 px-5 py-2"
                    >
                      {submittingDoc ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                      {submittingDoc ? 'Uploading & Processing…' : 'Upload Document & Resolve'}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>

          <div className="text-xs text-gray-500">
            Task opened {safeFormatDistanceToNow(task.created_at)} ({safeFormatDate(task.created_at)})
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-gray-100 flex justify-end bg-gray-50">
          <button onClick={onClose} className="btn-secondary text-xs">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AdminResolution() {
  const [tasks, setTasks] = useState<ResolutionTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<TaskStatus | ''>('');
  const [selected, setSelected] = useState<ResolutionTask | null>(null);

  const load = async () => {
    setLoading(true);
    try { setTasks(await resolution.listTasks(filter || undefined)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [filter]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <AlertTriangle className="w-6 h-6 text-amber-500" /> Resolution Center
          </h1>
          <p className="text-gray-500 text-sm mt-0.5">Review unanswered customer questions, update the Priority Document, or upload new policies</p>
        </div>
        <select
          value={filter}
          onChange={e => setFilter(e.target.value as TaskStatus | '')}
          className="input-field w-40 text-sm"
        >
          <option value="">All Status</option>
          <option value="open">Open</option>
          <option value="in_review">In Review</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Open', count: tasks.filter(t => t.status === 'open').length, color: 'text-red-600', bg: 'bg-red-50' },
          { label: 'In Review', count: tasks.filter(t => t.status === 'in_review').length, color: 'text-amber-600', bg: 'bg-amber-50' },
          { label: 'Resolved', count: tasks.filter(t => t.status === 'resolved').length, color: 'text-green-600', bg: 'bg-green-50' },
        ].map(({ label, count, color, bg }) => (
          <div key={label} className={clsx('card flex items-center gap-4', bg, 'border-0')}>
            <span className={clsx('text-3xl font-bold', color)}>{count}</span>
            <span className="text-gray-600 text-sm font-medium">{label}</span>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden shadow-xs border border-gray-200">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
          </div>
        ) : tasks.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <CheckCircle className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="font-medium">No resolution tasks</p>
            <p className="text-sm mt-1">
              {filter ? `No tasks with status "${filter}"` : 'All customer questions are resolved'}
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Customer Question', 'Status', 'Opened', 'Action'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tasks.map(task => (
                <tr key={task.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 max-w-md">
                    <p className="text-gray-800 font-semibold truncate">"{task.question}"</p>
                    <p className="text-gray-500 text-xs truncate mt-0.5" title={task.abstention_reason}>
                      {task.abstention_reason}
                    </p>
                  </td>
                  <td className="px-4 py-3"><TaskStatusBadge status={task.status} /></td>
                  <td className="px-4 py-3 text-gray-500 text-xs" title={safeFormatDate(task.created_at)}>
                    {safeFormatDistanceToNow(task.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => setSelected(task)}
                      className="btn-teal py-1 px-3 text-xs flex items-center gap-1.5"
                    >
                      <Eye className="w-3.5 h-3.5" /> Resolve / Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <TaskDetail
          task={selected}
          onClose={() => { setSelected(null); load(); }}
          onResolved={() => { load(); }}
        />
      )}
    </div>
  );
}
