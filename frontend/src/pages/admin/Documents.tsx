import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import {
  FileText, Upload, CheckCircle, XCircle, Clock,
  RefreshCw, AlertCircle, Loader2, Eye, Star,
  Layers, Calendar, Hash, PlusCircle
} from 'lucide-react';
import { documents } from '../../api/client';
import type { Document, DocumentDetail, DocStatus } from '../../types';
import { safeFormatDistanceToNow, safeFormatDate } from '../../utils/date';

function StatusChip({ status }: { status: DocStatus }) {
  const map: Record<DocStatus, { cls: string; icon: ReactNode; label: string }> = {
    published:  { cls: 'badge-approved',  icon: <CheckCircle className="w-3 h-3"/>, label: 'Published' },
    pending:    { cls: 'badge-pending',   icon: <Clock className="w-3 h-3"/>,       label: 'Pending' },
    processing: { cls: 'badge-pending',   icon: <Loader2 className="w-3 h-3 animate-spin"/>, label: 'Processing' },
    rejected:   { cls: 'badge-error',     icon: <XCircle className="w-3 h-3"/>,     label: 'Rejected' },
  };
  const cfg = map[status] ?? map.pending;
  return <span className={cfg.cls}>{cfg.icon}{cfg.label}</span>;
}

function DocumentDetailModal({ docId, onClose, onRefresh }: { docId: string; onClose: () => void; onRefresh: () => void }) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'content' | 'chunks' | 'add_entry'>('content');
  const [newQuestion, setNewQuestion] = useState('');
  const [newAnswer, setNewAnswer] = useState('');
  const [addingEntry, setAddingEntry] = useState(false);
  const [addSuccess, setAddSuccess] = useState('');
  const [addError, setAddError] = useState('');

  const fetchDetail = async () => {
    setLoading(true);
    try {
      const data = await documents.get(docId);
      setDetail(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [docId]);

  const handleAddPriorityEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newQuestion.trim() || !newAnswer.trim()) return;
    setAddingEntry(true);
    setAddSuccess('');
    setAddError('');
    try {
      await documents.addPriorityEntry(newQuestion, newAnswer);
      setAddSuccess('Successfully added Q&A entry with timestamp to Priority Document!');
      setNewQuestion('');
      setNewAnswer('');
      await fetchDetail();
      onRefresh();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to add entry';
      setAddError(msg);
    } finally {
      setAddingEntry(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col my-auto border border-gray-100">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-xl ${detail?.is_priority ? 'bg-amber-100 text-amber-700' : 'bg-teal-50 text-teal-700'}`}>
              {detail?.is_priority ? <Star className="w-5 h-5 fill-amber-500" /> : <FileText className="w-5 h-5" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-gray-900 truncate max-w-lg">
                  {detail?.title || 'Document Details'}
                </h2>
                {detail?.is_priority && (
                  <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-amber-100 text-amber-800 border border-amber-300">
                    ★ Priority Document
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-500 font-mono mt-0.5">
                {detail?.original_filename} • {detail?.file_type?.toUpperCase()}
                {detail?.file_size_bytes ? ` • ${(detail.file_size_bytes / 1024).toFixed(1)} KB` : ''}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl font-light leading-none p-1">
            &times;
          </button>
        </div>

        {/* Loading state */}
        {loading || !detail ? (
          <div className="flex flex-col items-center justify-center py-24 text-gray-500">
            <Loader2 className="w-8 h-8 animate-spin text-teal-600 mb-2" />
            <p className="text-sm font-medium">Loading document details…</p>
          </div>
        ) : (
          <>
            {/* Meta bar */}
            <div className="px-6 py-3 bg-gray-50 border-b border-gray-100 flex flex-wrap items-center gap-4 text-xs text-gray-600">
              <div className="flex items-center gap-1.5">
                <StatusChip status={detail.status} />
              </div>
              <div className="flex items-center gap-1">
                <Layers className="w-3.5 h-3.5 text-gray-400" />
                <span>Chunks: <strong className="text-gray-900">{detail.chunk_count}</strong></span>
              </div>
              {detail.effective_date && (
                <div className="flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-gray-400" />
                  <span>Effective: <strong className="text-gray-900">{detail.effective_date}</strong></span>
                </div>
              )}
              {detail.version_label && (
                <div className="flex items-center gap-1">
                  <Hash className="w-3.5 h-3.5 text-gray-400" />
                  <span>Version: <strong className="text-gray-900">{detail.version_label}</strong></span>
                </div>
              )}
              {detail.published_at && (
                <div className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-gray-400" />
                  <span>Published: <strong className="text-gray-900">{safeFormatDate(detail.published_at, 'yyyy-MM-dd HH:mm')}</strong></span>
                </div>
              )}
            </div>

            {/* Description if present */}
            {detail.description && (
              <div className="px-6 py-2.5 bg-amber-50/50 border-b border-amber-100 text-xs text-amber-900">
                <span className="font-semibold">Description:</span> {detail.description}
              </div>
            )}

            {/* Tabs */}
            <div className="flex border-b border-gray-200 px-6 gap-6 text-sm font-medium">
              <button
                onClick={() => setTab('content')}
                className={`py-3 border-b-2 transition-colors flex items-center gap-1.5 ${
                  tab === 'content'
                    ? 'border-teal-600 text-teal-700 font-semibold'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                <FileText className="w-4 h-4" /> Full Document Content
              </button>
              <button
                onClick={() => setTab('chunks')}
                className={`py-3 border-b-2 transition-colors flex items-center gap-1.5 ${
                  tab === 'chunks'
                    ? 'border-teal-600 text-teal-700 font-semibold'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                <Layers className="w-4 h-4" /> Chunks &amp; Vectors ({detail.chunks?.length ?? detail.chunk_count})
              </button>
              {detail.is_priority && (
                <button
                  onClick={() => setTab('add_entry')}
                  className={`py-3 border-b-2 transition-colors flex items-center gap-1.5 ${
                    tab === 'add_entry'
                      ? 'border-amber-600 text-amber-700 font-semibold'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  <PlusCircle className="w-4 h-4 text-amber-600" /> Add Q&amp;A Entry
                </button>
              )}
            </div>

            {/* Tab Body */}
            <div className="p-6 overflow-y-auto flex-1 max-h-[60vh]">
              {tab === 'content' && (
                <div>
                  {detail.content ? (
                    <div className="bg-gray-50 border border-gray-200 rounded-xl p-5 font-mono text-xs text-gray-800 leading-relaxed whitespace-pre-wrap select-text">
                      {detail.content}
                    </div>
                  ) : (
                    <div className="text-center py-12 text-gray-400">
                      <FileText className="w-8 h-8 mx-auto mb-2 opacity-40" />
                      <p>Full content preview not available for this file type.</p>
                      <p className="text-xs mt-1">Check the Chunks tab to view indexed text.</p>
                    </div>
                  )}
                </div>
              )}

              {tab === 'chunks' && (
                <div className="space-y-4">
                  {detail.chunks && detail.chunks.length > 0 ? (
                    detail.chunks.map((chunk) => (
                      <div key={chunk.chunk_index} className="border border-gray-200 rounded-xl p-4 bg-white shadow-xs">
                        <div className="flex items-center justify-between border-b border-gray-100 pb-2 mb-2">
                          <span className="text-xs font-bold text-teal-700">
                            Chunk #{chunk.chunk_index + 1}
                            {chunk.section_title ? ` — ${chunk.section_title}` : ''}
                          </span>
                          <span className="text-[11px] text-gray-400 font-medium">
                            {chunk.word_count} words
                          </span>
                        </div>
                        <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed font-mono">
                          {chunk.content}
                        </p>
                      </div>
                    ))
                  ) : detail.chunks_preview?.length ? (
                    detail.chunks_preview.map((preview) => (
                      <div key={preview.index} className="border border-gray-200 rounded-xl p-4 bg-white shadow-xs">
                        <div className="flex items-center justify-between border-b border-gray-100 pb-2 mb-2">
                          <span className="text-xs font-bold text-teal-700">
                            Chunk #{preview.index + 1}
                            {preview.section ? ` — ${preview.section}` : ''}
                          </span>
                        </div>
                        <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed font-mono">
                          {preview.excerpt}…
                        </p>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-12 text-gray-400">
                      <Layers className="w-8 h-8 mx-auto mb-2 opacity-40" />
                      <p>No chunks generated yet.</p>
                    </div>
                  )}
                </div>
              )}

              {tab === 'add_entry' && detail.is_priority && (
                <form onSubmit={handleAddPriorityEntry} className="space-y-4 max-w-xl mx-auto">
                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs text-amber-900 leading-relaxed">
                    <strong>Priority Document Immediate Ingestion:</strong> Adding a question and answer here will immediately stamp it with the current timestamp and index it with highest retrieval priority.
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
                      Customer Question *
                    </label>
                    <input
                      className="input-field text-sm"
                      placeholder="e.g. Can an international student open a personal savings account?"
                      value={newQuestion}
                      onChange={(e) => setNewQuestion(e.target.value)}
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
                      Admin Verified Answer *
                    </label>
                    <textarea
                      rows={5}
                      className="input-field text-sm resize-none"
                      placeholder="Type the official bank policy response..."
                      value={newAnswer}
                      onChange={(e) => setNewAnswer(e.target.value)}
                      required
                    />
                  </div>

                  {addSuccess && (
                    <div className="p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg text-xs flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 shrink-0" />
                      {addSuccess}
                    </div>
                  )}

                  {addError && (
                    <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      {addError}
                    </div>
                  )}

                  <div className="flex justify-end pt-2">
                    <button
                      type="submit"
                      disabled={addingEntry || !newQuestion.trim() || !newAnswer.trim()}
                      className="btn-teal flex items-center gap-2 px-5 py-2"
                    >
                      {addingEntry ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlusCircle className="w-4 h-4" />}
                      {addingEntry ? 'Saving & Re-indexing…' : 'Save to Priority Document'}
                    </button>
                  </div>
                </form>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3 border-t border-gray-100 flex justify-end bg-gray-50">
              <button onClick={onClose} className="btn-secondary text-xs">
                Close
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function UploadModal({ onClose, onUploaded }: { onClose: () => void; onUploaded: () => void }) {
  const [form, setForm] = useState({ title: '', description: '', version_label: '', effective_date: '', supersedes_id: '' });
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { setError('Please select a file'); return; }
    if (!form.title.trim()) { setError('Title is required'); return; }
    setLoading(true);
    setError('');
    try {
      const fd = new FormData();
      Object.entries(form).forEach(([k, v]) => fd.append(k, v));
      fd.append('file', file);
      await documents.upload(fd);
      onUploaded();
      onClose();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Upload failed';
      setError(detail);
    } finally { setLoading(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="font-bold text-gray-800 flex items-center gap-2">
            <Upload className="w-4 h-4 text-teal-600" /> Upload Document
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Title *</label>
            <input className="input-field" value={form.title} onChange={e => setForm(p => ({...p, title: e.target.value}))} required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Version Label</label>
              <input className="input-field" placeholder="e.g. v2.0" value={form.version_label} onChange={e => setForm(p => ({...p, version_label: e.target.value}))} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Effective Date</label>
              <input type="date" className="input-field" value={form.effective_date} onChange={e => setForm(p => ({...p, effective_date: e.target.value}))} />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea rows={2} className="input-field resize-none" value={form.description} onChange={e => setForm(p => ({...p, description: e.target.value}))} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Supersedes Document ID (optional)</label>
            <input className="input-field font-mono text-xs" placeholder="UUID of older version" value={form.supersedes_id} onChange={e => setForm(p => ({...p, supersedes_id: e.target.value}))} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">File * (PDF, DOCX, TXT, MD)</label>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={e => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-teal-50 file:text-teal-700 hover:file:bg-teal-100 cursor-pointer"
              required
            />
          </div>
          {error && (
            <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 p-3 rounded-lg">
              <AlertCircle className="w-4 h-4 shrink-0" /> {error}
            </div>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary">Cancel</button>
            <button type="submit" disabled={loading} className="btn-teal">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              {loading ? 'Uploading…' : 'Upload'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function AdminDocuments() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<DocStatus | ''>('');
  const [showUpload, setShowUpload] = useState(false);
  const [acting, setActing] = useState<string | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try { setDocs(await documents.list(filter || undefined)); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [filter]);

  const act = async (id: string, action: 'publish' | 'reject' | 'retry') => {
    setActing(id);
    try {
      if (action === 'publish') await documents.publish(id);
      else if (action === 'reject') await documents.reject(id);
      else await documents.retry(id);
      await load();
    } catch { /* TODO: toast */ }
    finally { setActing(null); }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <FileText className="w-6 h-6 text-teal-600" /> Document Management
          </h1>
          <p className="text-gray-500 text-sm mt-0.5">Upload, inspect full contents &amp; chunks, and manage banking policy documents</p>
        </div>
        <div className="flex gap-3">
          <select
            value={filter}
            onChange={e => setFilter(e.target.value as DocStatus | '')}
            className="input-field w-40 text-sm"
          >
            <option value="">All Status</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="published">Published</option>
            <option value="rejected">Rejected</option>
          </select>
          <button onClick={load} className="btn-secondary" title="Refresh">
            <RefreshCw className="w-4 h-4" />
          </button>
          <button onClick={() => setShowUpload(true)} className="btn-teal">
            <Upload className="w-4 h-4" /> Upload
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden shadow-xs border border-gray-200">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
          </div>
        ) : docs.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
            <p className="font-medium">No documents found</p>
            <p className="text-sm mt-1">Upload a document to get started</p>
            <button onClick={() => setShowUpload(true)} className="btn-teal mt-4">
              <Upload className="w-4 h-4" /> Upload First Document
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Document', 'Type / Version', 'Effective Date', 'Chunks', 'Status', 'Uploaded', 'Actions'].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {docs.map(doc => {
                  const isPriority = doc.is_priority || doc.original_filename?.includes('priority') || doc.version_label === 'PRIORITY';
                  return (
                    <tr
                      key={doc.id}
                      className={`hover:bg-teal-50/30 transition-colors ${isPriority ? 'bg-amber-50/30' : ''}`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {isPriority && (
                            <span title="Priority Document">
                              <Star className="w-4 h-4 text-amber-500 fill-amber-500 shrink-0" />
                            </span>
                          )}
                          <button
                            onClick={() => setSelectedDocId(doc.id)}
                            className="font-medium text-gray-900 hover:text-teal-700 text-left max-w-xs truncate underline-offset-2 hover:underline"
                            title="Click to view details and content"
                          >
                            {doc.title}
                          </button>
                        </div>
                        <div className="text-gray-400 text-xs font-mono mt-0.5">
                          {doc.original_filename}
                          {isPriority && (
                            <span className="ml-2 font-bold text-amber-700">★ PRIORITY DOC</span>
                          )}
                        </div>
                        {doc.processing_error && (
                          <div className="text-red-500 text-xs mt-0.5 truncate max-w-xs" title={doc.processing_error}>
                            ⚠ {doc.processing_error}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-600">
                        <span className="uppercase text-xs font-semibold bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded">
                          {doc.file_type}
                        </span>
                        {doc.version_label && (
                          <span className="ml-1.5 text-xs text-gray-500">
                            {doc.version_label}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{doc.effective_date || '—'}</td>
                      <td className="px-4 py-3 font-medium text-gray-700">{doc.chunk_count}</td>
                      <td className="px-4 py-3"><StatusChip status={doc.status} /></td>
                      <td className="px-4 py-3 text-gray-500 text-xs" title={safeFormatDate(doc.created_at)}>
                        {safeFormatDistanceToNow(doc.created_at)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          {/* Open / View Details Button */}
                          <button
                            onClick={() => setSelectedDocId(doc.id)}
                            className="btn-secondary py-1 px-2.5 text-xs flex items-center gap-1 hover:border-teal-400 hover:text-teal-700"
                            title="Open document and view full text and chunks"
                          >
                            <Eye className="w-3.5 h-3.5 text-teal-600" /> Open
                          </button>

                          {doc.status === 'pending' && (
                            <>
                              <button
                                onClick={() => act(doc.id, 'publish')}
                                disabled={acting === doc.id}
                                className="btn-teal py-1 px-2 text-xs"
                              >
                                {acting === doc.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
                                Publish
                              </button>
                              <button
                                onClick={() => act(doc.id, 'reject')}
                                disabled={acting === doc.id}
                                className="btn-danger py-1 px-2 text-xs"
                              >
                                <XCircle className="w-3 h-3" /> Reject
                              </button>
                            </>
                          )}
                          {doc.status === 'rejected' && (
                            <button
                              onClick={() => act(doc.id, 'retry')}
                              disabled={acting === doc.id}
                              className="btn-secondary py-1 px-2 text-xs"
                            >
                              <RefreshCw className="w-3 h-3" /> Retry
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {showUpload && (
        <UploadModal onClose={() => setShowUpload(false)} onUploaded={load} />
      )}

      {/* Document Detail Modal */}
      {selectedDocId && (
        <DocumentDetailModal
          docId={selectedDocId}
          onClose={() => setSelectedDocId(null)}
          onRefresh={load}
        />
      )}
    </div>
  );
}
