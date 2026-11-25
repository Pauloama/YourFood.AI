import { useEffect, useState, type FormEvent } from 'react';
import {
  Activity,
  Cpu,
  Database,
  Download,
  FileCode2,
  LogOut,
  Play,
  RefreshCw,
  Shield,
  Sparkles
} from 'lucide-react';
import { consoleApi, getStoredSession, saveSession } from './services/api';
import {
  PIPELINE_STEPS,
  TAXONOMY_ASPECTS,
  type AbsaAnalysisResponse,
  type AbsaHealth,
  type AuditLog,
  type AuthTokenResponse,
  type DiagnosticSentimentResponse,
  type PipelineAnalytics,
  type PipelineJob,
  type PipelineStepType,
  type Review
} from './types/models';

const JOB_STATUS_LABELS: Record<string, string> = {
  Queued: 'Na fila',
  Running: 'Em execução',
  Succeeded: 'Concluído',
  Failed: 'Falhou'
};

const STEP_LABELS: Record<string, string> = {
  ExportDataset: 'Exportar Dataset',
  ValidateDataset: 'Validar Dataset',
  PrepareDataset: 'Preparar Dataset',
  SplitDataset: 'Dividir Partições',
  FullDataPreparation: 'Preparação Completa',
  TrainAspectDetector: 'Treinar Detector (M1)',
  TrainSentimentClassifier: 'Treinar Sentimento (M2)',
  EvaluatePipeline: 'Avaliar Pipeline',
  ExportModels: 'Exportar Modelos'
};

const AUDIT_ACTION_LABELS: Record<string, string> = {
  USER_REGISTERED: 'Conta criada',
  USER_LOGIN: 'Login JWT',
  OAUTH2_AUTHORIZE: 'Autorização OAuth2',
  OAUTH2_TOKEN_EXCHANGE: 'Troca de token OAuth2',
  OAUTH2_EXTERNAL_LOGIN: 'Login OAuth2 externo',
  STORE_CREATED: 'Loja criada',
  STORE_UPDATED: 'Loja atualizada',
  MENU_ITEM_CREATED: 'Item criado',
  MENU_ITEM_UPDATED: 'Item atualizado',
  ORDER_CREATED: 'Pedido criado',
  ORDER_STATE_TRANSITION: 'Mudança de status',
  REVIEW_CREATED: 'Avaliação coletada',
  REVIEW_ANNOTATED: 'Anotação atualizada',
  REVIEW_INFERENCE_RUN: 'Inferência individual',
  BATCH_INFERENCE_RUN: 'Inferência em lote',
  DATASET_EXPORTED: 'Dataset exportado',
  PIPELINE_STEP_EXECUTED: 'Etapa executada'
};

function SentimentRatioBar({
  positive,
  neutral,
  negative,
  total
}: {
  positive: number;
  neutral: number;
  negative: number;
  total: number;
}) {
  if (total <= 0) {
    return <div className="sentiment-bar" />;
  }
  const posW = (positive / total) * 100;
  const neuW = (neutral / total) * 100;
  const negW = (negative / total) * 100;

  return (
    <div className="sentiment-bar">
      {posW > 0 && <div className="seg-pos" style={{ width: `${posW}%` }} />}
      {neuW > 0 && <div className="seg-neu" style={{ width: `${neuW}%` }} />}
      {negW > 0 && <div className="seg-neg" style={{ width: `${negW}%` }} />}
    </div>
  );
}

