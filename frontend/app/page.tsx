'use client';

import { useState, useCallback } from 'react';
import Link from 'next/link';
import { Upload, FileText, X, CheckCircle, AlertCircle, Loader2, CloudUpload } from 'lucide-react';
import { uploadDocuments } from '@/lib/api';

interface UploadResult {
  id?: string;
  filename: string;
  error?: string;
  status?: string;
  message?: string;
}

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [dragOver, setDragOver] = useState(false);

  const ALLOWED = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.xlsx', '.xls', '.csv'];

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const arr = Array.from(newFiles);
    const valid = arr.filter(f => {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase();
      return ALLOWED.includes(ext);
    });
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name + f.size));
      return [...prev, ...valid.filter(f => !existing.has(f.name + f.size))];
    });
  }, []);

  const removeFile = (idx: number) => {
    setFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  };

  const handleSubmit = async () => {
    if (!files.length) return;
    setUploading(true);
    setResults([]);
    try {
      const res = await uploadDocuments(files);
      setResults(res.results);
      setFiles([]);
    } catch (err: unknown) {
      setResults([{ filename: 'Upload', error: err instanceof Error ? err.message : 'Upload failed' }]);
    } finally {
      setUploading(false);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const getFileIcon = (name: string) => {
    const ext = name.split('.').pop()?.toLowerCase();
    const colors: Record<string, string> = {
      pdf: '#ef4444', jpg: '#3b82f6', jpeg: '#3b82f6', png: '#3b82f6',
      xlsx: '#10b981', xls: '#10b981', csv: '#f59e0b', tiff: '#8b5cf6', tif: '#8b5cf6',
    };
    return colors[ext || ''] || '#6b7280';
  };

  return (
    <div style={{ padding: '32px', maxWidth: 900, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
          Upload Documents
        </h1>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 8 }}>
          Upload PDF, images, spreadsheets, and CSV files for AI-powered data extraction
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById('file-input')?.click()}
        style={{
          border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: 16,
          padding: '48px 32px',
          textAlign: 'center',
          cursor: 'pointer',
          background: dragOver ? 'rgba(59, 130, 246, 0.05)' : 'var(--bg-card)',
          transition: 'all 0.2s',
          boxShadow: dragOver ? '0 0 30px rgba(59, 130, 246, 0.15)' : 'none',
        }}
      >
        <input
          id="file-input"
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif,.xlsx,.xls,.csv"
          style={{ display: 'none' }}
          onChange={e => e.target.files && addFiles(e.target.files)}
        />
        <div style={{
          width: 64, height: 64,
          background: dragOver ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.1)',
          borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 16px',
          transition: 'all 0.2s',
        }}>
          <CloudUpload size={28} color="#3b82f6" />
        </div>
        <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
          {dragOver ? 'Drop files here' : 'Drag & drop files here'}
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
          or click to browse
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center' }}>
          {['PDF', 'JPG', 'PNG', 'TIFF', 'XLSX', 'XLS', 'CSV'].map(type => (
            <span key={type} style={{
              padding: '3px 10px',
              background: 'rgba(59, 130, 246, 0.1)',
              border: '1px solid rgba(59, 130, 246, 0.2)',
              borderRadius: 20,
              fontSize: 11,
              color: '#60a5fa',
              fontWeight: 600,
            }}>{type}</span>
          ))}
        </div>
      </div>

      {/* File queue */}
      {files.length > 0 && (
        <div className="glass-card animate-fade-in" style={{ marginTop: 20, overflow: 'hidden' }}>
          <div style={{
            padding: '14px 20px',
            borderBottom: '1px solid var(--border)',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              {files.length} file{files.length > 1 ? 's' : ''} queued
            </span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {formatSize(files.reduce((s, f) => s + f.size, 0))} total
            </span>
          </div>
          {files.map((file, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '12px 20px',
              borderBottom: i < files.length - 1 ? '1px solid var(--border)' : 'none',
            }}>
              <div style={{
                width: 36, height: 36,
                background: `${getFileIcon(file.name)}20`,
                border: `1px solid ${getFileIcon(file.name)}40`,
                borderRadius: 8,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <FileText size={16} color={getFileIcon(file.name)} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {file.name}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{formatSize(file.size)}</div>
              </div>
              <button onClick={() => removeFile(i)} style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--text-muted)', padding: 4, borderRadius: 4,
                display: 'flex', alignItems: 'center',
                transition: 'color 0.2s',
              }}>
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Upload button */}
      {files.length > 0 && (
        <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
          <button className="btn-primary" onClick={handleSubmit} disabled={uploading}>
            {uploading ? <Loader2 size={16} className="animate-spin-slow" /> : <Upload size={16} />}
            {uploading ? 'Uploading...' : `Upload ${files.length} File${files.length > 1 ? 's' : ''}`}
          </button>
          <button className="btn-secondary" onClick={() => setFiles([])}>
            Clear All
          </button>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="glass-card animate-fade-in" style={{ marginTop: 24, overflow: 'hidden' }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
              Upload Results
            </span>
          </div>
          {results.map((r, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: 12,
              padding: '14px 20px',
              borderBottom: i < results.length - 1 ? '1px solid var(--border)' : 'none',
            }}>
              {r.error ? (
                <AlertCircle size={18} color="#ef4444" style={{ marginTop: 1, flexShrink: 0 }} />
              ) : (
                <CheckCircle size={18} color="#10b981" style={{ marginTop: 1, flexShrink: 0 }} />
              )}
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
                  {r.filename}
                </div>
                {r.error ? (
                  <div style={{ fontSize: 12, color: '#f87171', marginTop: 2 }}>{r.error}</div>
                ) : (
                  <div style={{ fontSize: 12, color: '#34d399', marginTop: 2 }}>
                    {r.message || 'Queued for processing'}
                  </div>
                )}
              </div>
              {r.id && (
                <Link href={`/documents/${r.id}`} style={{
                  fontSize: 11, color: 'var(--accent)', textDecoration: 'none',
                  fontWeight: 500, flexShrink: 0,
                }}>View →</Link>
              )}
            </div>
          ))}
          {results.some(r => !r.error) && (
            <div style={{ padding: '14px 20px', borderTop: '1px solid var(--border)' }}>
              <Link href="/documents" style={{
                fontSize: 13, color: 'var(--accent)', textDecoration: 'none', fontWeight: 600,
              }}>
                View all documents →
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
