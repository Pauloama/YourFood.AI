export interface UserSummary {
  id: string;
  fullName: string;
  email: string;
  role: string;
}

export interface AuthTokenResponse {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresInSeconds: number;
  user: UserSummary;
}

export interface AbsaHealth {
  status: string;
  aspectModelLoaded: boolean;
  sentimentModelLoaded: boolean;
  serviceUrl: string;
}

export interface ReviewAnnotation {
  id: string;
  aspect: string;
  entity: string;
  sentiment: string;
  evidenceText?: string | null;
}

export interface ReviewPrediction {
  entity: string;
  aspect: string;
  aspectProbability: number;
  sentiment: string;
  sentimentProbability: number;
}

export interface Review {
  id: string;
  orderId: string;
  customerId: string;
  storeId: string;
  storeName: string;
  text: string;
  rating: number;
  requiresReview: boolean;
  isExportedToDataset: boolean;
  createdAtUtc: string;
  lastAnalyzedAtUtc?: string | null;
  aspectModelVersion?: string | null;
  sentimentModelVersion?: string | null;
  lastInferenceLatencyMs?: number | null;
  annotations: ReviewAnnotation[];
  predictions: ReviewPrediction[];
}

export interface AbsaAnalysisResponse {
  reviewId: string;
  text: string;
  aspects: ReviewPrediction[];
  modelVersions: Record<string, string>;
  processingTimeMs: number;
}

export interface DiagnosticSentimentResponse {
  text: string;
  aspect: string;
  entity: string;
  predictedSentiment: string;
  probability: number;
  probabilities: Record<string, number>;
}

export interface BatchInferenceSummary {
  processedCount: number;
  failedCount: number;
  totalLatencyMs: number;
  results: Review[];
}

export interface ExportDatasetResponse {
  totalReviews: number;
  totalRows: number;
  fileName: string;
  savedPath?: string | null;
  content: string;
}

export type PipelineStepType =
  | 'ExportDataset'
  | 'ValidateDataset'
  | 'PrepareDataset'
  | 'SplitDataset'
  | 'FullDataPreparation'
  | 'TrainAspectDetector'
  | 'TrainSentimentClassifier'
  | 'EvaluatePipeline'
  | 'ExportModels';

export interface PipelineJob {
  id: string;
  step: string;
  status: string;
  triggeredByUserId: string;
  commandExecuted: string;
  outputLog: string;
  errorLog: string;
  exitCode?: number | null;
  createdAtUtc: string;
  startedAtUtc?: string | null;
  completedAtUtc?: string | null;
  reportJson?: string | null;
}

export interface PipelineAnalytics {
  totalStores: number;
  totalOrders: number;
  deliveredOrders: number;
  totalReviews: number;
  annotatedReviews: number;
  analyzedReviews: number;
  flaggedReviews: number;
  averageRating: number;
  aspectBreakdown: Array<{
    aspect: string;
    entity: string;
    positive: number;
    negative: number;
    neutral: number;
    total: number;
  }>;
  entityBreakdown: Array<{
    entity: string;
    positive: number;
    negative: number;
    neutral: number;
    total: number;
  }>;
}

export interface AuditLog {
  id: string;
  actorUserId?: string | null;
  action: string;
  entityType: string;
  entityId: string;
  correlationId: string;
  payloadHash: string;
  summary: string;
  createdAtUtc: string;
}

export const TAXONOMY_ASPECTS = [
  'sabor',
  'qualidade',
  'quantidade',
  'temperatura',
  'aparencia',
  'preparo',
  'atendimento',
  'pedido_correto',
  'embalagem',
  'custo_beneficio',
  'tempo_entrega',
  'condicao_entrega'
] as const;

export const PIPELINE_STEPS: Array<{ step: PipelineStepType; label: string; description: string }> = [
  { step: 'ExportDataset', label: '1. Exportar Dataset PostgreSQL', description: 'Exporta avaliações coletadas do delivery para data/raw/delivery_reviews.jsonl' },
  { step: 'ValidateDataset', label: '2. Validar Dataset', description: 'Executa scripts/validate_dataset.py e gera validation_report.json' },
  { step: 'PrepareDataset', label: '3. Preparar e Normalizar', description: 'Executa scripts/prepare_dataset.py separando conflitos' },
  { step: 'SplitDataset', label: '4. Dividir Treino/Val/Teste', description: 'Executa scripts/split_dataset.py sem vazamento de review_id' },
  { step: 'FullDataPreparation', label: 'Pipeline de Dados Completo', description: 'Executa Validate -> Prepare -> Split em sequência' },
  { step: 'TrainAspectDetector', label: '5. Treinar Detector (Modelo 1)', description: 'Fine-tuning BERTimbau multirrótulo + calibração de thresholds' },
  { step: 'TrainSentimentClassifier', label: '6. Treinar Sentimento (Modelo 2)', description: 'Fine-tuning BERTimbau por pares [texto, aspecto]' },
  { step: 'EvaluatePipeline', label: '7. Avaliar Pipeline Integrado', description: 'Executa scripts/evaluate_pipeline.py no conjunto de teste' },
  { step: 'ExportModels', label: '8. Exportar Artefatos Versionados', description: 'Empacota pesos, tokenizers, thresholds e metadados' }
];
