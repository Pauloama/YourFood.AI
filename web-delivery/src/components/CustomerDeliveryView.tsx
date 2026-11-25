import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, Clock, Plus, Search, ShoppingBag, Sparkles, Star, Trash2 } from 'lucide-react';
import { deliveryApi } from '../services/api';
import {
  ABSA_ASPECTS,
  ORDER_FLOW_STEPS,
  ORDER_STATUS_LABELS,
  type MenuItem,
  type Order,
  type Review,
  type ReviewAnnotationInput,
  type Store
} from '../types/models';

interface CartEntry {
  item: MenuItem;
  store: Store;
  quantity: number;
}

const ASPECT_LABEL_MAP: Record<string, string> = Object.fromEntries(
  ABSA_ASPECTS.map((a) => [a.code, a.label])
);

function getCategoryVisual(category: string): { coverClass: string; emoji: string } {
  const normalized = category.toLowerCase();
  if (normalized.includes('burg') || normalized.includes('lanche')) {
    return { coverClass: 'store-cover-burger', emoji: '🍔' };
  }
  if (normalized.includes('pizz') || normalized.includes('ital')) {
    return { coverClass: 'store-cover-pizza', emoji: '🍕' };
  }
  if (normalized.includes('japon') || normalized.includes('sushi')) {
    return { coverClass: 'store-cover-sushi', emoji: '🍣' };
  }
  return { coverClass: 'store-cover-default', emoji: '🍽️' };
}

