'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft, RefreshCw, RotateCcw, Save, AlertTriangle,
  CheckCircle, XCircle, Info, Loader2, FileText, Clock,
  DollarSign, User, Building, Calendar, Hash, Edit2, X,
} from 'lucide-react';
import {
  getDocumentResults, getDocumentStatus, correctDocument, reprocessDocument,
  DocumentResults, ProcessingEvent, Invoice,
} from '@/lib/api';

function ValidationBadge({ severity }: { severity: string }) {
  const config = {
    error: { bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.3)', color: '#f87171', Icon: XCircle },
    warning: { bg: 'rgba(245, 158, 11, 0.15)', border: 'rgba(245, 158, 11, 0.3)', color: '#fbbf24', Icon: AlertTriangle },
    info: { bg: 'rgba(59, 130, 246, 0.15)', border: 'rgba(59, 130, 246, 0.3)', color: '#60a5fa', Icon: Info },
  }[severity] ?? { bg: 'rgba(107, 114, 128, 0.15)', border: 'rgba(107, 114, 128, 0.3)', color: '#9ca3af', Icon: Info };
  const { bg, border, color, Icon } = config;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px', borderRadius: 12, background: bg, border: `1px solid ${border}`, color, fontSize: 11, fontWeight: 600 }}>
      <Icon size={11} />
      {severity}
    </span>
  );
}

