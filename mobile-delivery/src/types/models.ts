export type UserRole = 'Customer' | 'StoreOwner' | 'Admin';

export interface UserSummary {
  id: string;
  fullName: string;
  email: string;
  role: UserRole;
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

export interface Order {
  id: string;
  storeId: string;
  storeName: string;
  deliveryAddress: string;
  status: string;
  allowedNextStatuses: string[];
  subtotalAmount: number;
  deliveryFeeAmount: number;
  totalAmount: number;
  hasReview: boolean;
  createdAtUtc: string;
  items: OrderItem[];
}

export interface ReviewAnnotationInput {
  aspect: string;
  sentiment: 'positivo' | 'negativo' | 'neutro';
  evidenceText?: string;
}

export interface Review {
  id: string;
  orderId: string;
  storeName: string;
  text: string;
  rating: number;
  predictions: Array<{
    entity: string;
    aspect: string;
    aspectProbability: number;
    sentiment: string;
    sentimentProbability: number;
  }>;
}

export const ABSA_ASPECTS = [
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

export const ORDER_STATUS_PT: Record<string, string> = {
  PendingPayment: 'Aguardando Pagamento',
  Confirmed: 'Confirmado',
  Preparing: 'Em Preparo',
  ReadyForPickup: 'Pronto p/ Retirada',
  OutForDelivery: 'Saiu p/ Entrega',
  Delivered: 'Entregue',
  Cancelled: 'Cancelado'
};
