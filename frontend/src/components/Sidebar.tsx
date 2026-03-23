import React from 'react';
import { NavLink } from 'react-router-dom';

interface NavItem { to: string; icon: string; label: string; }

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
    </aside>
  );
};

export default Sidebar;
