import { useEffect, useState, type FormEvent } from 'react';
import { ArrowRight, BarChart3, PlusCircle, Store as StoreIcon } from 'lucide-react';
import { deliveryApi } from '../services/api';
import { ABSA_ASPECTS, ORDER_STATUS_LABELS, type Order, type PipelineAnalytics, type Store } from '../types/models';

const LEDGER_LABELS: Record<string, string> = {
  OrderCharge: 'Cobrança do Pedido',
  OrderRefund: 'Estorno',
  MerchantSettlement: 'Repasse ao Restaurante'
};

const ASPECT_LABELS: Record<string, string> = Object.fromEntries(
  ABSA_ASPECTS.map((a) => [a.code, a.label])
);

export function MerchantPortalView() {
  const [tab, setTab] = useState<'orders' | 'stores' | 'insights'>('orders');
  const [stores, setStores] = useState<Store[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [analytics, setAnalytics] = useState<PipelineAnalytics | null>(null);
  const [selectedStoreId, setSelectedStoreId] = useState<string>('');
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'error' | 'success'; text: string } | null>(null);

  const [storeName, setStoreName] = useState('');
  const [storeCategory, setStoreCategory] = useState('Hamburgueria');
  const [storeDesc, setStoreDesc] = useState('');
  const [storeAddress, setStoreAddress] = useState('');
  const [storeFee, setStoreFee] = useState('8.90');
  const [storeEta, setStoreEta] = useState('35');

  const [itemName, setItemName] = useState('');
  const [itemDesc, setItemDesc] = useState('');
  const [itemCat, setItemCat] = useState('Pratos Principais');
  const [itemPrice, setItemPrice] = useState('39.90');

  const loadData = async () => {
    try {
      const [myStores, myOrders] = await Promise.all([
        deliveryApi.getMyStores(),
        deliveryApi.getMerchantOrders()
      ]);
      setStores(myStores);
      setOrders(myOrders);
      const targetStore = selectedStoreId || myStores[0]?.id || '';
      if (!selectedStoreId && targetStore) setSelectedStoreId(targetStore);
      const stats = await deliveryApi.getStoreAnalytics(targetStore || undefined);
      setAnalytics(stats);
    } catch (err) {
      setFeedback({ type: 'error', text: err instanceof Error ? err.message : 'Não foi possível carregar os dados da loja.' });
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateStore = async (e: FormEvent) => {
    e.preventDefault();
    setFeedback(null);
    setBusyAction('store');
    try {
      await deliveryApi.createStore({
        name: storeName,
        category: storeCategory,
        description: storeDesc,
        address: storeAddress,
        deliveryFee: Number(storeFee),
        estimatedDeliveryMinutes: Number(storeEta)
      });
      setStoreName('');
      setStoreDesc('');
      setStoreAddress('');
      setFeedback({ type: 'success', text: 'Estabelecimento cadastrado e disponível para pedidos!' });
      await loadData();
    } catch (err) {
      setFeedback({ type: 'error', text: err instanceof Error ? err.message : 'Não foi possível cadastrar a loja.' });
    } finally {
      setBusyAction(null);
    }
  };

  const handleCreateMenuItem = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedStoreId) return;
    setFeedback(null);
    setBusyAction('item');
    try {
      await deliveryApi.addMenuItem(selectedStoreId, {
        name: itemName,
        description: itemDesc,
        category: itemCat,
        price: Number(itemPrice)
      });
      setItemName('');
      setItemDesc('');
      setFeedback({ type: 'success', text: 'Novo item publicado no cardápio!' });
      await loadData();
    } catch (err) {
      setFeedback({ type: 'error', text: err instanceof Error ? err.message : 'Não foi possível adicionar o item.' });
    } finally {
      setBusyAction(null);
    }
  };

  const handleAdvanceOrder = async (orderId: string, nextStatus: string) => {
    setFeedback(null);
    setBusyAction(`${orderId}-${nextStatus}`);
    try {
      await deliveryApi.transitionOrder(
        orderId,
        nextStatus,
        `Status atualizado pelo restaurante para ${ORDER_STATUS_LABELS[nextStatus] || nextStatus}`
      );
      setFeedback({ type: 'success', text: `Pedido atualizado para "${ORDER_STATUS_LABELS[nextStatus] || nextStatus}".` });
      await loadData();
    } catch (err) {
      setFeedback({ type: 'error', text: err instanceof Error ? err.message : 'Não foi possível atualizar o status do pedido.' });
    } finally {
      setBusyAction(null);
    }
  };

  const selectedStore = stores.find((s) => s.id === selectedStoreId);
  const activeOrdersCount = orders.filter((o) => o.status !== 'Delivered' && o.status !== 'Cancelled').length;
  const totalRevenue = orders
    .filter((o) => o.status !== 'Cancelled')
    .reduce((sum, o) => sum + o.subtotalAmount, 0);

  return (
    <div className="stack" style={{ gap: '1.25rem' }}>
      <div className="grid-4">
        <div className="card">
          <span className="muted">Pedidos Ativos</span>
          <div className="kpi-value" style={{ color: 'var(--primary)' }}>
            {activeOrdersCount}
          </div>
        </div>
        <div className="card">
          <span className="muted">Lojas Cadastradas</span>
          <div className="kpi-value">{stores.length}</div>
        </div>
        <div className="card">
          <span className="muted">Faturamento Bruto</span>
          <div className="kpi-value" style={{ color: 'var(--success)' }}>
            R$ {totalRevenue.toFixed(2)}
          </div>
        </div>
        <div className="card">
          <span className="muted">Nota Média</span>
          <div className="kpi-value" style={{ color: 'var(--amber)' }}>
            {analytics ? analytics.averageRating.toFixed(1) : '0.0'} ★
          </div>
        </div>
      </div>

      <div className="tabs">
        <button className={`tab-btn ${tab === 'orders' ? 'active' : ''}`} onClick={() => setTab('orders')}>
          Pedidos ({orders.length})
        </button>
        <button className={`tab-btn ${tab === 'stores' ? 'active' : ''}`} onClick={() => setTab('stores')}>
          Lojas & Cardápio ({stores.length})
        </button>
        <button className={`tab-btn ${tab === 'insights' ? 'active' : ''}`} onClick={() => setTab('insights')}>
          <BarChart3 size={15} /> Avaliações & Insights
        </button>
      </div>

      {feedback && (
        <div className={feedback.type === 'error' ? 'error-box' : 'success-box'}>{feedback.text}</div>
      )}

      {tab === 'orders' && (
        <div className="stack">
          {orders.length === 0 ? (
            <div className="card empty-state">
              <div style={{ fontSize: '2.2rem' }}>📋</div>
              <h3>Nenhum pedido recebido ainda</h3>
              <p className="muted">Assim que um cliente finalizar um pedido nas suas lojas, ele aparecerá aqui.</p>
            </div>
          ) : (
            orders.map((order) => (
              <div key={order.id} className="card stack">
                <div className="row-between">
                  <div>
                    <h3>
                      {order.storeName} · <span className="muted">#{order.id.slice(0, 8)}</span>
                    </h3>
                    <p className="muted">
                      {order.deliveryAddress} · Total R$ {order.totalAmount.toFixed(2)}
                    </p>
                  </div>
                  <span
                    className={`badge ${
                      order.status === 'Delivered'
                        ? 'badge-positive'
                        : order.status === 'Cancelled'
                          ? 'badge-negative'
                          : 'badge-info'
                    }`}
                  >
                    {ORDER_STATUS_LABELS[order.status] || order.status}
                  </span>
                </div>
                <div className="muted">
                  {order.items.map((i) => `${i.quantity}x ${i.itemNameSnapshot}`).join(' · ')}
                </div>
                <div className="row">
                  {order.allowedNextStatuses.map((next) => (
                    <button
                      key={next}
                      disabled={busyAction !== null}
                      className={next === 'Cancelled' ? 'btn-danger' : next === 'Delivered' ? 'btn-success' : 'btn-primary'}
                      onClick={() => handleAdvanceOrder(order.id, next)}
                    >
                      <ArrowRight size={14} />{' '}
                      {busyAction === `${order.id}-${next}`
                        ? 'Atualizando...'
                        : ORDER_STATUS_LABELS[next] || next}
                    </button>
                  ))}
                </div>
                <div className="row muted" style={{ fontSize: '0.78rem', paddingTop: '0.4rem', borderTop: '1px solid var(--border)' }}>
                  <strong>Extrato financeiro:</strong>
                  {order.ledgerEntries.map((l) => (
                    <span key={l.id} className="badge badge-neutral">
                      {LEDGER_LABELS[l.entryType] || l.entryType}: R$ {l.amount.toFixed(2)}
                    </span>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {tab === 'stores' && (
        <div className="grid-2" style={{ alignItems: 'start' }}>
          <form className="card stack" onSubmit={handleCreateStore}>
            <div className="row">
              <StoreIcon size={20} color="#ea4c23" />
              <h3>Cadastrar Nova Loja</h3>
            </div>
            <input placeholder="Nome do Estabelecimento" value={storeName} onChange={(e) => setStoreName(e.target.value)} required />
            <input placeholder="Categoria (Ex: Pizzaria, Hamburgueria)" value={storeCategory} onChange={(e) => setStoreCategory(e.target.value)} required />
            <textarea placeholder="Descrição da loja" value={storeDesc} onChange={(e) => setStoreDesc(e.target.value)} required />
            <input placeholder="Endereço completo" value={storeAddress} onChange={(e) => setStoreAddress(e.target.value)} required />
            <div className="form-grid-2">
              <div>
                <label className="muted">Taxa de Entrega (R$)</label>
                <input type="number" step="0.10" value={storeFee} onChange={(e) => setStoreFee(e.target.value)} required />
              </div>
              <div>
                <label className="muted">Tempo Estimado (min)</label>
                <input type="number" value={storeEta} onChange={(e) => setStoreEta(e.target.value)} required />
              </div>
            </div>
            <button type="submit" className="btn-primary" disabled={busyAction === 'store'}>
              <PlusCircle size={15} /> {busyAction === 'store' ? 'Cadastrando...' : 'Criar Loja'}
            </button>
          </form>

          <div className="card stack">
            <h3>Gerenciar Cardápio</h3>
            {stores.length === 0 ? (
              <p className="muted">Cadastre sua primeira loja ao lado para adicionar itens ao cardápio.</p>
            ) : (
              <>
                <select value={selectedStoreId} onChange={(e) => setSelectedStoreId(e.target.value)}>
                  {stores.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.menuItems.length} itens)
                    </option>
                  ))}
                </select>

                {selectedStore && (
                  <>
                    <form className="stack" onSubmit={handleCreateMenuItem}>
                      <input placeholder="Nome do item" value={itemName} onChange={(e) => setItemName(e.target.value)} required />
                      <input placeholder="Descrição do item" value={itemDesc} onChange={(e) => setItemDesc(e.target.value)} required />
                      <div className="form-grid-2">
                        <input placeholder="Categoria" value={itemCat} onChange={(e) => setItemCat(e.target.value)} required />
                        <input type="number" step="0.10" placeholder="Preço (R$)" value={itemPrice} onChange={(e) => setItemPrice(e.target.value)} required />
                      </div>
                      <button type="submit" className="btn-primary" disabled={busyAction === 'item'}>
                        {busyAction === 'item' ? 'Salvando...' : 'Adicionar Item ao Cardápio'}
                      </button>
                    </form>

                    <div className="stack" style={{ marginTop: '0.4rem' }}>
                      {selectedStore.menuItems.map((item) => (
                        <div key={item.id} className="row-between" style={{ padding: '0.65rem 0.85rem', background: 'var(--surface-warm)', borderRadius: 10, border: '1px solid var(--border)' }}>
                          <div>
                            <strong>{item.name}</strong>
                            <div className="muted">
                              {item.category} ·{' '}
                              <span className="price-tag" style={{ fontSize: '0.9rem' }}>
                                R$ {item.price.toFixed(2)}
                              </span>
                            </div>
                          </div>
                          <span className={`badge ${item.isAvailable ? 'badge-positive' : 'badge-negative'}`}>
                            {item.isAvailable ? 'Disponível' : 'Pausado'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {tab === 'insights' && (
        <div className="card stack">
          <h3>Percepção dos Clientes por Aspecto</h3>
          {!analytics || analytics.aspectBreakdown.every((a) => a.total === 0) ? (
            <p className="muted">Ainda não há avaliações suficientes para exibir os indicadores por aspecto.</p>
          ) : (
            <div className="grid-3">
              {analytics.aspectBreakdown
                .filter((a) => a.total > 0)
                .map((a) => (
                  <div key={a.aspect} style={{ padding: '0.9rem', background: 'var(--surface-warm)', borderRadius: 12, border: '1px solid var(--border)' }}>
                    <div className="row-between">
                      <strong>{ASPECT_LABELS[a.aspect] || a.aspect}</strong>
                      <span className="badge badge-info">{a.entity}</span>
                    </div>
                    <div className="row" style={{ marginTop: '0.55rem' }}>
                      <span className="badge badge-positive">{a.positive} positivo(s)</span>
                      <span className="badge badge-negative">{a.negative} negativo(s)</span>
                      <span className="badge badge-neutral">{a.neutral} neutro(s)</span>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
