import { useEffect, useState } from 'react';
import { SafeAreaView, Text, TouchableOpacity, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { loadSession, persistSession } from './src/services/api';
import { AuthScreen } from './src/screens/AuthScreen';
import { CustomerFlowScreen } from './src/screens/CustomerFlowScreen';
import { MerchantFlowScreen } from './src/screens/MerchantFlowScreen';
import { themeStyles as s } from './src/styles/theme';
import type { AuthTokenResponse } from './src/types/models';

export default function App() {
  const [session, setSession] = useState<AuthTokenResponse | null>(null);

  useEffect(() => {
    loadSession().then(setSession);
  }, []);

  const handleLogout = async () => {
    await persistSession(null);
    setSession(null);
  };

  return (
    <SafeAreaView style={s.safe}>
      <StatusBar style="light" />
      {!session ? (
        <AuthScreen onAuthenticated={setSession} />
      ) : (
        <>
          <View style={s.header}>
            <View>
              <Text style={s.title}>YourFood.AI</Text>
              <Text style={s.subtitle}>
                {session.user.fullName} · {session.user.role}
              </Text>
            </View>
            <TouchableOpacity style={s.buttonSecondary} onPress={handleLogout}>
              <Text style={s.buttonText}>Sair</Text>
            </TouchableOpacity>
          </View>
          {session.user.role === 'StoreOwner' ? <MerchantFlowScreen /> : <CustomerFlowScreen />}
        </>
      )}
    </SafeAreaView>
  );
}
