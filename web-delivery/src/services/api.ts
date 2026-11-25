import type {
  AuthTokenResponse,
  MenuItem,
  Order,
  PipelineAnalytics,
  Review,
  ReviewAnnotationInput,
  Store,
  UserRole
} from '../types/models';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';
const STORAGE_KEY = 'yourfood_delivery_session';

const ERROR_MESSAGES_PT: Record<string, string> = {
  INVALID_CREDENTIALS: 'E-mail ou senha incorretos. Verifique seus dados e tente novamente.',
  INVALID_REGISTRATION: 'Preencha nome completo, e-mail válido e senha com pelo menos 6 caracteres.',
  CONFLICT: 'Este registro já existe. Verifique os dados informados.',
  STORE_CLOSED: 'Este restaurante está fechado no momento.',
  EMPTY_ORDER: 'Adicione pelo menos um item à sacola antes de finalizar o pedido.',
  MISSING_DELIVERY_ADDRESS: 'Informe o endereço de entrega para continuar.',
  ORDER_NOT_DELIVERED: 'Só é possível avaliar pedidos que já foram entregues.',
  INVALID_STATE_TRANSITION: 'Esta mudança de status não é permitida para o estado atual do pedido.',
  INVALID_ASPECT: 'O aspecto selecionado não faz parte da taxonomia oficial.',
  INVALID_SENTIMENT: 'O sentimento selecionado é inválido.',
  EMPTY_REVIEW_TEXT: 'Escreva um breve comentário antes de enviar sua avaliação.',
  FORBIDDEN: 'Você não tem permissão para realizar esta ação.',
  IDEMPOTENCY_CONFLICT: 'Esta requisição já foi processada com dados diferentes.',
  INTERNAL_SERVER_ERROR: 'Ocorreu um erro interno no servidor. Tente novamente em instantes.'
};

function translateApiError(rawBody: string, status: number): string {
  try {
    const parsed = JSON.parse(rawBody) as { code?: string; message?: string; detail?: string };
    if (parsed.code && ERROR_MESSAGES_PT[parsed.code]) {
      return ERROR_MESSAGES_PT[parsed.code];
    }
    if (parsed.message?.toLowerCase().includes('already registered')) {
      return 'Este e-mail já está cadastrado. Tente fazer login.';
    }
    if (parsed.message?.toLowerCase().includes('already been submitted')) {
      return 'Você já enviou uma avaliação para este pedido.';
    }
    if (status === 401) {
      return 'Sua sessão expirou. Faça login novamente.';
    }
    if (status === 403) {
      return 'Você não tem permissão para acessar este recurso.';
    }
    if (status >= 500) {
      return 'Não foi possível completar a operação no momento. Tente novamente.';
    }
    return parsed.message || parsed.detail || 'Não foi possível processar sua solicitação.';
  } catch {
    if (status === 401) return 'Sua sessão expirou. Faça login novamente.';
    if (status >= 500) return 'Serviço temporariamente indisponível. Tente novamente em instantes.';
    return 'Não foi possível processar sua solicitação.';
  }
}

export function getStoredSession(): AuthTokenResponse | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthTokenResponse;
  } catch {
    return null;
  }
}

export function saveSession(session: AuthTokenResponse | null): void {
  if (!session) {
    localStorage.removeItem(STORAGE_KEY);
    return;
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

async function refreshAccessToken(refreshToken: string): Promise<AuthTokenResponse | null> {
  const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refreshToken })
  });
  if (!response.ok) return null;
  const refreshed = (await response.json()) as AuthTokenResponse;
  saveSession(refreshed);
  return refreshed;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  useIdempotency = false,
  retryOnUnauthorized = true
): Promise<T> {
  const session = getStoredSession();
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  headers.set('X-Correlation-ID', crypto.randomUUID());

  if (session?.accessToken) {
    headers.set('Authorization', `Bearer ${session.accessToken}`);
  }

  if (useIdempotency) {
    headers.set('Idempotency-Key', crypto.randomUUID());
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error('Sem conexão com o servidor. Verifique se o backend está ativo.');
  }

  if (response.status === 401 && retryOnUnauthorized && session?.refreshToken) {
    const refreshed = await refreshAccessToken(session.refreshToken);
    if (refreshed) {
      return request<T>(path, options, false, false);
    }
    saveSession(null);
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(translateApiError(text, response.status));
  }

  return (await response.json()) as T;
}

export const deliveryApi = {
  register: (fullName: string, email: string, password: string, role: UserRole) =>
    request<AuthTokenResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ fullName, email, password, role })
    }),

  login: (email: string, password: string) =>
    request<AuthTokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    }),

  oauthExternalLogin: (provider: string, email: string, fullName: string, preferredRole: UserRole) =>
    request<AuthTokenResponse>('/api/v1/auth/oauth2/external', {
      method: 'POST',
      body: JSON.stringify({
        provider,
        externalSubject: `${provider}-${email}`,
        email,
        fullName,
        preferredRole
      })
    }),

  listStores: (search?: string, category?: string) => {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (category) params.set('category', category);
    const qs = params.toString();
    return request<Store[]>(`/api/v1/stores${qs ? `?${qs}` : ''}`);
  },

  getMyStores: () => request<Store[]>('/api/v1/stores/mine'),

  createStore: (payload: {
    name: string;
    category: string;
    description: string;
    address: string;
    deliveryFee: number;
    estimatedDeliveryMinutes: number;
  }) =>
    request<Store>('/api/v1/stores', { method: 'POST', body: JSON.stringify(payload) }, true),

  addMenuItem: (
    storeId: string,
    payload: { name: string; description: string; category: string; price: number }
  ) =>
    request<MenuItem>(`/api/v1/stores/${storeId}/items`, { method: 'POST', body: JSON.stringify(payload) }, true),

  updateMenuItem: (
    menuItemId: string,
    payload: { name: string; description: string; category: string; price: number; isAvailable: boolean }
  ) =>
    request<MenuItem>(`/api/v1/stores/items/${menuItemId}`, { method: 'PUT', body: JSON.stringify(payload) }),

  createOrder: (payload: {
    storeId: string;
    deliveryAddress: string;
    notes?: string;
    items: Array<{ menuItemId: string; quantity: number }>;
  }) =>
    request<Order>('/api/v1/orders', { method: 'POST', body: JSON.stringify(payload) }, true),

  getMyOrders: () => request<Order[]>('/api/v1/orders/my'),

  getMerchantOrders: (storeId?: string) =>
    request<Order[]>(`/api/v1/orders/merchant${storeId ? `?storeId=${storeId}` : ''}`),

  transitionOrder: (orderId: string, nextStatus: string, reason?: string) =>
    request<Order>(`/api/v1/orders/${orderId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ nextStatus, reason })
    }),

  createReview: (payload: {
    orderId: string;
    text: string;
    rating: number;
    runInferenceImmediately: boolean;
    annotations?: ReviewAnnotationInput[];
  }) =>
    request<Review>('/api/v1/reviews', { method: 'POST', body: JSON.stringify(payload) }, true),

  listReviews: (storeId?: string) =>
    request<Review[]>(`/api/v1/reviews${storeId ? `?storeId=${storeId}` : ''}`),

  getStoreAnalytics: (storeId?: string) =>
    request<PipelineAnalytics>(`/api/v1/pipeline/analytics${storeId ? `?storeId=${storeId}` : ''}`)
};