function InvoiceField({ label, value, icon: Icon, editable, onChange, type = 'text' }: {
  label: string; value: string | number | null; icon?: React.ElementType;
  editable?: boolean; onChange?: (v: string) => void; type?: string;
}) {
  return (
    <div style={{ padding: '14px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 5 }}>
        {Icon && <Icon size={11} />}{label}
      </div>
      {editable && onChange ? (
        <input
          className="input-field"
          type={type}
          value={value ?? ''}
          onChange={e => onChange(e.target.value)}
          style={{ padding: '6px 10px', fontSize: 14 }}
        />
      ) : (
        <div style={{ fontSize: 14, color: value ? 'var(--text-primary)' : 'var(--text-muted)', fontWeight: value ? 500 : 400 }}>
          {value ?? '—'}
        </div>
      )}
    </div>
  );
}

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [data, setData] = useState<DocumentResults | null>(null);
  const [status, setStatus] = useState<{ status: string; events: ProcessingEvent[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [corrections, setCorrections] = useState<Partial<Invoice>>({});
  const [saving, setSaving] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [results, stat] = await Promise.all([
        getDocumentResults(id),
        getDocumentStatus(id),
      ]);
      setData(results);
      setStatus(stat);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    let active = true;
    Promise.all([
      getDocumentResults(id),
      getDocumentStatus(id),
    ])
      .then(([results, stat]) => {
        if (active) {
          setData(results);
          setStatus(stat);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) setLoading(false);
      });

    const interval = setInterval(() => {
      if (data?.document.status && ['pending', 'processing', 'extracted'].includes(data.document.status)) {
        fetchData();
      }
    }, 3000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [id, fetchData, data?.document.status]);

  const startEditing = () => {
    setEditing(true);
    setCorrections({
      invoice_number: data?.invoice?.invoice_number ?? undefined,
      invoice_date: data?.invoice?.invoice_date ?? undefined,
      supplier_name: data?.invoice?.supplier_name ?? undefined,
      customer_name: data?.invoice?.customer_name ?? undefined,
      subtotal: data?.invoice?.subtotal ?? undefined,
      tax: data?.invoice?.tax ?? undefined,
      total: data?.invoice?.total ?? undefined,
      currency: data?.invoice?.currency ?? undefined,
    });
  };

  const saveCorrections = async () => {
    setSaving(true);
    try {
      await correctDocument(id, corrections);
      await fetchData();
      setEditing(false);
    } catch (e) {
      alert('Failed to save corrections');
    } finally {
      setSaving(false);
    }
  };

  const handleReprocess = async () => {
    setReprocessing(true);
    try { await reprocessDocument(id); await fetchData(); }
    catch (e) { alert('Reprocess failed'); }
    finally { setReprocessing(false); }
  };

  const setCorrectionField = (field: keyof Invoice, value: string) => {
    setCorrections(prev => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '50vh' }}>
        <Loader2 size={32} color="var(--accent)" style={{ animation: 'spin-slow 2s linear infinite' }} />
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ padding: 32, textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)' }}>Document not found.</p>
        <Link href="/documents" style={{ color: 'var(--accent)' }}>← Back to documents</Link>
      </div>
    );
  }

  const { document: doc, invoice, validation_issues } = data;
  const isProcessing = ['pending', 'processing', 'extracted'].includes(doc.status);
  const errorIssues = validation_issues.filter(i => i.severity === 'error');
  const warnIssues = validation_issues.filter(i => i.severity === 'warning');

  return (
    <div style={{ padding: '32px', maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 28 }}>
        <Link href="/documents" style={{
          display: 'flex', alignItems: 'center', gap: 6,
          color: 'var(--text-muted)', textDecoration: 'none', fontSize: 13,
          padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)',
        }}>
          <ArrowLeft size={14} /> Back
        </Link>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {doc.filename}
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
            <span className={`badge badge-${doc.status}`}>{doc.status.replace('_', ' ')}</span>
            {doc.doc_type && <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 500 }}>{doc.doc_type}</span>}
            {doc.page_count && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{doc.page_count} pages</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-secondary" onClick={fetchData} style={{ padding: '8px 12px', gap: 6 }}>
            <RefreshCw size={13} />
          </button>
          {doc.status === 'failed' && (
            <button className="btn-secondary" onClick={handleReprocess} disabled={reprocessing} style={{ gap: 6 }}>
              {reprocessing ? <Loader2 size={13} /> : <RotateCcw size={13} />}
              Reprocess
            </button>
          )}
          {!editing && invoice && (
            <button className="btn-primary" onClick={startEditing} style={{ gap: 6 }}>
              <Edit2 size={13} /> Edit
            </button>
          )}
          {editing && (
            <>
              <button className="btn-secondary" onClick={() => setEditing(false)} style={{ gap: 6 }}>
                <X size={13} /> Cancel
              </button>
              <button className="btn-primary" onClick={saveCorrections} disabled={saving} style={{ gap: 6 }}>
                {saving ? <Loader2 size={13} /> : <Save size={13} />}
                {saving ? 'Saving...' : 'Save'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Processing spinner */}
      {isProcessing && (
        <div className="glass-card animate-fade-in" style={{
          padding: '20px 24px', marginBottom: 20,
          background: 'rgba(59, 130, 246, 0.05)',
          border: '1px solid rgba(59, 130, 246, 0.2)',
          display: 'flex', alignItems: 'center', gap: 14,
        }}>
          <Loader2 size={20} color="#60a5fa" style={{ animation: 'spin-slow 2s linear infinite', flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#60a5fa' }}>Processing document...</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              {doc.status === 'pending' ? 'Queued' : doc.status === 'processing' ? 'Running OCR and extraction' : 'Running AI analysis'}
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {doc.status === 'failed' && doc.error && (
        <div className="glass-card" style={{
          padding: '16px 20px', marginBottom: 20,
          background: 'rgba(239, 68, 68, 0.05)',
          border: '1px solid rgba(239, 68, 68, 0.2)',
          display: 'flex', gap: 12,
        }}>
          <XCircle size={18} color="#f87171" style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#f87171' }}>Processing failed</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{doc.error}</div>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Invoice data */}
        <div className="glass-card" style={{ padding: '20px 24px' }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileText size={15} color="var(--accent)" /> Invoice Data
            {invoice?.confidence && (
              <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 'auto' }}>
                Confidence: {(invoice.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
          {editing ? (
            <>
              <InvoiceField label="Invoice Number" icon={Hash} value={corrections.invoice_number ?? null} editable onChange={v => setCorrectionField('invoice_number', v)} />
              <InvoiceField label="Invoice Date" icon={Calendar} value={corrections.invoice_date ?? null} editable onChange={v => setCorrectionField('invoice_date', v)} />
              <InvoiceField label="Supplier" icon={Building} value={corrections.supplier_name ?? null} editable onChange={v => setCorrectionField('supplier_name', v)} />
              <InvoiceField label="Customer" icon={User} value={corrections.customer_name ?? null} editable onChange={v => setCorrectionField('customer_name', v)} />
              <InvoiceField label="Currency" value={corrections.currency ?? null} editable onChange={v => setCorrectionField('currency', v)} />
              <InvoiceField label="Subtotal" icon={DollarSign} value={corrections.subtotal ?? null} editable type="number" onChange={v => setCorrectionField('subtotal', v)} />
              <InvoiceField label="Tax" icon={DollarSign} value={corrections.tax ?? null} editable type="number" onChange={v => setCorrectionField('tax', v)} />
              <InvoiceField label="Total" icon={DollarSign} value={corrections.total ?? null} editable type="number" onChange={v => setCorrectionField('total', v)} />
            </>
          ) : invoice ? (
            <>
              <InvoiceField label="Invoice Number" icon={Hash} value={invoice.invoice_number} />
              <InvoiceField label="Invoice Date" icon={Calendar} value={invoice.invoice_date} />
              <InvoiceField label="Supplier" icon={Building} value={invoice.supplier_name} />
              <InvoiceField label="Customer" icon={User} value={invoice.customer_name} />
              <InvoiceField label="Currency" value={invoice.currency} />
              <InvoiceField label="Subtotal" icon={DollarSign} value={invoice.subtotal !== null ? `${invoice.currency || ''} ${Number(invoice.subtotal).toFixed(2)}` : null} />
              <InvoiceField label="Tax" icon={DollarSign} value={invoice.tax !== null ? `${invoice.currency || ''} ${Number(invoice.tax).toFixed(2)}` : null} />
              <div style={{ padding: '14px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, letterSpacing: 0.5, textTransform: 'uppercase' }}>
                  Total
                </div>
                <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)' }}>
                  {invoice.total !== null ? `${invoice.currency || ''} ${Number(invoice.total).toFixed(2)}` : '—'}
                </div>
              </div>
            </>
          ) : (
            <div style={{ padding: '30px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
              {isProcessing ? 'Extracting data...' : 'No invoice data extracted'}
            </div>
          )}
        </div>

        {/* Validation & Processing events */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Validation */}
          <div className="glass-card" style={{ padding: '20px 24px' }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              {errorIssues.length > 0 ? <AlertTriangle size={15} color="#f59e0b" /> : <CheckCircle size={15} color="#10b981" />}
              Validation
              {validation_issues.length > 0 && (
                <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
                  {errorIssues.length} error{errorIssues.length !== 1 ? 's' : ''}, {warnIssues.length} warning{warnIssues.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>
            {validation_issues.length === 0 ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#34d399', fontSize: 13 }}>
                <CheckCircle size={16} />
                All validation checks passed
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {validation_issues.map(issue => (
                  <div key={issue.id} style={{
                    padding: '10px 12px', borderRadius: 8,
                    background: issue.severity === 'error' ? 'rgba(239, 68, 68, 0.05)' : 'rgba(245, 158, 11, 0.05)',
                    border: `1px solid ${issue.severity === 'error' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)'}`,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <ValidationBadge severity={issue.severity} />
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 500 }}>
                        {issue.code}{issue.field ? ` · ${issue.field}` : ''}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{issue.message}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Processing events */}
          <div className="glass-card" style={{ padding: '20px 24px' }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Clock size={15} color="var(--accent)" /> Processing Timeline
            </div>
            {status?.events?.length === 0 && (
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No events yet</div>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {status?.events?.map((ev, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  padding: '8px 10px', borderRadius: 8,
                  background: ev.status === 'failed' ? 'rgba(239, 68, 68, 0.05)' : 'rgba(16, 185, 129, 0.05)',
                }}>
                  {ev.status === 'ok' ? (
                    <CheckCircle size={13} color="#10b981" style={{ marginTop: 1, flexShrink: 0 }} />
                  ) : ev.status === 'failed' ? (
                    <XCircle size={13} color="#ef4444" style={{ marginTop: 1, flexShrink: 0 }} />
                  ) : (
                    <Loader2 size={13} color="#60a5fa" style={{ marginTop: 1, flexShrink: 0 }} />
                  )}
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', textTransform: 'capitalize' }}>
                      {ev.stage} {ev.status !== 'ok' ? `(${ev.status})` : ''}
                    </div>
                    {ev.message && (
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{ev.message}</div>
                    )}
                    {ev.duration_ms && (
                      <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{ev.duration_ms}ms</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Line items */}
      {invoice?.line_items && invoice.line_items.length > 0 && (
        <div className="glass-card animate-fade-in" style={{ marginTop: 20, overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
            Line Items ({invoice.line_items.length})
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Description</th>
                <th>Qty</th>
                <th>Unit Price</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {invoice.line_items.map((item, i) => (
                <tr key={i}>
                  <td style={{ color: 'var(--text-muted)', width: 40 }}>{i + 1}</td>
                  <td>{item.description || '—'}</td>
                  <td style={{ color: 'var(--text-muted)' }}>{item.quantity ?? '—'}</td>
                  <td style={{ color: 'var(--text-muted)' }}>{item.unit_price !== null ? Number(item.unit_price).toFixed(2) : '—'}</td>
                  <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    {item.amount !== null ? `${invoice.currency || ''} ${Number(item.amount).toFixed(2)}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
