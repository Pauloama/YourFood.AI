import AsyncStorage from '@react-native-async-storage/async-storage';
import type {
  AuthTokenResponse,
  MenuItem,
  Order,
  Review,
  ReviewAnnotationInput,
  Store,
  UserRole
} from '../types/models';

const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'http://10.0.2.2:5000';
const SESSION_KEY = 'yourfood_mobile_session';

function createKey(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

export async function loadSession(): Promise<AuthTokenResponse | null> {
  const raw = await AsyncStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthTokenResponse;
  } catch {
    return null;
  }
}

export async function persistSession(session: AuthTokenResponse | null): Promise<void> {
  if (!session) {
    await AsyncStorage.removeItem(SESSION_KEY);
    return;
  }
  await AsyncStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

async function request<T>(path: string, options: RequestInit = {}, idempotent = false): Promise<T> {
  const session = await loadSession();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Correlation-ID': createKey()
  };

  if (session?.accessToken) {
    headers.Authorization = `Bearer ${session.accessToken}`;
  }

  if (idempotent) {
    headers['Idempotency-Key'] = createKey();
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers, ...(options.headers as Record<string, string> | undefined) }
  });

  if (!response.ok) {
    const body = await response.text();
    try {
      const parsed = JSON.parse(body) as { message?: string };
      throw new Error(parsed.message || `HTTP ${response.status}`);
    } catch (err) {
      if (err instanceof Error && err.message) throw err;
      throw new Error(`HTTP ${response.status}`);
    }
  }

  return (await response.json()) as T;
}

export const mobileApi = {
  login: (email: string, password: string) =>
    request<AuthTokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    }),

  register: (fullName: string, email: string, password: string, role: UserRole) =>
    request<AuthTokenResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ fullName, email, password, role })
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

  listStores: () => request<Store[]>('/api/v1/stores'),
  getMyStores: () => request<Store[]>('/api/v1/stores/mine'),

  createStore: (payload: {
    name: string;
    category: string;
    description: string;
    address: string;
    deliveryFee: number;
    estimatedDeliveryMinutes: number;
  }) => request<Store>('/api/v1/stores', { method: 'POST', body: JSON.stringify(payload) }, true),

  addMenuItem: (storeId: string, payload: { name: string; description: string; category: string; price: number }) =>
    request<MenuItem>(`/api/v1/stores/${storeId}/items`, { method: 'POST', body: JSON.stringify(payload) }, true),

  createOrder: (payload: {
    storeId: string;
    deliveryAddress: string;
    notes?: string;
    items: Array<{ menuItemId: string; quantity: number }>;
  }) => request<Order>('/api/v1/orders', { method: 'POST', body: JSON.stringify(payload) }, true),

  getMyOrders: () => request<Order[]>('/api/v1/orders/my'),
  getMerchantOrders: () => request<Order[]>('/api/v1/orders/merchant'),

  transitionOrder: (orderId: string, nextStatus: string) =>
    request<Order>(`/api/v1/orders/${orderId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ nextStatus, reason: `Mobile transition: ${nextStatus}` })
    }),

  createReview: (payload: {
    orderId: string;
    text: string;
    rating: number;
    runInferenceImmediately: boolean;
    annotations?: ReviewAnnotationInput[];
  }) => request<Review>('/api/v1/reviews', { method: 'POST', body: JSON.stringify(payload) }, true)
};
