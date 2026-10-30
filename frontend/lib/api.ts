const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface Document {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: string;
  doc_type: string | null;
  page_count: number | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface LineItem {
  description: string | null;
  quantity: number | null;
  unit_price: number | null;
  amount: number | null;
}

export interface Invoice {
  id: string;
  invoice_number: string | null;
  invoice_date: string | null;
  supplier_name: string | null;
  customer_name: string | null;
  subtotal: number | null;
  tax: number | null;
  total: number | null;
  currency: string | null;
  confidence: number | null;
  source: string;
  line_items: LineItem[];
}

export interface ValidationIssue {
  id: string;
  code: string;
  severity: string;
  field: string | null;
  message: string;
}

export interface ProcessingEvent {
  stage: string;
  status: string;
  message: string | null;
  duration_ms: number | null;
  created_at: string;
}

export interface DocumentResults {
  document: Document;
  invoice: Invoice | null;
  validation_issues: ValidationIssue[];
}

export interface SearchResult {
  id: string;
  filename: string;
  status: string;
  doc_type: string | null;
  created_at: string;
  invoice_number: string | null;
  supplier_name: string | null;
  total: number | null;
  currency: string | null;
  score: number;
}

// --- Upload ---
export async function uploadDocuments(files: File[]): Promise<{
  uploaded: number;
  results: Array<{ id?: string; filename: string; error?: string; status?: string }>;
}> {
  const formData = new FormData();
  files.forEach(f => formData.append('files', f));
  const res = await fetch(`${API_BASE}/api/documents/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  return res.json();
}

// --- List documents ---
export async function listDocuments(
  skip = 0,
  limit = 20,
  status?: string
): Promise<{ total: number; skip: number; limit: number; documents: Document[] }> {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (status) params.set('status', status);
  const res = await fetch(`${API_BASE}/api/documents?${params}`);
  if (!res.ok) throw new Error('Failed to fetch documents');
  return res.json();
}

// --- Get status ---
export async function getDocumentStatus(id: string): Promise<{
  id: string;
  status: string;
  error: string | null;
  events: ProcessingEvent[];
}> {
  const res = await fetch(`${API_BASE}/api/documents/${id}/status`);
  if (!res.ok) throw new Error('Failed to fetch status');
  return res.json();
}

// --- Get results ---
export async function getDocumentResults(id: string): Promise<DocumentResults> {
  const res = await fetch(`${API_BASE}/api/documents/${id}/results`);
  if (!res.ok) throw new Error('Failed to fetch results');
  return res.json();
}

// --- Correct ---
export async function correctDocument(id: string, payload: Partial<Invoice>): Promise<void> {
  const res = await fetch(`${API_BASE}/api/documents/${id}/correct`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to save corrections');
}

// --- Reprocess ---
export async function reprocessDocument(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/documents/${id}/reprocess`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reprocess');
}

// --- Delete ---
export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/documents/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete');
}

// --- Search ---
export async function searchDocuments(
  q: string,
  mode: 'keyword' | 'semantic' = 'keyword',
  limit = 20
): Promise<{ query: string; mode: string; count: number; results: SearchResult[] }> {
  const params = new URLSearchParams({ q, mode, limit: String(limit) });
  const res = await fetch(`${API_BASE}/api/search?${params}`);
  if (!res.ok) throw new Error('Search failed');
  return res.json();
}
