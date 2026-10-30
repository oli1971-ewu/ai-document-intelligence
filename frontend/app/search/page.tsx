'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Search, FileText, Loader2, Cpu, AlertCircle } from 'lucide-react';
import { searchDocuments, SearchResult } from '@/lib/api';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<'keyword' | 'semantic'>('keyword');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState('');
  const [meta, setMeta] = useState<{ count: number; mode: string } | null>(null);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setSearched(false);
    try {
      const res = await searchDocuments(query, mode);
      setResults(res.results);
      setMeta({ count: res.count, mode: res.mode });
      setSearched(true);
    } catch (e) {
      setError('Search failed. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (iso: string) =>
    new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  return (
    <div style={{ padding: '32px', maxWidth: 900, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
          Search Documents
        </h1>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 8 }}>
          Search across all processed documents using keyword or semantic AI search
        </p>
      </div>

      {/* Search box */}
      <div className="glass-card" style={{ padding: 24, marginBottom: 24 }}>
        {/* Mode toggle */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          {(['keyword', 'semantic'] as const).map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              style={{
                padding: '6px 16px',
                borderRadius: 20,
                border: `1px solid ${mode === m ? 'var(--accent)' : 'var(--border)'}`,
                background: mode === m ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                color: mode === m ? 'var(--accent)' : 'var(--text-secondary)',
                fontSize: 12,
                fontWeight: mode === m ? 600 : 400,
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 5,
                transition: 'all 0.2s',
              }}
            >
              {m === 'semantic' && <Cpu size={11} />}
              {m === 'keyword' && <Search size={11} />}
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
          <span style={{ fontSize: 11, color: 'var(--text-muted)', alignSelf: 'center', marginLeft: 8 }}>
            {mode === 'semantic' ? '⚡ AI-powered similarity search' : '🔍 Exact keyword matching'}
          </span>
        </div>

        {/* Input row */}
        <div style={{ display: 'flex', gap: 10 }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <Search size={16} color="var(--text-muted)" style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)' }} />
            <input
              className="input-field"
              placeholder="Search by filename, invoice number, supplier, or any text..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              style={{ paddingLeft: 38 }}
            />
          </div>
          <button className="btn-primary" onClick={handleSearch} disabled={loading || !query.trim()}>
            {loading ? <Loader2 size={16} style={{ animation: 'spin-slow 2s linear infinite' }} /> : <Search size={16} />}
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>

        {/* Quick searches */}
        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Quick:</span>
          {['invoice', 'tax', 'USD', 'failed'].map(q => (
            <button key={q} onClick={() => { setQuery(q); }} style={{
              padding: '3px 10px', borderRadius: 12, border: '1px solid var(--border)',
              background: 'transparent', color: 'var(--text-muted)', fontSize: 11, cursor: 'pointer',
              transition: 'all 0.2s',
            }}>
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: '14px 16px', borderRadius: 8, marginBottom: 16,
          background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)',
          display: 'flex', alignItems: 'center', gap: 8, color: '#f87171', fontSize: 13,
        }}>
          <AlertCircle size={15} /> {error}
        </div>
      )}

      {/* Results */}
      {searched && (
        <div className="animate-fade-in">
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
            {meta?.count} result{meta?.count !== 1 ? 's' : ''} for &quot;<strong style={{ color: 'var(--text-secondary)' }}>{query}</strong>&quot;
            {meta?.mode === 'keyword_fallback' && <span style={{ color: '#f59e0b' }}> (keyword fallback)</span>}
          </div>

          {results.length === 0 ? (
            <div className="glass-card" style={{ padding: 48, textAlign: 'center' }}>
              <Search size={36} color="var(--text-muted)" style={{ marginBottom: 12 }} />
              <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-secondary)' }}>No results found</div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 6 }}>
                Try different keywords or switch to semantic search
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {results.map(r => (
                <Link key={r.id} href={`/documents/${r.id}`} style={{ textDecoration: 'none' }}>
                  <div className="glass-card" style={{
                    padding: '16px 20px',
                    display: 'flex', alignItems: 'center', gap: 16,
                    cursor: 'pointer', transition: 'all 0.2s',
                  }}>
                    <div style={{
                      width: 40, height: 40, flexShrink: 0,
                      background: 'rgba(59, 130, 246, 0.1)',
                      border: '1px solid rgba(59, 130, 246, 0.2)',
                      borderRadius: 10,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <FileText size={18} color="#60a5fa" />
                    </div>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {r.filename}
                      </div>
                      <div style={{ display: 'flex', gap: 16, marginTop: 4, flexWrap: 'wrap' }}>
                        {r.invoice_number && (
                          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                            # {r.invoice_number}
                          </span>
                        )}
                        {r.supplier_name && (
                          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                            {r.supplier_name}
                          </span>
                        )}
                        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                          {formatDate(r.created_at)}
                        </span>
                      </div>
                    </div>

                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      {r.total !== null && (
                        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
                          {r.currency || ''} {Number(r.total).toFixed(2)}
                        </div>
                      )}
                      <span className={`badge badge-${r.status}`} style={{ marginTop: 4 }}>
                        {r.status.replace('_', ' ')}
                      </span>
                    </div>

                    {r.score > 0 && (
                      <div style={{
                        flexShrink: 0, fontSize: 11, color: 'var(--text-muted)',
                        background: 'var(--bg-secondary)', padding: '3px 8px', borderRadius: 12,
                      }}>
                        {(r.score * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