export function App() {
  const [session, setSession] = useState<AuthTokenResponse | null>(() => getStoredSession());
  const [email, setEmail] = useState('admin@yourfood.ai');
  const [password, setPassword] = useState('Admin@123');
  const [authError, setAuthError] = useState<string | null>(null);

  const [tab, setTab] = useState<'overview' | 'pipeline' | 'inference' | 'dataset'>('overview');
  const [health, setHealth] = useState<AbsaHealth | null>(null);
  const [analytics, setAnalytics] = useState<PipelineAnalytics | null>(null);
  const [jobs, setJobs] = useState<PipelineJob[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [selectedJob, setSelectedJob] = useState<PipelineJob | null>(null);

  const [datasetFile, setDatasetFile] = useState('delivery_reviews.jsonl');
  const [seed, setSeed] = useState(42);
  const [runningStep, setRunningStep] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

  const [inferenceText, setInferenceText] = useState(
    'A pizza estava deliciosa e quentinha, mas a entrega atrasou e a embalagem veio amassada.'
  );
  const [inferenceResult, setInferenceResult] = useState<AbsaAnalysisResponse | null>(null);

  const [diagText, setDiagText] = useState('O hambúrguer estava bom, mas chegou frio.');
  const [diagAspect, setDiagAspect] = useState<string>('temperatura');
  const [diagResult, setDiagResult] = useState<DiagnosticSentimentResponse | null>(null);

  const [editingReviewId, setEditingReviewId] = useState<string | null>(null);
  const [editAspect, setEditAspect] = useState<string>('sabor');
  const [editSentiment, setEditSentiment] = useState<'positivo' | 'negativo' | 'neutro'>('positivo');

  const refreshAll = async () => {
    if (!session) return;
    try {
      const [h, a, j, r, l] = await Promise.all([
        consoleApi.getHealth(),
        consoleApi.getAnalytics(),
        consoleApi.getJobs(),
        consoleApi.listReviews(),
        consoleApi.getAuditLogs()
      ]);
      setHealth(h);
      setAnalytics(a);
      setJobs(j);
      setReviews(r);
      setAuditLogs(l);
      if (!selectedJob && j.length > 0) setSelectedJob(j[0]);
    } catch (err) {
      setBanner({ type: 'err', text: err instanceof Error ? err.message : 'Não foi possível atualizar os dados.' });
    }
  };

  useEffect(() => {
    refreshAll();
  }, [session]);

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    try {
      const res = await consoleApi.login(email, password);
      if (res.user.role !== 'Admin') {
        throw new Error('Este console é exclusivo para contas Administrador MLOps.');
      }
      saveSession(res);
      setSession(res);
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Não foi possível autenticar.');
    }
  };

  const handleLogout = () => {
    saveSession(null);
    setSession(null);
  };

  const handleRunStep = async (step: PipelineStepType) => {
    setRunningStep(step);
    setBanner(null);
    try {
      const job = await consoleApi.triggerJob(step, datasetFile, seed);
      setSelectedJob(job);
      const label = STEP_LABELS[step] || step;
      setBanner({
        type: job.status === 'Succeeded' ? 'ok' : 'err',
        text:
          job.status === 'Succeeded'
            ? `Etapa "${label}" concluída com sucesso! Veja os detalhes nos logs abaixo.`
            : `Etapa "${label}" falhou (código ${job.exitCode ?? 'N/A'}). Verifique os logs de erro abaixo.`
      });
      await refreshAll();
    } catch (err) {
      setBanner({ type: 'err', text: err instanceof Error ? err.message : 'Erro ao executar etapa do pipeline.' });
    } finally {
      setRunningStep(null);
    }
  };

  const handleDownloadExport = async (format: 'jsonl' | 'csv') => {
    setBanner(null);
    try {
      const exported = await consoleApi.exportDataset(format, true, true);
      const blob = new Blob([exported.content], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = exported.fileName;
      a.click();
      URL.revokeObjectURL(url);
      setBanner({
        type: 'ok',
        text: `Dataset exportado com ${exported.totalReviews} avaliações (${exported.totalRows} linhas) e salvo no diretório do pipeline.`
      });
      await refreshAll();
    } catch (err) {
      setBanner({ type: 'err', text: err instanceof Error ? err.message : 'Não foi possível exportar o dataset.' });
    }
  };

  const handleSingleInference = async () => {
    setBanner(null);
    try {
      const res = await consoleApi.analyzeText(inferenceText);
      setInferenceResult(res);
    } catch (err) {
      setBanner({ type: 'err', text: err instanceof Error ? err.message : 'Não foi possível executar a inferência.' });
    }
  };

  const handleDiagnostic = async () => {
    setBanner(null);
    try {
      const res = await consoleApi.classifySentiment(diagText, diagAspect);
      setDiagResult(res);
    } catch (err) {
      setBanner({ type: 'err', text: err instanceof Error ? err.message : 'Não foi possível executar o diagnóstico.' });
    }
  };

  const handleBatchInference = async () => {
    setBanner(null);
    try {
      const summary = await consoleApi.analyzePendingBatch(32);
      setBanner({
        type: summary.failedCount === 0 ? 'ok' : 'err',
        text:
          summary.processedCount === 0 && summary.failedCount === 0
            ? 'Todas as avaliações coletadas já possuem inferência registrada.'
            : `Lote finalizado: ${summary.processedCount} avaliação(ões) analisada(s), ${summary.failedCount} falha(s) (${summary.totalLatencyMs} ms).`
      });
      await refreshAll();
    } catch (err) {
      setBanner({ type: 'err', text: err instanceof Error ? err.message : 'Não foi possível rodar a inferência em lote.' });
    }
  };

  const handleAppendAnnotation = async (review: Review) => {
    try {
      const next = [
        ...review.annotations.map((a) => ({
          aspect: a.aspect,
          sentiment: a.sentiment,
          evidenceText: a.evidenceText || undefined
        })),
        { aspect: editAspect, sentiment: editSentiment }
      ];
      await consoleApi.updateAnnotations(review.id, next, false);
      setEditingReviewId(null);
      setBanner({ type: 'ok', text: `Anotação salva para a avaliação #${review.id.slice(0, 8)}.` });
      await refreshAll();
    } catch (err) {
      setBanner({ type: 'err', text: err instanceof Error ? err.message : 'Não foi possível salvar a anotação.' });
    }
  };

  if (!session) {
    return (
      <div className="auth-wrapper">
        <form className="card stack" style={{ width: '100%', maxWidth: 430, boxShadow: 'var(--shadow-md)' }} onSubmit={handleLogin}>
          <div className="row">
            <div className="brand-mark">
              <Cpu size={20} />
            </div>
            <div>
              <h2>YourFood.AI MLOps Studio</h2>
              <p className="muted">Orquestração BERTimbau ABSA & Inferência</p>
            </div>
          </div>
          {authError && <div className="error-box">{authError}</div>}
          <div>
            <label className="muted">E-mail de Administrador</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="muted">Senha</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <button type="submit" className="btn-primary" style={{ padding: '0.78rem' }}>
            Acessar Console MLOps
          </button>
        </form>
      </div>
    );
  }

  return (
    <div>
      <header className="topbar">
        <div className="row">
          <div className="brand-mark">
            <Cpu size={19} />
          </div>
          <strong style={{ fontSize: '1.02rem', fontFamily: 'Plus Jakarta Sans' }}>
            YourFood.AI · MLOps Studio
          </strong>
        </div>
        <div className="row">
          <span className={`badge ${health?.status === 'ok' ? 'badge-ok' : 'badge-err'}`}>
            <Activity size={13} /> API ML: {health?.status === 'ok' ? 'Online' : 'Offline'}
          </span>
          <button className="btn-topbar" onClick={refreshAll}>
            <RefreshCw size={14} /> Atualizar
          </button>
          <button className="btn-topbar" onClick={handleLogout}>
            <LogOut size={14} /> Sair
          </button>
        </div>
      </header>

      <main className="container">
        <div className="tabs">
          <button className={`tab-btn ${tab === 'overview' ? 'active' : ''}`} onClick={() => setTab('overview')}>
            Visão Geral
          </button>
          <button className={`tab-btn ${tab === 'pipeline' ? 'active' : ''}`} onClick={() => setTab('pipeline')}>
            Pipeline ({jobs.length})
          </button>
          <button className={`tab-btn ${tab === 'inference' ? 'active' : ''}`} onClick={() => setTab('inference')}>
            Inferência
          </button>
          <button className={`tab-btn ${tab === 'dataset' ? 'active' : ''}`} onClick={() => setTab('dataset')}>
            Dataset & Auditoria ({reviews.length})
          </button>
        </div>

        {banner && (
          <div className={banner.type === 'ok' ? 'success-box' : 'error-box'} style={{ marginBottom: '1rem' }}>
            {banner.text}
          </div>
        )}

        {tab === 'overview' && (
          <div className="stack">
            <div className="grid-4">
              <div className="card">
                <p className="muted">Avaliações Coletadas</p>
                <div className="kpi-num" style={{ color: 'var(--accent)' }}>
                  {analytics?.totalReviews ?? 0}
                </div>
                <span className="muted">{analytics?.annotatedReviews ?? 0} anotadas</span>
              </div>
              <div className="card">
                <p className="muted">Inferências Salvas</p>
                <div className="kpi-num" style={{ color: 'var(--success)' }}>
                  {analytics?.analyzedReviews ?? 0}
                </div>
                <span className="muted">{analytics?.flaggedReviews ?? 0} aguardando revisão</span>
              </div>
              <div className="card">
                <p className="muted">Pedidos Entregues</p>
                <div className="kpi-num">{analytics?.deliveredOrders ?? 0}</div>
                <span className="muted">de {analytics?.totalOrders ?? 0} pedidos</span>
              </div>
              <div className="card">
                <p className="muted">Modelos BERTimbau</p>
                <div className="row" style={{ marginTop: '0.55rem' }}>
                  <span className={`badge ${health?.aspectModelLoaded ? 'badge-ok' : 'badge-warn'}`}>
                    Detector: {health?.aspectModelLoaded ? 'Carregado' : 'Pendente'}
                  </span>
                  <span className={`badge ${health?.sentimentModelLoaded ? 'badge-ok' : 'badge-warn'}`}>
                    Sentimento: {health?.sentimentModelLoaded ? 'Carregado' : 'Pendente'}
                  </span>
                </div>
              </div>
            </div>

            {analytics && (
              <div className="grid-2">
                <div className="card stack">
                  <h3>Sentimento por Entidade de Negócio</h3>
                  {analytics.entityBreakdown.map((e) => (
                    <div key={e.entity} style={{ padding: '0.85rem', background: 'var(--surface-alt)', borderRadius: 12, border: '1px solid var(--border)' }}>
                      <div className="row-between">
                        <strong style={{ textTransform: 'capitalize' }}>{e.entity}</strong>
                        <div className="row">
                          <span className="badge badge-ok">+{e.positive}</span>
                          <span className="badge badge-warn">~{e.neutral}</span>
                          <span className="badge badge-err">-{e.negative}</span>
                        </div>
                      </div>
                      <SentimentRatioBar positive={e.positive} neutral={e.neutral} negative={e.negative} total={e.total} />
                    </div>
                  ))}
                </div>

                <div className="card stack">
                  <h3>Cobertura da Taxonomia (12 Aspectos)</h3>
                  <div className="grid-3">
                    {analytics.aspectBreakdown.map((a) => (
                      <div key={a.aspect} style={{ padding: '0.75rem', background: 'var(--surface-alt)', borderRadius: 12, border: '1px solid var(--border)' }}>
                        <div className="row-between">
                          <strong style={{ fontSize: '0.86rem' }}>{a.aspect}</strong>
                          <span className="badge badge-info">{a.total}</span>
                        </div>
                        <SentimentRatioBar positive={a.positive} neutral={a.neutral} negative={a.negative} total={a.total} />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'pipeline' && (
          <div className="stack">
            <div className="card pipeline-toolbar">
              <div>
                <label className="muted">Arquivo de entrada em data/raw/</label>
                <input value={datasetFile} onChange={(e) => setDatasetFile(e.target.value)} />
              </div>
              <div>
                <label className="muted">Seed</label>
                <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
              </div>
              <div className="row">
                <button className="btn-secondary" onClick={() => handleDownloadExport('jsonl')}>
                  <Download size={14} /> Baixar .jsonl
                </button>
                <button className="btn-secondary" onClick={() => handleDownloadExport('csv')}>
                  <Download size={14} /> Baixar .csv
                </button>
              </div>
            </div>

            <div className="grid-3">
              {PIPELINE_STEPS.map((item) => (
                <div key={item.step} className="card step-card stack">
                  <strong>{item.label}</strong>
                  <p className="muted">{item.description}</p>
                  <button
                    className="btn-primary"
                    style={{ marginTop: 'auto' }}
                    disabled={runningStep !== null}
                    onClick={() => handleRunStep(item.step)}
                  >
                    <Play size={14} /> {runningStep === item.step ? 'Executando...' : 'Executar Etapa'}
                  </button>
                </div>
              ))}
            </div>

            <div className="grid-2" style={{ alignItems: 'start' }}>
              <div className="card stack">
                <h3>Histórico de Execuções</h3>
                {jobs.length === 0 ? (
                  <p className="muted">Nenhuma etapa executada ainda. Clique em qualquer cartão acima para iniciar.</p>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Etapa</th>
                          <th>Status</th>
                          <th>Código</th>
                          <th>Horário</th>
                        </tr>
                      </thead>
                      <tbody>
                        {jobs.map((job) => (
                          <tr
                            key={job.id}
                            style={{ cursor: 'pointer', background: selectedJob?.id === job.id ? 'var(--accent-soft)' : undefined }}
                            onClick={() => setSelectedJob(job)}
                          >
                            <td>
                              <strong>{STEP_LABELS[job.step] || job.step}</strong>
                            </td>
                            <td>
                              <span className={`badge ${job.status === 'Succeeded' ? 'badge-ok' : job.status === 'Failed' ? 'badge-err' : 'badge-warn'}`}>
                                {JOB_STATUS_LABELS[job.status] || job.status}
                              </span>
                            </td>
                            <td>{job.exitCode ?? '-'}</td>
                            <td className="muted">{new Date(job.createdAtUtc).toLocaleTimeString('pt-BR')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="card stack">
                <div className="row">
                  <FileCode2 size={18} color="#4f46e5" />
                  <h3>Logs & Relatório da Execução</h3>
                </div>
                {selectedJob ? (
                  <>
                    <div className="badge badge-info" style={{ width: 'fit-content' }}>
                      {selectedJob.commandExecuted}
                    </div>
                    <div>
                      <strong>Saída padrão (stdout)</strong>
                      <pre className="log-box">{selectedJob.outputLog || '(nenhuma saída registrada)'}</pre>
                    </div>
                    {selectedJob.errorLog && (
                      <div>
                        <strong>Erros (stderr)</strong>
                        <pre className="log-box" style={{ color: '#fca5a5' }}>
                          {selectedJob.errorLog}
                        </pre>
                      </div>
                    )}
                    {selectedJob.reportJson && (
                      <div>
                        <strong>Relatório JSON Gerado</strong>
                        <pre className="log-box">{selectedJob.reportJson}</pre>
                      </div>
                    )}
                  </>
                ) : (
                  <p className="muted">Selecione uma execução na tabela ao lado para inspecionar logs e relatórios.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {tab === 'inference' && (
          <div className="stack">
            {health && (!health.aspectModelLoaded || !health.sentimentModelLoaded) && (
              <div className="error-box">
                Os modelos treinados ainda não foram carregados na API FastAPI (`bertimbau-absa/artifacts/`). Execute o treinamento para habilitar previsões em tempo real.
              </div>
            )}

            <div className="card row-between" style={{ background: 'linear-gradient(135deg, #eef2ff 0%, #ecfeff 100%)', borderColor: '#c7d2fe' }}>
              <div>
                <h3>Inferência em Lote sobre Avaliações Pendentes</h3>
                <p className="muted">
                  Analisa avaliações coletadas do Delivery ainda sem predição e persiste o resultado estruturado no banco.
                </p>
              </div>
              <button className="btn-success" onClick={handleBatchInference}>
                <Sparkles size={15} /> Rodar Lote no BERTimbau
              </button>
            </div>

            <div className="grid-2" style={{ alignItems: 'start' }}>
              <div className="card stack">
                <h3>Inferência Completa (Modelo 1 + Modelo 2)</h3>
                <textarea rows={4} value={inferenceText} onChange={(e) => setInferenceText(e.target.value)} />
                <button className="btn-primary" onClick={handleSingleInference}>
                  <Sparkles size={15} /> Analisar Texto
                </button>

                {inferenceResult && (
                  <div className="stack">
                    <div className="row-between muted">
                      <span>Tempo de resposta: {inferenceResult.processingTimeMs} ms</span>
                      <span>Aspectos encontrados: {inferenceResult.aspects.length}</span>
                    </div>
                    {inferenceResult.aspects.length === 0 ? (
                      <span className="badge badge-warn">Nenhum aspecto atingiu o limite de confiança</span>
                    ) : (
                      inferenceResult.aspects.map((a, idx) => (
                        <div key={`${a.aspect}-${idx}`} style={{ padding: '0.8rem', background: 'var(--surface-alt)', borderRadius: 12, border: '1px solid var(--border)' }}>
                          <div className="row-between">
                            <strong>
                              {a.entity} / {a.aspect}
                            </strong>
                            <span className={`badge ${a.sentiment === 'positivo' ? 'badge-ok' : a.sentiment === 'negativo' ? 'badge-err' : 'badge-warn'}`}>
                              {a.sentiment} ({(a.sentimentProbability * 100).toFixed(1)}%)
                            </span>
                          </div>
                          <div className="muted" style={{ fontSize: '0.78rem', marginTop: '0.25rem' }}>
                            Confiança na detecção do aspecto: {(a.aspectProbability * 100).toFixed(1)}%
                          </div>
                          <div className="confidence-track">
                            <div className="confidence-fill" style={{ width: `${Math.round(a.aspectProbability * 100)}%` }} />
                          </div>
                        </div>
                      ))
                    )}
                    <pre className="log-box">{JSON.stringify(inferenceResult.modelVersions, null, 2)}</pre>
                  </div>
                )}
              </div>

              <div className="card stack">
                <h3>Diagnóstico Isolado do Modelo 2 (Sentimento por Aspecto)</h3>
                <textarea rows={3} value={diagText} onChange={(e) => setDiagText(e.target.value)} />
                <select value={diagAspect} onChange={(e) => setDiagAspect(e.target.value)}>
                  {TAXONOMY_ASPECTS.map((asp) => (
                    <option key={asp} value={asp}>
                      {asp}
                    </option>
                  ))}
                </select>
                <button className="btn-primary" onClick={handleDiagnostic}>
                  Classificar Sentimento
                </button>

                {diagResult && (
                  <div className="stack">
                    <div className="row-between">
                      <strong>
                        {diagResult.entity} : {diagResult.aspect}
                      </strong>
                      <span className={`badge ${diagResult.predictedSentiment === 'positivo' ? 'badge-ok' : diagResult.predictedSentiment === 'negativo' ? 'badge-err' : 'badge-warn'}`}>
                        {diagResult.predictedSentiment} ({(diagResult.probability * 100).toFixed(1)}%)
                      </span>
                    </div>
                    <pre className="log-box">{JSON.stringify(diagResult.probabilities, null, 2)}</pre>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {tab === 'dataset' && (
          <div className="stack">
            <div className="card stack">
              <div className="row">
                <Database size={18} color="#4f46e5" />
                <h3>Avaliações Coletadas do Delivery</h3>
              </div>
              {reviews.length === 0 ? (
                <p className="muted">Nenhuma avaliação coletada ainda. Avalie um pedido entregue no app de delivery.</p>
              ) : (
                reviews.map((r) => (
                  <div key={r.id} style={{ padding: '1rem', background: 'var(--surface-alt)', borderRadius: 12, border: '1px solid var(--border)' }} className="stack">
                    <div className="row-between">
                      <strong>
                        {r.storeName} · Nota {r.rating}/5
                      </strong>
                      <div className="row">
                        {r.requiresReview && <span className="badge badge-err">Revisão necessária</span>}
                        {r.isExportedToDataset && <span className="badge badge-info">Exportada</span>}
                        <button
                          className="btn-secondary"
                          onClick={async () => {
                            try {
                              await consoleApi.analyzeSingleReview(r.id);
                              setBanner({ type: 'ok', text: 'Inferência executada e salva para a avaliação.' });
                              await refreshAll();
                            } catch (err) {
                              setBanner({ type: 'err', text: err instanceof Error ? err.message : 'Erro na inferência.' });
                            }
                          }}
                        >
                          Analisar com IA
                        </button>
                        <button
                          className="btn-secondary"
                          onClick={() => setEditingReviewId(editingReviewId === r.id ? null : r.id)}
                        >
                          + Anotar
                        </button>
                      </div>
                    </div>
                    <p>"{r.text}"</p>
                    <div className="row">
                      {r.annotations.map((ann) => (
                        <span key={ann.id} className="badge badge-info">
                          Anotação: {ann.aspect} ({ann.sentiment})
                        </span>
                      ))}
                      {r.predictions.map((pred, idx) => (
                        <span key={`${pred.aspect}-${idx}`} className="badge badge-ok">
                          Predição IA: {pred.aspect} → {pred.sentiment} ({Math.round(pred.sentimentProbability * 100)}%)
                        </span>
                      ))}
                    </div>
                    {editingReviewId === r.id && (
                      <div className="inline-form-row">
                        <select value={editAspect} onChange={(e) => setEditAspect(e.target.value)}>
                          {TAXONOMY_ASPECTS.map((asp) => (
                            <option key={asp} value={asp}>
                              {asp}
                            </option>
                          ))}
                        </select>
                        <select
                          value={editSentiment}
                          onChange={(e) => setEditSentiment(e.target.value as 'positivo' | 'negativo' | 'neutro')}
                        >
                          <option value="positivo">Positivo</option>
                          <option value="negativo">Negativo</option>
                          <option value="neutro">Neutro</option>
                        </select>
                        <button className="btn-primary" onClick={() => handleAppendAnnotation(r)}>
                          Salvar Anotação
                        </button>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            <div className="card stack">
              <div className="row">
                <Shield size={18} color="#10b981" />
                <h3>Trilha de Auditoria (Hash SHA-256)</h3>
              </div>
              {auditLogs.length === 0 ? (
                <p className="muted">Nenhum evento de auditoria registrado até o momento.</p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Evento</th>
                        <th>Entidade</th>
                        <th>Resumo</th>
                        <th>Correlação</th>
                        <th>Hash</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditLogs.map((log) => (
                        <tr key={log.id}>
                          <td>
                            <span className="badge badge-info">{AUDIT_ACTION_LABELS[log.action] || log.action}</span>
                          </td>
                          <td>{log.entityType}</td>
                          <td>{log.summary}</td>
                          <td className="muted">{log.correlationId.slice(0, 10)}</td>
                          <td className="muted">{log.payloadHash.slice(0, 14)}...</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
