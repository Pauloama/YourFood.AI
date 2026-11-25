import type {
  AbsaAnalysisResponse,
  AbsaHealth,
  AuditLog,
  AuthTokenResponse,
  BatchInferenceSummary,
  DiagnosticSentimentResponse,
  ExportDatasetResponse,
  PipelineAnalytics,
  PipelineJob,
  PipelineStepType,
  Review
} from '../types/models';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';
const SESSION_KEY = 'yourfood_mlops_session';

function translateConsoleError(raw: string, status: number): string {
  try {
    const parsed = JSON.parse(raw) as { code?: string; message?: string; detail?: string };
    const text = `${parsed.message ?? ''} ${parsed.detail ?? ''}`.toLowerCase();

    if (status === 503 || text.includes('models are not currently loaded') || text.includes('503')) {
      return 'Os modelos BERTimbau ainda não estão carregados na API de inferência. Treine/exporte os artefatos para bertimbau-absa/artifacts/ e reinicie o serviço absa-api.';
    }
    if (parsed.code === 'INVALID_CREDENTIALS') {
      return 'E-mail ou senha inválidos. Use as credenciais de Administrador MLOps.';
    }
    if (status === 401) {
      return 'Sessão expirada. Faça login novamente.';
    }
    if (status === 403) {
      return 'Acesso restrito a contas com perfil Administrador MLOps.';
    }
    if (status === 422 || parsed.code === 'INVALID_ASPECT') {
      return 'Parâmetros inválidos. Verifique se o texto não está vazio e se o aspecto pertence à taxonomia oficial.';
    }
    if (status >= 500) {
      return 'Erro interno ao processar a solicitação. Verifique os logs do serviço.';
    }
    return parsed.message || parsed.detail || 'Não foi possível concluir a operação.';
  } catch {
    if (status === 503) {
      return 'Os modelos BERTimbau ainda não estão carregados na API de inferência.';
    }
    return 'Não foi possível concluir a operação no servidor.';
  }
}

export function getStoredSession(): AuthTokenResponse | null {
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthTokenResponse;
  } catch {
    return null;
  }
}

export function saveSession(session: AuthTokenResponse | null): void {
  if (!session) {
    localStorage.removeItem(SESSION_KEY);
    return;
  }
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const session = getStoredSession();
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  headers.set('X-Correlation-ID', crypto.randomUUID());

  if (session?.accessToken) {
    headers.set('Authorization', `Bearer ${session.accessToken}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error('Sem conexão com o backend. Verifique se o container backend-api está ativo.');
  }

  if (!response.ok) {
    const raw = await response.text();
    throw new Error(translateConsoleError(raw, response.status));
  }

  return (await response.json()) as T;
}

export const consoleApi = {
  login: (email: string, password: string) =>
    request<AuthTokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    }),

  getHealth: () => request<AbsaHealth>('/api/v1/pipeline/health'),
  getAnalytics: () => request<PipelineAnalytics>('/api/v1/pipeline/analytics'),
  getJobs: () => request<PipelineJob[]>('/api/v1/pipeline/jobs?limit=30'),
  getAuditLogs: () => request<AuditLog[]>('/api/v1/pipeline/audit-logs?limit=50'),
  listReviews: () => request<Review[]>('/api/v1/reviews'),

  exportDataset: (format: 'jsonl' | 'csv', includeUnannotated: boolean, excludeFlagged: boolean) =>
    request<ExportDatasetResponse>('/api/v1/pipeline/export', {
      method: 'POST',
      body: JSON.stringify({
        format,
        includeUnannotated,
        excludeFlagged,
        saveToPipelineRawDir: true
      })
    }),

  triggerJob: (step: PipelineStepType, datasetFileName: string, seed: number) =>
    request<PipelineJob>('/api/v1/pipeline/jobs', {
      method: 'POST',
      body: JSON.stringify({ step, datasetFileName, seed })
    }),

  analyzeText: (text: string, reviewId?: string) =>
    request<AbsaAnalysisResponse>('/api/v1/pipeline/inference/analyze', {
      method: 'POST',
      body: JSON.stringify({ reviewId: reviewId || undefined, text })
    }),

  classifySentiment: (text: string, aspect: string) =>
    request<DiagnosticSentimentResponse>('/api/v1/pipeline/inference/classify-sentiment', {
      method: 'POST',
      body: JSON.stringify({ text, aspect })
    }),

  analyzeSingleReview: (reviewId: string) =>
    request<Review>(`/api/v1/reviews/${reviewId}/analyze`, { method: 'POST' }),

  analyzePendingBatch: (maxCount = 32) =>
    request<BatchInferenceSummary>('/api/v1/reviews/analyze-batch', {
      method: 'POST',
      body: JSON.stringify({ maxCount })
    }),

  updateAnnotations: (
    reviewId: string,
    annotations: Array<{ aspect: string; sentiment: string; evidenceText?: string }>,
    requiresReview: boolean
  ) =>
    request<Review>(`/api/v1/reviews/${reviewId}/annotations`, {
      method: 'PUT',
      body: JSON.stringify({ annotations, requiresReview })
    })
};
