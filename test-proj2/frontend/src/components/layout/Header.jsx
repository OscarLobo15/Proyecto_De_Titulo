import { LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext.jsx';

export function Header() {
  const { user, logout } = useAuth();

  return (
    <header className="topbar">
      <div>
        <span className="eyebrow">Test Proj2</span>
        <h1>Panel operativo</h1>
      </div>
      <div className="user-menu">
        <span>{user?.email || user?.displayName || 'Usuario'}</span>
        <button className="icon-button" type="button" onClick={logout} title="Cerrar sesion">
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
}

