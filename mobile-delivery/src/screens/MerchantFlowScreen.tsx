import { useEffect, useState } from 'react';
import { ScrollView, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { mobileApi } from '../services/api';
import { themeStyles as s } from '../styles/theme';
import { ORDER_STATUS_PT, type Order, type Store } from '../types/models';

export function MerchantFlowScreen() {
  const [tab, setTab] = useState<'orders' | 'stores'>('orders');
  const [stores, setStores] = useState<Store[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [storeName, setStoreName] = useState('');
  const [storeCategory, setStoreCategory] = useState('Hamburgueria');
  const [storeAddress, setStoreAddress] = useState('');
  const [itemName, setItemName] = useState('');
  const [itemPrice, setItemPrice] = useState('34.90');
  const [message, setMessage] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const [sList, oList] = await Promise.all([mobileApi.getMyStores(), mobileApi.getMerchantOrders()]);
      setStores(sList);
      setOrders(oList);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Erro ao carregar dados do restaurante');
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const createStore = async () => {
    if (!storeName.trim()) return;
    try {
      await mobileApi.createStore({
        name: storeName,
        category: storeCategory,
        description: 'Cadastrado via YourFood Mobile',
        address: storeAddress || 'Centro',
        deliveryFee: 8.5,
        estimatedDeliveryMinutes: 35
      });
      setStoreName('');
      setStoreAddress('');
      setMessage('Loja cadastrada!');
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Erro ao cadastrar loja');
    }
  };

  const addItem = async (storeId: string) => {
    if (!itemName.trim()) return;
    try {
      await mobileApi.addMenuItem(storeId, {
        name: itemName,
        description: 'Item cadastrado via app mobile',
        category: 'Cardápio',
        price: Number(itemPrice)
      });
      setItemName('');
      setMessage('Item cadastrado!');
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Erro ao adicionar item');
    }
  };

  const advance = async (orderId: string, nextStatus: string) => {
    try {
      await mobileApi.transitionOrder(orderId, nextStatus);
      setMessage(`Pedido movido para ${ORDER_STATUS_PT[nextStatus]}`);
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Erro na transição');
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

        {tab === 'orders' &&
          orders.map((order) => (
            <View key={order.id} style={s.card}>
              <View style={s.rowBetween}>
                <Text style={s.cardTitle}>{order.storeName}</Text>
                <Text style={s.badge}>{ORDER_STATUS_PT[order.status] || order.status}</Text>
              </View>
              <Text style={s.subtitle}>
                {order.deliveryAddress} · R$ {order.totalAmount.toFixed(2)}
              </Text>
              <View style={s.row}>
                {order.allowedNextStatuses.map((next) => (
                  <TouchableOpacity key={next} style={s.buttonPrimary} onPress={() => advance(order.id, next)}>
                    <Text style={s.buttonText}>{ORDER_STATUS_PT[next] || next}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ))}

        {tab === 'stores' && (
          <>
            <View style={s.card}>
              <Text style={s.cardTitle}>Nova Loja</Text>
              <TextInput style={s.input} placeholder="Nome da Loja" placeholderTextColor="#64748b" value={storeName} onChangeText={setStoreName} />
              <TextInput style={s.input} placeholder="Categoria" placeholderTextColor="#64748b" value={storeCategory} onChangeText={setStoreCategory} />
              <TextInput style={s.input} placeholder="Endereço" placeholderTextColor="#64748b" value={storeAddress} onChangeText={setStoreAddress} />
              <TouchableOpacity style={s.buttonPrimary} onPress={createStore}>
                <Text style={s.buttonText}>Cadastrar Loja</Text>
              </TouchableOpacity>
            </View>

            {stores.map((store) => (
              <View key={store.id} style={s.card}>
                <Text style={s.cardTitle}>
                  {store.name} ({store.menuItems.length} itens)
                </Text>
                <TextInput style={s.input} placeholder="Novo item do cardápio" placeholderTextColor="#64748b" value={itemName} onChangeText={setItemName} />
                <TextInput style={s.input} placeholder="Preço (ex: 34.90)" placeholderTextColor="#64748b" keyboardType="decimal-pad" value={itemPrice} onChangeText={setItemPrice} />
                <TouchableOpacity style={s.buttonSuccess} onPress={() => addItem(store.id)}>
                  <Text style={s.buttonText}>Adicionar Item</Text>
                </TouchableOpacity>
              </View>
            ))}
          </>
        )}
      </ScrollView>

      <View style={s.tabBar}>
        <TouchableOpacity style={[s.tabItem, tab === 'orders' && s.tabActive]} onPress={() => setTab('orders')}>
          <Text style={s.buttonText}>Pedidos ({orders.length})</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.tabItem, tab === 'stores' && s.tabActive]} onPress={() => setTab('stores')}>
          <Text style={s.buttonText}>Lojas ({stores.length})</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
