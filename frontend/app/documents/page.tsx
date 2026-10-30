'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  FileText, RefreshCw, Trash2, Search, Filter,
  ChevronLeft, ChevronRight, Eye, RotateCcw, Loader2,
  AlertCircle, CheckCircle, Clock, Zap,
} from 'lucide-react';
import { listDocuments, deleteDocument, reprocessDocument, Document } from '@/lib/api';

const STATUS_OPTIONS = ['', 'pending', 'processing', 'extracted', 'completed', 'needs_review', 'failed'];

function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${status}`}>{status.replace('_', ' ')}</span>;
}

function StatCard({ label, value, color, icon: Icon }: {
  label: string; value: number | string; color: string; icon: React.ElementType;
}) {
  return (
    <div className="glass-card" style={{ padding: '20px 24px', display: 'flex', alignItems: 'center', gap: 16 }}>
      <div style={{
        width: 48, height: 48,
        background: `${color}20`,
        border: `1px solid ${color}40`,
        borderRadius: 12,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon size={22} color={color} />
      </div>
      <div>
        <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-primary)' }}>{value}</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>{label}</div>
      </div>
    </div>
  );
}

export default function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [skip, setSkip] = useState(0);
  const [status, setStatus] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);
  const [reprocessing, setReprocessing] = useState<string | null>(null);

  const limit = 15;

  const fetchDocs = useCallback(async () => {
    try {
      const res = await listDocuments(skip, limit, status || undefined);
      setDocs(res.documents);
      setTotal(res.total);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [skip, status]);

  useEffect(() => {
    let active = true;
    listDocuments(skip, limit, status || undefined)
      .then((res) => {
        if (active) {
          setDocs(res.documents);
          setTotal(res.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) setLoading(false);
      });

    // Auto-refresh if any docs are processing
    const interval = setInterval(() => {
      fetchDocs();
    }, 5000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [skip, status, fetchDocs]);

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this document?')) return;
    setDeleting(id);
    try { await deleteDocument(id); fetchDocs(); }
    catch (e) { alert('Delete failed'); }
    finally { setDeleting(null); }
  };

  const handleReprocess = async (id: string) => {
    setReprocessing(id);
    try { await reprocessDocument(id); fetchDocs(); }
    catch (e) { alert('Reprocess failed'); }
    finally { setReprocessing(null); }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  };

  // Stats
  const stats = {
    total,
    completed: docs.filter(d => d.status === 'completed').length,
    processing: docs.filter(d => ['pending', 'processing', 'extracted'].includes(d.status)).length,
    failed: docs.filter(d => d.status === 'failed').length,
  };

  return (
    <div style={{ padding: '32px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>Documents</h1>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 6 }}>
            {total} documents processed
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn-secondary" onClick={fetchDocs} style={{ gap: 8 }}>
            <RefreshCw size={14} />
            Refresh
          </button>
          <Link href="/" className="btn-primary" style={{ textDecoration: 'none', color: 'white' }}>
            + Upload New
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24, alignItems: 'center' }}>
        <Filter size={14} color="var(--text-muted)" />
        <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>Status:</span>
        {STATUS_OPTIONS.map(s => (
          <button
            key={s}
            onClick={() => { setStatus(s); setSkip(0); }}
            style={{
              padding: '5px 14px',
              borderRadius: 20,
              border: `1px solid ${status === s ? 'var(--accent)' : 'var(--border)'}`,
              background: status === s ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
              color: status === s ? 'var(--accent)' : 'var(--text-secondary)',
              fontSize: 12,
              fontWeight: status === s ? 600 : 400,
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            {s || 'All'}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="glass-card" style={{ overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 48, textAlign: 'center' }}>
            <Loader2 size={28} color="var(--accent)" style={{ animation: 'spin-slow 2s linear infinite' }} />
            <div style={{ marginTop: 12, color: 'var(--text-muted)', fontSize: 13 }}>Loading documents...</div>
          </div>
        ) : docs.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center' }}>
            <FileText size={40} color="var(--text-muted)" style={{ marginBottom: 12 }} />
            <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-secondary)' }}>No documents found</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 6 }}>
              Upload some documents to get started
            </div>
            <Link href="/" style={{
              display: 'inline-block', marginTop: 16,
              padding: '10px 20px', background: 'var(--accent)', color: 'white',
              borderRadius: 8, textDecoration: 'none', fontSize: 14, fontWeight: 600,
            }}>
              Upload Documents
            </Link>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Type</th>
                <th>Status</th>
                <th>Size</th>
                <th>Pages</th>
                <th>Uploaded</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map(doc => (
                <tr key={doc.id} className="animate-fade-in">
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{
                        width: 32, height: 32, borderRadius: 8,
                        background: 'rgba(59, 130, 246, 0.1)',
                        border: '1px solid rgba(59, 130, 246, 0.2)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0,
                      }}>
                        <FileText size={14} color="#60a5fa" />
                      </div>
                      <div>
                        <Link href={`/documents/${doc.id}`} style={{
                          fontSize: 13, fontWeight: 500, color: 'var(--text-primary)',
                          textDecoration: 'none', maxWidth: 200, display: 'block',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }} title={doc.filename}>
                          {doc.filename}
                        </Link>
                        {doc.error && (
                          <div style={{ fontSize: 11, color: '#f87171', marginTop: 2, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {doc.error}
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 500 }}>
                      {doc.doc_type || '—'}
                    </span>
                  </td>
                  <td><StatusBadge status={doc.status} /></td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{formatSize(doc.size_bytes)}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>{doc.page_count ?? '—'}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                    {formatDate(doc.created_at)}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <Link href={`/documents/${doc.id}`} title="View results" style={{
                        padding: '5px 8px', borderRadius: 6, background: 'rgba(59, 130, 246, 0.1)',
                        border: '1px solid rgba(59, 130, 246, 0.2)', display: 'flex',
                        alignItems: 'center', textDecoration: 'none',
                      }}>
                        <Eye size={12} color="#60a5fa" />
                      </Link>
                      {doc.status === 'failed' && (
                        <button title="Reprocess" onClick={() => handleReprocess(doc.id)} style={{
                          padding: '5px 8px', borderRadius: 6, background: 'rgba(245, 158, 11, 0.1)',
                          border: '1px solid rgba(245, 158, 11, 0.2)', cursor: 'pointer', display: 'flex', alignItems: 'center',
                        }}>
                          {reprocessing === doc.id
                            ? <Loader2 size={12} color="#fbbf24" />
                            : <RotateCcw size={12} color="#fbbf24" />
                          }
                        </button>
                      )}
                      <button title="Delete" onClick={() => handleDelete(doc.id)} style={{
                        padding: '5px 8px', borderRadius: 6, background: 'rgba(239, 68, 68, 0.1)',
                        border: '1px solid rgba(239, 68, 68, 0.2)', cursor: 'pointer', display: 'flex', alignItems: 'center',
                      }}>
                        {deleting === doc.id
                          ? <Loader2 size={12} color="#f87171" />
                          : <Trash2 size={12} color="#f87171" />
                        }
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {total > limit && (
          <div style={{
            padding: '16px 20px',
            borderTop: '1px solid var(--border)',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Showing {skip + 1}–{Math.min(skip + limit, total)} of {total}
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn-secondary"
                onClick={() => setSkip(s => Math.max(0, s - limit))}
                disabled={skip === 0}
                style={{ padding: '6px 12px', fontSize: 12 }}
              >
                <ChevronLeft size={14} /> Prev
              </button>
              <button
                className="btn-secondary"
                onClick={() => setSkip(s => s + limit)}
                disabled={skip + limit >= total}
                style={{ padding: '6px 12px', fontSize: 12 }}
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