export function CustomerDeliveryView() {
  const [tab, setTab] = useState<'explore' | 'orders' | 'reviews'>('explore');
  const [stores, setStores] = useState<Store[]>([]);
  const [selectedStore, setSelectedStore] = useState<Store | null>(null);
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<string>('Todos');
  const [cart, setCart] = useState<CartEntry[]>([]);
  const [deliveryAddress, setDeliveryAddress] = useState('Av. Paulista, 1578 - Apto 91');
  const [orderNotes, setOrderNotes] = useState('');
  const [orders, setOrders] = useState<Order[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [reviewTargetOrder, setReviewTargetOrder] = useState<Order | null>(null);
  const [reviewText, setReviewText] = useState('');
  const [reviewRating, setReviewRating] = useState(5);
  const [runInference, setRunInference] = useState(true);
  const [annotations, setAnnotations] = useState<ReviewAnnotationInput[]>([]);
  const [draftAspect, setDraftAspect] = useState<string>(ABSA_ASPECTS[0].code);
  const [draftSentiment, setDraftSentiment] = useState<'positivo' | 'negativo' | 'neutro'>('positivo');
  const [draftEvidence, setDraftEvidence] = useState('');
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ type: 'error' | 'success'; text: string } | null>(null);
  const cartRef = useRef<HTMLDivElement | null>(null);

  const loadAll = async (overrideSearch?: string) => {
    try {
      const term = overrideSearch !== undefined ? overrideSearch : search;
      const [s, o, r] = await Promise.all([
        deliveryApi.listStores(term || undefined),
        deliveryApi.getMyOrders(),
        deliveryApi.listReviews()
      ]);
      setStores(s);
      setOrders(o);
      setReviews(r);
      if (selectedStore) {
        setSelectedStore(s.find((x) => x.id === selectedStore.id) ?? null);
      }
    } catch (err) {
      setFeedback({ type: 'error', text: err instanceof Error ? err.message : 'Não foi possível carregar os restaurantes.' });
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const categories = ['Todos', ...Array.from(new Set(stores.map((s) => s.category)))];
  const visibleStores =
    activeCategory === 'Todos' ? stores : stores.filter((s) => s.category === activeCategory);

  const addToCart = (store: Store, item: MenuItem) => {
    setCart((prev) => {
      if (prev.length > 0 && prev[0].store.id !== store.id) {
        setFeedback({
          type: 'success',
          text: `Sua sacola foi atualizada para os itens de ${store.name}.`
        });
        return [{ store, item, quantity: 1 }];
      }
      const existing = prev.find((c) => c.item.id === item.id);
      if (existing) {
        return prev.map((c) => (c.item.id === item.id ? { ...c, quantity: c.quantity + 1 } : c));
      }
      return [...prev, { store, item, quantity: 1 }];
    });
  };

  const changeQty = (itemId: string, delta: number) => {
    setCart((prev) =>
      prev
        .map((c) => (c.item.id === itemId ? { ...c, quantity: c.quantity + delta } : c))
        .filter((c) => c.quantity > 0)
    );
  };

  const cartItemCount = cart.reduce((s, c) => s + c.quantity, 0);
  const cartSubtotal = cart.reduce((sum, c) => sum + c.item.price * c.quantity, 0);
  const cartFee = cart.length > 0 ? cart[0].store.deliveryFee : 0;
  const cartTotal = cartSubtotal + cartFee;

  const checkout = async () => {
    if (cart.length === 0) return;
    if (!deliveryAddress.trim()) {
      setFeedback({ type: 'error', text: 'Informe o endereço de entrega antes de finalizar o pedido.' });
      return;
    }
    setFeedback(null);
    setBusyAction('checkout');
    try {
      const created = await deliveryApi.createOrder({
        storeId: cart[0].store.id,
        deliveryAddress: deliveryAddress.trim(),
        notes: orderNotes.trim() || undefined,
        items: cart.map((c) => ({ menuItemId: c.item.id, quantity: c.quantity }))
      });
      setCart([]);
      setOrderNotes('');
      setTab('orders');
      setFeedback({
        type: 'success',
        text: `Pedido #${created.id.slice(0, 8)} recebido! Confirme o pagamento para a cozinha iniciar o preparo.`
      });
      await loadAll();
    } catch (err) {
      setFeedback({ type: 'error', text: err instanceof Error ? err.message : 'Não foi possível finalizar o pedido.' });
    } finally {
      setBusyAction(null);
    }
  };

  const handleTransition = async (orderId: string, nextStatus: string) => {
    setFeedback(null);
    setBusyAction(`${orderId}-${nextStatus}`);
    try {
      const reason =
        nextStatus === 'Confirmed' ? 'Pagamento confirmado pelo cliente' : 'Pedido cancelado pelo cliente';
      await deliveryApi.transitionOrder(orderId, nextStatus, reason);
      setFeedback({
        type: 'success',
        text:
          nextStatus === 'Confirmed'
            ? 'Pagamento confirmado! Seu pedido já foi enviado para a cozinha.'
            : 'Pedido cancelado com sucesso. O estorno foi registrado.'
      });
      await loadAll();
    } catch (err) {
      setFeedback({ type: 'error', text: err instanceof Error ? err.message : 'Não foi possível atualizar o pedido.' });
    } finally {
      setBusyAction(null);
    }
  };

  const addDraftAnnotation = () => {
    setAnnotations((prev) => [
      ...prev,
      { aspect: draftAspect, sentiment: draftSentiment, evidenceText: draftEvidence.trim() || undefined }
    ]);
    setDraftEvidence('');
  };

  const removeDraftAnnotation = (index: number) => {
    setAnnotations((prev) => prev.filter((_, idx) => idx !== index));
  };

  const submitReview = async () => {
    if (!reviewTargetOrder || !reviewText.trim()) return;
    setFeedback(null);
    setBusyAction('review');
    try {
      const created = await deliveryApi.createReview({
        orderId: reviewTargetOrder.id,
        text: reviewText.trim(),
        rating: reviewRating,
        runInferenceImmediately: runInference,
        annotations: annotations.length > 0 ? annotations : undefined
      });
      setReviewTargetOrder(null);
      setReviewText('');
      setReviewRating(5);
      setAnnotations([]);
      setTab('reviews');
      setFeedback({
        type: 'success',
        text:
          created.predictions.length > 0
            ? `Obrigado pela avaliação! Nossa IA identificou ${created.predictions.length} ponto(s) no seu comentário.`
            : 'Obrigado pela sua avaliação! Seu feedback foi registrado com sucesso.'
      });
      await loadAll();
    } catch (err) {
      setFeedback({ type: 'error', text: err instanceof Error ? err.message : 'Não foi possível enviar a avaliação.' });
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <div className="stack" style={{ gap: '1.25rem' }}>
      <div className="hero-banner">
        <div>
          <h1>O que vamos pedir hoje?</h1>
          <p>
            Escolha seus pratos favoritos, acompanhe cada etapa em tempo real e compartilhe como foi sua experiência.
          </p>
        </div>
        <div className="hero-search">
          <input
            placeholder="Buscar restaurantes ou pratos..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') loadAll();
            }}
          />
          <button className="btn-primary" onClick={() => loadAll()}>
            <Search size={16} /> Buscar
          </button>
        </div>
      </div>

      <div className="row-between">
        <div className="tabs">
          <button className={`tab-btn ${tab === 'explore' ? 'active' : ''}`} onClick={() => setTab('explore')}>
            Restaurantes
          </button>
          <button className={`tab-btn ${tab === 'orders' ? 'active' : ''}`} onClick={() => setTab('orders')}>
            Meus Pedidos ({orders.length})
          </button>
          <button className={`tab-btn ${tab === 'reviews' ? 'active' : ''}`} onClick={() => setTab('reviews')}>
            Avaliações ({reviews.length})
          </button>
        </div>

        {tab === 'explore' && !selectedStore && (
          <div className="chip-row">
            {categories.map((cat) => (
              <button
                key={cat}
                className={`chip ${activeCategory === cat ? 'active' : ''}`}
                onClick={() => setActiveCategory(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
        )}
      </div>

      {feedback && (
        <div className={feedback.type === 'error' ? 'error-box' : 'success-box'}>{feedback.text}</div>
      )}

      {tab === 'explore' && (
        <div className="delivery-layout">
          <div className="stack">
            {!selectedStore ? (
              visibleStores.length === 0 ? (
                <div className="card empty-state">
                  <div style={{ fontSize: '2.2rem' }}>🔎</div>
                  <h3>Nenhum restaurante encontrado</h3>
                  <p className="muted">Tente buscar por outro nome ou limpar o filtro de categoria.</p>
                  <button
                    className="btn-secondary"
                    onClick={() => {
                      setSearch('');
                      setActiveCategory('Todos');
                      loadAll('');
                    }}
                  >
                    Mostrar todos os restaurantes
                  </button>
                </div>
              ) : (
                <div className="grid-2">
                  {visibleStores.map((store) => {
                    const visual = getCategoryVisual(store.category);
                    return (
                      <div key={store.id} className="card store-card">
                        <div className={`store-cover ${visual.coverClass}`}>
                          <div className="store-emoji">{visual.emoji}</div>
                          <span className="badge badge-glass">
                            {store.isOpen && <span className="live-dot" />}
                            {store.isOpen ? 'Aberto agora' : 'Fechado'}
                          </span>
                        </div>
                        <div className="store-body">
                          <div className="row-between">
                            <h3>{store.name}</h3>
                            <span className="badge badge-info">{store.category}</span>
                          </div>
                          <p className="muted">{store.description}</p>
                          <div className="row-between muted" style={{ marginTop: 'auto', paddingTop: '0.4rem' }}>
                            <span className="row" style={{ gap: '0.3rem' }}>
                              <Clock size={14} /> {store.estimatedDeliveryMinutes} min
                            </span>
                            <strong>Entrega R$ {store.deliveryFee.toFixed(2)}</strong>
                          </div>
                          <button className="btn-primary" onClick={() => setSelectedStore(store)}>
                            Ver Cardápio ({store.menuItems.length} itens)
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )
            ) : (
              <div className="stack">
                <div className="card row-between" style={{ background: 'var(--surface-warm)', borderColor: '#f5d6c8' }}>
                  <div className="row">
                    <div className="store-emoji" style={{ background: '#ffffff', boxShadow: 'var(--shadow-sm)' }}>
                      {getCategoryVisual(selectedStore.category).emoji}
                    </div>
                    <div>
                      <h2>{selectedStore.name}</h2>
                      <p className="muted">
                        {selectedStore.address} · {selectedStore.estimatedDeliveryMinutes} min · Entrega R${' '}
                        {selectedStore.deliveryFee.toFixed(2)}
                      </p>
                    </div>
                  </div>
                  <button className="btn-secondary" onClick={() => setSelectedStore(null)}>
                    Voltar às Lojas
                  </button>
                </div>

                <div className="grid-2">
                  {selectedStore.menuItems.map((item) => (
                    <div key={item.id} className="card menu-card">
                      <div className="stack" style={{ gap: '0.45rem' }}>
                        <div className="row-between">
                          <h4>{item.name}</h4>
                          <span className="price-tag">R$ {item.price.toFixed(2)}</span>
                        </div>
                        <span className="badge badge-neutral" style={{ width: 'fit-content' }}>
                          {item.category}
                        </span>
                        <p className="muted">{item.description}</p>
                      </div>
                      <button
                        className="btn-primary"
                        disabled={!item.isAvailable}
                        onClick={() => addToCart(selectedStore, item)}
                      >
                        <Plus size={15} /> {item.isAvailable ? 'Adicionar à Sacola' : 'Indisponível'}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div ref={cartRef} className="card cart-sticky stack">
            <div className="row-between">
              <div className="row">
                <ShoppingBag size={20} color="#ea4c23" />
                <h3>Sua Sacola</h3>
              </div>
              {cartItemCount > 0 && <span className="badge badge-info">{cartItemCount} {cartItemCount === 1 ? 'item' : 'itens'}</span>}
            </div>

            {cart.length === 0 ? (
              <div className="empty-state" style={{ padding: '1rem 0.25rem' }}>
                <div style={{ fontSize: '2rem' }}>🛍️</div>
                <p className="muted">Sua sacola está vazia. Escolha pratos deliciosos para fazer seu pedido!</p>
              </div>
            ) : (
              <>
                <div className="badge badge-neutral" style={{ width: 'fit-content' }}>
                  {cart[0].store.name}
                </div>
                {cart.map((entry) => (
                  <div key={entry.item.id} className="row-between" style={{ paddingBottom: '0.5rem', borderBottom: '1px solid var(--border)' }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <strong>{entry.item.name}</strong>
                      <div className="muted">R$ {(entry.item.price * entry.quantity).toFixed(2)}</div>
                    </div>
                    <div className="row" style={{ gap: '0.35rem' }}>
                      <div className="qty-control">
                        <button className="qty-btn" onClick={() => changeQty(entry.item.id, -1)}>
                          -
                        </button>
                        <strong style={{ minWidth: 18, textAlign: 'center', fontSize: '0.88rem' }}>{entry.quantity}</strong>
                        <button className="qty-btn" onClick={() => changeQty(entry.item.id, 1)}>
                          +
                        </button>
                      </div>
                      <button className="btn-danger" style={{ padding: '0.4rem' }} onClick={() => changeQty(entry.item.id, -entry.quantity)}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}

                <div className="stack" style={{ gap: '0.4rem' }}>
                  <div className="row-between muted">
                    <span>Subtotal</span>
                    <span>R$ {cartSubtotal.toFixed(2)}</span>
                  </div>
                  <div className="row-between muted">
                    <span>Taxa de entrega</span>
                    <span>R$ {cartFee.toFixed(2)}</span>
                  </div>
                  <div className="row-between" style={{ fontSize: '1.05rem', paddingTop: '0.35rem' }}>
                    <strong>Total</strong>
                    <strong className="price-tag" style={{ fontSize: '1.18rem' }}>
                      R$ {cartTotal.toFixed(2)}
                    </strong>
                  </div>
                </div>

                <div>
                  <label className="muted">Endereço de Entrega</label>
                  <input value={deliveryAddress} onChange={(e) => setDeliveryAddress(e.target.value)} />
                </div>
                <div>
                  <label className="muted">Observações para a cozinha</label>
                  <input value={orderNotes} onChange={(e) => setOrderNotes(e.target.value)} placeholder="Ex: sem cebola, molho à parte" />
                </div>
                <button className="btn-primary" style={{ padding: '0.8rem' }} disabled={busyAction === 'checkout'} onClick={checkout}>
                  {busyAction === 'checkout' ? 'Enviando pedido...' : 'Finalizar Pedido'}
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {tab === 'explore' && cartItemCount > 0 && (
        <button
          type="button"
          className="mobile-cart-bar"
          onClick={() => cartRef.current?.scrollIntoView({ behavior: 'smooth' })}
        >
          <span>
            Ver Sacola ({cartItemCount} {cartItemCount === 1 ? 'item' : 'itens'})
          </span>
          <span>R$ {cartTotal.toFixed(2)}</span>
        </button>
      )}

      {tab === 'orders' && (
        <div className="stack">
          {orders.length === 0 ? (
            <div className="card empty-state">
              <div style={{ fontSize: '2.2rem' }}>🛵</div>
              <h3>Você ainda não fez nenhum pedido</h3>
              <p className="muted">Explore os restaurantes disponíveis e peça seu prato favorito.</p>
              <button className="btn-primary" onClick={() => setTab('explore')}>
                Explorar Restaurantes
              </button>
            </div>
          ) : (
            orders.map((order) => {
              const currentIdx = ORDER_FLOW_STEPS.indexOf(order.status);
              const progressPct =
                order.status === 'Cancelled'
                  ? 0
                  : Math.round(((currentIdx + 1) / ORDER_FLOW_STEPS.length) * 100);
              return (
                <div key={order.id} className="card stack">
                  <div className="row-between">
                    <div>
                      <h3>
                        {order.storeName} · <span className="muted">#{order.id.slice(0, 8)}</span>
                      </h3>
                      <p className="muted">
                        {order.deliveryAddress} · {new Date(order.createdAtUtc).toLocaleString('pt-BR')}
                      </p>
                    </div>
                    <span
                      className={`badge ${
                        order.status === 'Cancelled'
                          ? 'badge-negative'
                          : order.status === 'Delivered'
                            ? 'badge-positive'
                            : 'badge-info'
                      }`}
                    >
                      {order.status !== 'Cancelled' && order.status !== 'Delivered' && <span className="live-dot" />}
                      {ORDER_STATUS_LABELS[order.status] || order.status}
                    </span>
                  </div>

                  {order.status !== 'Cancelled' && (
                    <div className="progress-track">
                      <div className="progress-fill" style={{ width: `${progressPct}%` }} />
                    </div>
                  )}

                  <div className="timeline">
                    {ORDER_FLOW_STEPS.map((step, idx) => (
                      <span
                        key={step}
                        className={`timeline-step ${
                          order.status === 'Cancelled'
                            ? ''
                            : idx < currentIdx
                              ? 'done'
                              : idx === currentIdx
                                ? 'current'
                                : ''
                        }`}
                      >
                        {ORDER_STATUS_LABELS[step]}
                      </span>
                    ))}
                  </div>

                  <div className="row-between" style={{ paddingTop: '0.4rem', borderTop: '1px solid var(--border)' }}>
                    <div className="muted">
                      {order.items.map((i) => `${i.quantity}x ${i.itemNameSnapshot}`).join(' · ')}
                    </div>
                    <strong className="price-tag">Total R$ {order.totalAmount.toFixed(2)}</strong>
                  </div>

                  <div className="row">
                    {order.status === 'PendingPayment' && (
                      <button
                        className="btn-success"
                        disabled={busyAction !== null}
                        onClick={() => handleTransition(order.id, 'Confirmed')}
                      >
                        <CheckCircle2 size={15} />{' '}
                        {busyAction === `${order.id}-Confirmed` ? 'Confirmando...' : 'Confirmar Pagamento'}
                      </button>
                    )}
                    {order.allowedNextStatuses.includes('Cancelled') && (
                      <button
                        className="btn-danger"
                        disabled={busyAction !== null}
                        onClick={() => handleTransition(order.id, 'Cancelled')}
                      >
                        {busyAction === `${order.id}-Cancelled` ? 'Cancelando...' : 'Cancelar Pedido'}
                      </button>
                    )}
                    {order.status === 'Delivered' && !order.hasReview && (
                      <button className="btn-primary" onClick={() => setReviewTargetOrder(order)}>
                        <Sparkles size={15} /> Avaliar Pedido
                      </button>
                    )}
                    {order.hasReview && <span className="badge badge-positive">Pedido Avaliado</span>}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {tab === 'reviews' &&
        (reviews.length === 0 ? (
          <div className="card empty-state">
            <div style={{ fontSize: '2.2rem' }}>⭐</div>
            <h3>Nenhuma avaliação registrada ainda</h3>
            <p className="muted">Quando seu pedido for entregue, avalie a experiência na aba Meus Pedidos.</p>
          </div>
        ) : (
          <div className="grid-2">
            {reviews.map((review) => (
              <div key={review.id} className="card stack">
                <div className="row-between">
                  <h4>{review.storeName}</h4>
                  <span className="badge badge-neutral">
                    <Star size={13} /> {review.rating}.0 / 5
                  </span>
                </div>
                <p style={{ fontSize: '0.96rem' }}>"{review.text}"</p>
                {review.annotations.length > 0 && (
                  <div className="row">
                    <span className="muted" style={{ fontSize: '0.78rem' }}>
                      Pontos destacados:
                    </span>
                    {review.annotations.map((ann) => (
                      <span
                        key={ann.id}
                        className={`badge ${
                          ann.sentiment === 'positivo'
                            ? 'badge-positive'
                            : ann.sentiment === 'negativo'
                              ? 'badge-negative'
                              : 'badge-neutral'
                        }`}
                      >
                        {ASPECT_LABEL_MAP[ann.aspect] || ann.aspect}: {ann.sentiment}
                      </span>
                    ))}
                  </div>
                )}
                {review.predictions.length > 0 && (
                  <div className="row">
                    <span className="muted" style={{ fontSize: '0.78rem' }}>
                      Análise automática:
                    </span>
                    {review.predictions.map((pred, idx) => (
                      <span
                        key={`${pred.aspect}-${idx}`}
                        className={`badge ${
                          pred.sentiment === 'positivo'
                            ? 'badge-positive'
                            : pred.sentiment === 'negativo'
                              ? 'badge-negative'
                              : 'badge-neutral'
                        }`}
                      >
                        {ASPECT_LABEL_MAP[pred.aspect] || pred.aspect} → {pred.sentiment} (
                        {Math.round(pred.sentimentProbability * 100)}%)
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}

      {reviewTargetOrder && (
        <div className="modal-backdrop">
          <div className="card modal-content stack">
            <div className="row-between">
              <h3>Avaliar {reviewTargetOrder.storeName}</h3>
              <button className="btn-secondary" onClick={() => setReviewTargetOrder(null)}>
                Fechar
              </button>
            </div>
            <p className="muted">
              Conte o que você achou do pedido. Sua avaliação ajuda os restaurantes e aprimora nossas recomendações.
            </p>

            <div>
              <label className="muted">Sua nota geral</label>
              <div className="row" style={{ marginTop: '0.35rem' }}>
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    className={`star-btn ${star <= reviewRating ? 'lit' : ''}`}
                    onClick={() => setReviewRating(star)}
                  >
                    <Star size={15} /> {star}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="muted">Seu comentário</label>
              <textarea
                rows={4}
                placeholder="Ex: O hambúrguer estava maravilhoso e bem quente, entrega super rápida!"
                value={reviewText}
                onChange={(e) => setReviewText(e.target.value)}
              />
            </div>

            <div className="card stack" style={{ background: 'var(--surface-warm)' }}>
              <strong>Destacar aspectos específicos (opcional)</strong>
              <div className="form-grid-2">
                <select value={draftAspect} onChange={(e) => setDraftAspect(e.target.value)}>
                  {ABSA_ASPECTS.map((a) => (
                    <option key={a.code} value={a.code}>
                      {a.label} ({a.entity})
                    </option>
                  ))}
                </select>
                <select
                  value={draftSentiment}
                  onChange={(e) => setDraftSentiment(e.target.value as 'positivo' | 'negativo' | 'neutro')}
                >
                  <option value="positivo">Positivo</option>
                  <option value="negativo">Negativo</option>
                  <option value="neutro">Neutro</option>
                </select>
              </div>
              <div className="form-grid-2">
                <input
                  placeholder="Trecho de evidência (opcional)"
                  value={draftEvidence}
                  onChange={(e) => setDraftEvidence(e.target.value)}
                />
                <button type="button" className="btn-secondary" onClick={addDraftAnnotation}>
                  + Adicionar Destaque
                </button>
              </div>
              {annotations.length > 0 && (
                <div className="row">
                  {annotations.map((a, idx) => (
                    <button
                      key={`${a.aspect}-${idx}`}
                      type="button"
                      className={`badge ${
                        a.sentiment === 'positivo'
                          ? 'badge-positive'
                          : a.sentiment === 'negativo'
                            ? 'badge-negative'
                            : 'badge-neutral'
                      }`}
                      onClick={() => removeDraftAnnotation(idx)}
                    >
                      {ASPECT_LABEL_MAP[a.aspect] || a.aspect}: {a.sentiment} ×
                    </button>
                  ))}
                </div>
              )}
            </div>

            <label className="row muted" style={{ cursor: 'pointer' }}>
              <input
                type="checkbox"
                style={{ width: 'auto' }}
                checked={runInference}
                onChange={(e) => setRunInference(e.target.checked)}
              />
              Analisar sentimentos automaticamente ao enviar
            </label>

            <button
              className="btn-primary"
              style={{ padding: '0.8rem' }}
              onClick={submitReview}
              disabled={!reviewText.trim() || busyAction === 'review'}
            >
              <Sparkles size={16} /> {busyAction === 'review' ? 'Enviando...' : 'Enviar Avaliação'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
