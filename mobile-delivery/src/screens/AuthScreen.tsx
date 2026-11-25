import { useState } from 'react';
import { ScrollView, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { mobileApi, persistSession } from '../services/api';
import { themeStyles as s } from '../styles/theme';
import type { AuthTokenResponse, UserRole } from '../types/models';

interface Props {
  onAuthenticated: (session: AuthTokenResponse) => void;
}

export function AuthScreen({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('customer@yourfood.ai');
  const [password, setPassword] = useState('Customer@123');
  const [role, setRole] = useState<UserRole>('Customer');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setError(null);
    setLoading(true);
    try {
      const session =
        mode === 'login'
          ? await mobileApi.login(email, password)
          : await mobileApi.register(fullName, email, password, role);
      await persistSession(session);
      onAuthenticated(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro de autenticação');
    } finally {
      setLoading(false);
    }
  };

  const handleOAuth = async (provider: string) => {
    setError(null);
    setLoading(true);
    try {
      const targetEmail = role === 'StoreOwner' ? `mobile.merchant.${provider}@yourfood.ai` : `mobile.customer.${provider}@yourfood.ai`;
      const session = await mobileApi.oauthExternalLogin(provider, targetEmail, `Usuário ${provider}`, role);
      await persistSession(session);
      onAuthenticated(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro OAuth2');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={s.container}>
      <View style={s.card}>
        <Text style={s.title}>YourFood.AI Mobile</Text>
        <Text style={s.subtitle}>Delivery & Coleta de Dados para Pipeline BERTimbau ABSA</Text>

        <View style={s.row}>
          <TouchableOpacity
            style={[s.buttonSecondary, mode === 'login' && s.tabActive]}
            onPress={() => setMode('login')}
          >
            <Text style={s.buttonText}>Entrar</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[s.buttonSecondary, mode === 'register' && s.tabActive]}
            onPress={() => setMode('register')}
          >
            <Text style={s.buttonText}>Cadastrar</Text>
          </TouchableOpacity>
        </View>

        {error && <Text style={s.errorText}>{error}</Text>}

        {mode === 'register' && (
          <TextInput
            style={s.input}
            placeholder="Nome completo"
            placeholderTextColor="#64748b"
            value={fullName}
            onChangeText={setFullName}
          />
        )}

        <TextInput
          style={s.input}
          placeholder="E-mail"
          placeholderTextColor="#64748b"
          autoCapitalize="none"
          value={email}
          onChangeText={setEmail}
        />

        <TextInput
          style={s.input}
          placeholder="Senha"
          placeholderTextColor="#64748b"
          secureTextEntry
          value={password}
          onChangeText={setPassword}
        />

        <View style={s.row}>
          <TouchableOpacity
            style={[s.buttonSecondary, role === 'Customer' && s.tabActive]}
            onPress={() => setRole('Customer')}
          >
            <Text style={s.buttonText}>Cliente</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[s.buttonSecondary, role === 'StoreOwner' && s.tabActive]}
            onPress={() => setRole('StoreOwner')}
          >
            <Text style={s.buttonText}>Restaurante</Text>
          </TouchableOpacity>
        </View>

        <TouchableOpacity style={s.buttonPrimary} onPress={handleSubmit} disabled={loading}>
          <Text style={s.buttonText}>{loading ? 'Carregando...' : mode === 'login' ? 'Entrar (JWT)' : 'Criar Conta'}</Text>
        </TouchableOpacity>

        <View style={s.row}>
          <TouchableOpacity style={[s.buttonSecondary, { flex: 1 }]} onPress={() => handleOAuth('google')}>
            <Text style={s.buttonText}>OAuth2 Google</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[s.buttonSecondary, { flex: 1 }]} onPress={() => handleOAuth('github')}>
            <Text style={s.buttonText}>OAuth2 GitHub</Text>
          </TouchableOpacity>
        </View>
      </View>
    </ScrollView>
  );
}
