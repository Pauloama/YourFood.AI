import { useState, type FormEvent } from 'react';
import { ShieldCheck, Sparkles, UtensilsCrossed } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import type { UserRole } from '../types/models';

export function AuthView() {
  const { login, register, oauthLogin } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('customer@yourfood.ai');
  const [password, setPassword] = useState('Customer@123');
  const [role, setRole] = useState<UserRole>('Customer');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(fullName, email, password, role);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível concluir o acesso.');
    } finally {
      setLoading(false);
    }
  };

  const handleOAuth = async (provider: string) => {
    setError(null);
    setLoading(true);
    try {
      const targetEmail = role === 'StoreOwner' ? `merchant.${provider}@yourfood.ai` : `cliente.${provider}@yourfood.ai`;
      const targetName = role === 'StoreOwner' ? `Restaurante (${provider})` : `Cliente (${provider})`;
      await oauthLogin(provider, targetEmail, targetName, role);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível entrar via OAuth2.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-split">
      <section className="auth-showcase">
        <div className="row">
          <div className="store-emoji">
            <UtensilsCrossed size={22} color="#ffffff" />
          </div>
          <strong style={{ fontSize: '1.25rem', fontFamily: 'Plus Jakarta Sans' }}>YourFood.AI</strong>
        </div>

        <div className="stack" style={{ gap: '1.1rem' }}>
          <h1>Seu delivery favorito, mais inteligente a cada avaliação.</h1>
          <p>
            Peça nos melhores restaurantes, acompanhe seu pedido passo a passo e compartilhe sua experiência real.
          </p>
          <div className="grid-2 auth-features-grid" style={{ gap: '0.9rem' }}>
            <div className="auth-feature-card">
              <strong>Acompanhamento em Tempo Real</strong>
              <p style={{ fontSize: '0.86rem', marginTop: '0.25rem' }}>
                Veja cada etapa do preparo até a entrega na sua porta com total transparência.
              </p>
            </div>
            <div className="auth-feature-card">
              <div className="row" style={{ gap: '0.35rem' }}>
                <Sparkles size={15} />
                <strong>Avaliações que Importam</strong>
              </div>
              <p style={{ fontSize: '0.86rem', marginTop: '0.25rem' }}>
                Nossa IA entende detalhes de sabor, temperatura, preparo, embalagem e entrega.
              </p>
            </div>
          </div>
        </div>

        <div className="row" style={{ fontSize: '0.84rem', opacity: 0.92 }}>
          <ShieldCheck size={16} /> Acesso protegido com JWT e OAuth2
        </div>
      </section>

      <section className="auth-panel">
        <div className="card auth-card stack">
          <div>
            <h2>{mode === 'login' ? 'Bem-vindo de volta' : 'Crie sua conta'}</h2>
            <p className="muted">Entre como cliente para pedir ou como restaurante para gerenciar.</p>
          </div>

          <div className="tabs" style={{ width: '100%' }}>
            <button
              type="button"
              className={`tab-btn ${mode === 'login' ? 'active' : ''}`}
              style={{ flex: 1 }}
              onClick={() => {
                setMode('login');
                setError(null);
              }}
            >
              Entrar
            </button>
            <button
              type="button"
              className={`tab-btn ${mode === 'register' ? 'active' : ''}`}
              style={{ flex: 1 }}
              onClick={() => {
                setMode('register');
                setError(null);
              }}
            >
              Criar Conta
            </button>
          </div>

          {error && <div className="error-box">{error}</div>}

          <form className="stack" onSubmit={handleSubmit}>
            {mode === 'register' && (
              <div>
                <label className="muted">Nome completo</label>
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Ex: Marina Silva" required />
              </div>
            )}

            <div>
              <label className="muted">E-mail</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>

            <div>
              <label className="muted">Senha</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>

            {mode === 'register' && (
              <div>
                <label className="muted">Tipo de conta</label>
                <select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
                  <option value="Customer">Cliente (Fazer pedidos e avaliar)</option>
                  <option value="StoreOwner">Dono de Restaurante (Gerenciar lojas e cardápios)</option>
                </select>
              </div>
            )}

            <button type="submit" className="btn-primary" style={{ padding: '0.78rem' }} disabled={loading}>
              {loading ? 'Entrando...' : mode === 'login' ? 'Entrar' : 'Criar Conta'}
            </button>
          </form>

          <div className="stack" style={{ gap: '0.6rem' }}>
            <div className="row muted" style={{ fontSize: '0.8rem' }}>
              <ShieldCheck size={15} /> Entrar com provedor OAuth2 ou conta de demonstração
            </div>
            <div className="form-grid-2">
              <button type="button" className="btn-secondary" onClick={() => handleOAuth('google')} disabled={loading}>
                Google
              </button>
              <button type="button" className="btn-secondary" onClick={() => handleOAuth('github')} disabled={loading}>
                GitHub
              </button>
            </div>
            <div className="form-grid-2">
              <button
                type="button"
                className="btn-secondary"
                style={{ fontSize: '0.82rem' }}
                onClick={() => {
                  setMode('login');
                  setEmail('customer@yourfood.ai');
                  setPassword('Customer@123');
                  setRole('Customer');
                  setError(null);
                }}
              >
                Usar Demo Cliente
              </button>
              <button
                type="button"
                className="btn-secondary"
                style={{ fontSize: '0.82rem' }}
                onClick={() => {
                  setMode('login');
                  setEmail('merchant@yourfood.ai');
                  setPassword('Merchant@123');
                  setRole('StoreOwner');
                  setError(null);
                }}
              >
                Usar Demo Restaurante
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
