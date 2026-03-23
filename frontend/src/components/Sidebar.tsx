import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';

interface NavItem { to: string; icon: string; label: string; }
interface User { username: string; email?: string }

const nav: NavItem[] = [
  { to: '/',           icon: '🏠', label: 'Dashboard' },
  { to: '/search',     icon: '🔍', label: 'Search' },
  { to: '/watchlist',  icon: '👁️',  label: 'Watchlist' },
  { to: '/downloads',  icon: '⬇️',  label: 'Downloads' },
];

const integrations: NavItem[] = [
  { to: '/komga',    icon: '📚', label: 'Komga' },
  { to: '/settings', icon: '⚙️',  label: 'Settings' },
];

const Sidebar: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const userStr = localStorage.getItem('user');
    if (userStr) {
      setUser(JSON.parse(userStr));
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    navigate('/login');
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <img className="logo-icon" src="/logo/Ghost-Only.png" alt="GhostShelf logo" />
        <span className="logo-text">GhostShelf</span>
      </div>

      <span className="nav-section-label">Navigate</span>
      {nav.map(n => (
        <NavLink
          key={n.to}
          to={n.to}
          end={n.to === '/'}
          className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
        >
          <span className="nav-icon">{n.icon}</span>
          {n.label}
        </NavLink>
      ))}

      <span className="nav-section-label" style={{ marginTop: '1rem' }}>Integrations</span>
      {integrations.map(n => (
        <NavLink
          key={n.to}
          to={n.to}
          className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
        >
          <span className="nav-icon">{n.icon}</span>
          {n.label}
        </NavLink>
      ))}

      {/* User info and logout button */}
      {user && (
        <div style={{
          marginTop: 'auto',
          paddingTop: '1rem',
          borderTop: '1px solid var(--border-color)',
          fontSize: '0.875rem',
        }}>
          <div style={{ padding: '0.5rem 0.75rem', color: 'var(--text-muted)', wordBreak: 'break-word' }}>
            👤 {user.username}
          </div>
          <button
            onClick={handleLogout}
            style={{
              width: '100%',
              padding: '0.5rem 0.75rem',
              background: 'var(--color-error)',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.875rem',
              marginTop: '0.5rem',
            }}
          >
            🚪 Logout
          </button>
        </div>
      )}
    </aside>
  );
};

export default Sidebar;
