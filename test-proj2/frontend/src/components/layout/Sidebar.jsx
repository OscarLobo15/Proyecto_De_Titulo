import { Gauge, Settings } from 'lucide-react';
import { NavLink } from 'react-router-dom';

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">RA</span>
        <span>Test Proj2</span>
      </div>
      <nav>
        <NavLink to="/app/dashboard">
          <Gauge size={18} />
          Dashboard
        </NavLink>
        <NavLink to="/app/settings">
          <Settings size={18} />
          Settings
        </NavLink>
      </nav>
    </aside>
  );
}

