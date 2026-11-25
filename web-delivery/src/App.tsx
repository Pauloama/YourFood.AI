import { LogOut, UtensilsCrossed } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AuthView } from './components/AuthView';
import { CustomerDeliveryView } from './components/CustomerDeliveryView';
import { MerchantPortalView } from './components/MerchantPortalView';

function DeliveryShell() {
  const { user, logout } = useAuth();

  if (!user) return <AuthView />;

  const initials = user.fullName
    .split(' ')
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');

  return (
    <div>
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <UtensilsCrossed size={19} />
          </div>
          <span>
            YourFood<span className="brand-accent">.AI</span>
          </span>
        </div>
        <div className="nav-actions">
          <div className="user-pill">
            <span className="user-avatar">{initials || 'YF'}</span>
            <span className="user-name">{user.fullName}</span>
            <span className="badge badge-info">{user.role === 'StoreOwner' ? 'Restaurante' : 'Cliente'}</span>
          </div>
          <button className="btn-secondary" onClick={logout}>
            <LogOut size={15} /> Sair
          </button>
        </div>
      </header>
      <main className="container">
        {user.role === 'StoreOwner' ? <MerchantPortalView /> : <CustomerDeliveryView />}
      </main>
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <DeliveryShell />
    </AuthProvider>
  );
}
