export type UserRole = 'Customer' | 'StoreOwner' | 'Admin';

export interface UserSummary {
  id: string;
  fullName: string;
  email: string;
  role: UserRole;
  oAuthProvider?: string | null;
}

export interface AuthTokenResponse {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresInSeconds: number;
  user: UserSummary;
}

export interface MenuItem {
  id: string;
  storeId: string;
  name: string;
  description: string;
  category: string;
  price: number;
  currencyCode: string;
  isAvailable: boolean;
}

export interface Store {
  id: string;
  ownerId: string;
  name: string;
  category: string;
  description: string;
  address: string;
  deliveryFee: number;
  estimatedDeliveryMinutes: number;
  isOpen: boolean;
  menuItems: MenuItem[];
}

export interface OrderItem {
  id: string;
  menuItemId: string;
  itemNameSnapshot: string;
  unitPriceSnapshot: number;
  quantity: number;
  lineTotal: number;
}

export interface OrderStateTransition {
  id: string;
  fromStatus?: string | null;
  toStatus: string;
  actorUserId: string;
  reason?: string | null;
  createdAtUtc: string;
}

export interface LedgerEntry {
  id: string;
  entryType: string;
  amount: number;
  currencyCode: string;
  description: string;
  createdAtUtc: string;
}

export interface Order {
  id: string;
  customerId: string;
  storeId: string;
  storeName: string;
  deliveryAddress: string;
  status: string;
  allowedNextStatuses: string[];
  subtotalAmount: number;
  deliveryFeeAmount: number;
  totalAmount: number;
  currencyCode: string;
  notes?: string | null;
  hasReview: boolean;
  createdAtUtc: string;
  items: OrderItem[];
  stateHistory: OrderStateTransition[];
  ledgerEntries: LedgerEntry[];
}

export interface ReviewAnnotationInput {
  aspect: string;
  sentiment: 'positivo' | 'negativo' | 'neutro';
  evidenceText?: string;
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
  annotations: ReviewAnnotation[];
  predictions: ReviewPrediction[];
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

export const ABSA_ASPECTS = [
  { code: 'sabor', entity: 'produto', label: 'Sabor' },
  { code: 'qualidade', entity: 'produto', label: 'Qualidade' },
  { code: 'quantidade', entity: 'produto', label: 'Quantidade' },
  { code: 'temperatura', entity: 'produto', label: 'Temperatura' },
  { code: 'aparencia', entity: 'produto', label: 'Aparência' },
  { code: 'preparo', entity: 'produto', label: 'Preparo' },
  { code: 'atendimento', entity: 'loja', label: 'Atendimento' },
  { code: 'pedido_correto', entity: 'loja', label: 'Pedido Correto' },
  { code: 'embalagem', entity: 'loja', label: 'Embalagem' },
  { code: 'custo_beneficio', entity: 'loja', label: 'Custo-Benefício' },
  { code: 'tempo_entrega', entity: 'entrega', label: 'Tempo de Entrega' },
  { code: 'condicao_entrega', entity: 'entrega', label: 'Condição da Entrega' }
] as const;

export const ORDER_STATUS_LABELS: Record<string, string> = {
  PendingPayment: 'Aguardando Pagamento',
  Confirmed: 'Confirmado',
  Preparing: 'Em Preparo',
  ReadyForPickup: 'Pronto p/ Retirada',
  OutForDelivery: 'Saiu p/ Entrega',
  Delivered: 'Entregue',
  Cancelled: 'Cancelado'
};

export const ORDER_FLOW_STEPS = [
  'PendingPayment',
  'Confirmed',
  'Preparing',
  'ReadyForPickup',
  'OutForDelivery',
  'Delivered'
];
