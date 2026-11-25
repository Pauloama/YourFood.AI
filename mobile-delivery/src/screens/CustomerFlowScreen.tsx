import { useEffect, useState } from 'react';
import { ScrollView, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { mobileApi } from '../services/api';
import { themeStyles as s } from '../styles/theme';
import {
  ABSA_ASPECTS,
  ORDER_STATUS_PT,
  type MenuItem,
  type Order,
  type ReviewAnnotationInput,
  type Store
} from '../types/models';

export function CustomerFlowScreen() {
  const [tab, setTab] = useState<'stores' | 'orders'>('stores');
  const [stores, setStores] = useState<Store[]>([]);
  const [selectedStore, setSelectedStore] = useState<Store | null>(null);
  const [cart, setCart] = useState<Array<{ store: Store; item: MenuItem; quantity: number }>>([]);
  const [address, setAddress] = useState('Av. Paulista, 1200 - Apto 51');
  const [orders, setOrders] = useState<Order[]>([]);
  const [reviewOrder, setReviewOrder] = useState<Order | null>(null);
  const [reviewText, setReviewText] = useState('');
  const [reviewRating, setReviewRating] = useState(5);
  const [selectedAspect, setSelectedAspect] = useState<string>(ABSA_ASPECTS[0]);
  const [selectedSentiment, setSelectedSentiment] = useState<'positivo' | 'negativo' | 'neutro'>('positivo');
  const [annotations, setAnnotations] = useState<ReviewAnnotationInput[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const [sList, oList] = await Promise.all([mobileApi.listStores(), mobileApi.getMyOrders()]);
      setStores(sList);
      setOrders(oList);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Erro ao sincronizar');
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const addCart = (store: Store, item: MenuItem) => {
    setCart((prev) => {
      if (prev.length > 0 && prev[0].store.id !== store.id) {
        return [{ store, item, quantity: 1 }];
      }
      const existing = prev.find((c) => c.item.id === item.id);
      if (existing) {
        return prev.map((c) => (c.item.id === item.id ? { ...c, quantity: c.quantity + 1 } : c));
      }
      return [...prev, { store, item, quantity: 1 }];
    });
  };

  const placeOrder = async () => {
    if (cart.length === 0) return;
    try {
      await mobileApi.createOrder({
        storeId: cart[0].store.id,
        deliveryAddress: address,
        items: cart.map((c) => ({ menuItemId: c.item.id, quantity: c.quantity }))
      });
      setCart([]);
      setTab('orders');
      setMessage('Pedido realizado! Confirme o pagamento para iniciar o preparo.');
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Falha ao enviar pedido');
    }
  };

  const advanceOrder = async (orderId: string, nextStatus: string) => {
    try {
      await mobileApi.transitionOrder(orderId, nextStatus);
      setMessage(`Status alterado para ${ORDER_STATUS_PT[nextStatus]}`);
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Falha ao atualizar status');
    }
  };

  const submitReview = async () => {
    if (!reviewOrder || !reviewText.trim()) return;
    try {
      const created = await mobileApi.createReview({
        orderId: reviewOrder.id,
        text: reviewText.trim(),
        rating: reviewRating,
        runInferenceImmediately: true,
        annotations: annotations.length > 0 ? annotations : undefined
      });
      setReviewOrder(null);
      setReviewText('');
      setAnnotations([]);
      setMessage(`Avaliação registrada! ${created.predictions.length} aspectos extraídos pelo BERTimbau.`);
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Erro ao enviar avaliação');
    }
  };

  return (
    <View style={{ flex: 1 }}>
      <ScrollView contentContainerStyle={s.container}>
        {message && (
          <View style={s.card}>
            <Text style={s.text}>{message}</Text>
          </View>
        )}

        {reviewOrder && (
          <View style={s.card}>
            <Text style={s.cardTitle}>Avaliar {reviewOrder.storeName}</Text>
            <TextInput
              style={s.input}
              placeholder="Escreva sobre sabor, entrega, embalagem..."
              placeholderTextColor="#64748b"
              multiline
              value={reviewText}
              onChangeText={setReviewText}
            />
            <View style={s.row}>
              {[1, 2, 3, 4, 5].map((star) => (
                <TouchableOpacity
                  key={star}
                  style={[s.buttonSecondary, reviewRating === star && s.tabActive]}
                  onPress={() => setReviewRating(star)}
                >
                  <Text style={s.buttonText}>{star}★</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={s.subtitle}>Anotação de aspecto opcional:</Text>
            <View style={s.row}>
              {ABSA_ASPECTS.slice(0, 6).map((asp) => (
                <TouchableOpacity
                  key={asp}
                  style={[s.buttonSecondary, selectedAspect === asp && s.tabActive]}
                  onPress={() => setSelectedAspect(asp)}
                >
                  <Text style={s.buttonText}>{asp}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <View style={s.row}>
              {(['positivo', 'negativo', 'neutro'] as const).map((sent) => (
                <TouchableOpacity
                  key={sent}
                  style={[s.buttonSecondary, selectedSentiment === sent && s.tabActive]}
                  onPress={() => setSelectedSentiment(sent)}
                >
                  <Text style={s.buttonText}>{sent}</Text>
                </TouchableOpacity>
              ))}
              <TouchableOpacity
                style={s.buttonSecondary}
                onPress={() => setAnnotations((prev) => [...prev, { aspect: selectedAspect, sentiment: selectedSentiment }])}
              >
                <Text style={s.buttonText}>+ Tag</Text>
              </TouchableOpacity>
            </View>
            <View style={s.row}>
              <TouchableOpacity style={[s.buttonPrimary, { flex: 1 }]} onPress={submitReview}>
                <Text style={s.buttonText}>Enviar Avaliação ao Pipeline</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.buttonSecondary} onPress={() => setReviewOrder(null)}>
                <Text style={s.buttonText}>Cancelar</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {tab === 'stores' && !selectedStore && (
          <>
            {stores.map((store) => (
              <View key={store.id} style={s.card}>
                <View style={s.rowBetween}>
                  <Text style={s.cardTitle}>{store.name}</Text>
                  <Text style={s.badge}>{store.category}</Text>
                </View>
                <Text style={s.subtitle}>{store.description}</Text>
                <Text style={s.subtitle}>
                  Entrega R$ {store.deliveryFee.toFixed(2)} · {store.estimatedDeliveryMinutes} min
                </Text>
                <TouchableOpacity style={s.buttonPrimary} onPress={() => setSelectedStore(store)}>
                  <Text style={s.buttonText}>Abrir Cardápio ({store.menuItems.length})</Text>
                </TouchableOpacity>
              </View>
            ))}
          </>
        )}

        {tab === 'stores' && selectedStore && (
          <>
            <TouchableOpacity style={s.buttonSecondary} onPress={() => setSelectedStore(null)}>
              <Text style={s.buttonText}>Voltar às Lojas</Text>
            </TouchableOpacity>
            <Text style={s.title}>{selectedStore.name}</Text>
            {selectedStore.menuItems.map((item) => (
              <View key={item.id} style={s.card}>
                <View style={s.rowBetween}>
                  <Text style={s.cardTitle}>{item.name}</Text>
                  <Text style={s.badge}>R$ {item.price.toFixed(2)}</Text>
                </View>
                <Text style={s.subtitle}>{item.description}</Text>
                <TouchableOpacity style={s.buttonPrimary} onPress={() => addCart(selectedStore, item)}>
                  <Text style={s.buttonText}>Adicionar</Text>
                </TouchableOpacity>
              </View>
            ))}

            {cart.length > 0 && (
              <View style={s.card}>
                <Text style={s.cardTitle}>Carrinho ({cart.reduce((a, b) => a + b.quantity, 0)} itens)</Text>
                <TextInput style={s.input} value={address} onChangeText={setAddress} />
                <TouchableOpacity style={s.buttonSuccess} onPress={placeOrder}>
                  <Text style={s.buttonText}>Confirmar Pedido</Text>
                </TouchableOpacity>
              </View>
            )}
          </>
        )}

        {tab === 'orders' &&
          orders.map((order) => (
            <View key={order.id} style={s.card}>
              <View style={s.rowBetween}>
                <Text style={s.cardTitle}>{order.storeName}</Text>
                <Text style={s.badge}>{ORDER_STATUS_PT[order.status] || order.status}</Text>
              </View>
              <Text style={s.subtitle}>Total R$ {order.totalAmount.toFixed(2)}</Text>
              <View style={s.row}>
                {order.status === 'PendingPayment' && (
                  <TouchableOpacity style={s.buttonSuccess} onPress={() => advanceOrder(order.id, 'Confirmed')}>
                    <Text style={s.buttonText}>Confirmar Pagamento</Text>
                  </TouchableOpacity>
                )}
                {order.status === 'Delivered' && !order.hasReview && (
                  <TouchableOpacity style={s.buttonPrimary} onPress={() => setReviewOrder(order)}>
                    <Text style={s.buttonText}>Avaliar Pedido</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          ))}
      </ScrollView>

      <View style={s.tabBar}>
        <TouchableOpacity style={[s.tabItem, tab === 'stores' && s.tabActive]} onPress={() => setTab('stores')}>
          <Text style={s.buttonText}>Restaurantes</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.tabItem, tab === 'orders' && s.tabActive]} onPress={() => setTab('orders')}>
          <Text style={s.buttonText}>Pedidos ({orders.length})</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
