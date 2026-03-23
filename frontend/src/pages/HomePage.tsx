import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getRequests, getDownloads, getCwaStatus, getKomgaStatus } from '@/services/api';
import type { RequestItem, DownloadItem } from '@/types';

const HomePage: React.FC = () => {
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const [cwaOk, setCwaOk] = useState<boolean | null>(null);
  const [komgaOk, setKomgaOk] = useState<boolean | null>(null);

  useEffect(() => {
    getRequests().then(setRequests).catch(() => {});
    getDownloads().then(setDownloads).catch(() => {});
    getCwaStatus().then(r => setCwaOk(r.connected)).catch(() => setCwaOk(false));
    getKomgaStatus().then(r => setKomgaOk(r.connected)).catch(() => setKomgaOk(false));
  }, []);

  const books  = requests.filter(i => i.content_type === 'book').length;
  const comics = requests.filter(i => i.content_type === 'comic').length;
  const manga  = requests.filter(i => i.content_type === 'manga').length;
  const active = downloads.filter(d => d.status === 'queued' || d.status === 'downloading').length;

  const chip = (ok: boolean | null, label: string) => {
    const cls = ok === null ? 'unknown' : ok ? 'connected' : 'disconnected';
    const txt = ok === null ? 'Checking…' : ok ? 'Connected' : 'Disconnected';
    return (
      <span className={`status-chip ${cls}`}>
        <span className="dot" />{label}: {txt}
      </span>
    );
  };

  return (
    <>
      <div className="page-header">
        <h1 className="brand-title">
          <img src="/logo/Ghost-Only.png" alt="GhostShelf logo" />
          <span>GhostShelf</span>
        </h1>
        <p>Your unified library tracker for books, comics &amp; manga</p>
      </div>

      <div className="page-body">
        {/* Integration status */}
        <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
          {chip(cwaOk, 'CWA')}
          {chip(komgaOk, 'Komga')}
        </div>

        {/* Stats */}
        <div className="stat-grid">
          <div className="stat-card">
            <span className="stat-icon">📖</span>
            <span className="stat-value">{requests.length}</span>
            <span className="stat-label">Total requests</span>
          </div>
          <div className="stat-card">
            <span className="stat-icon">🦸</span>
            <span className="stat-value">{comics}</span>
            <span className="stat-label">Comics tracked</span>
          </div>
          <div className="stat-card">
            <span className="stat-icon">🎌</span>
            <span className="stat-value">{manga}</span>
            <span className="stat-label">Manga tracked</span>
          </div>
          <div className="stat-card">
            <span className="stat-icon">⬇️</span>
            <span className="stat-value">{active}</span>
            <span className="stat-label">Active downloads</span>
          </div>
          <div className="stat-card">
            <span className="stat-icon">👁️</span>
            <span className="stat-value">{requests.length}</span>
            <span className="stat-label">Total requests</span>
          </div>
        </div>

        {/* Quick links */}
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-soft)',
            borderRadius: 'var(--radius-lg)',
            padding: '1.4rem',
          }}
        >
          <h2 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem' }}>Quick Actions</h2>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <Link to="/search" className="btn btn-primary">🔍 Search Books &amp; Comics</Link>
            <Link to="/requests" className="btn btn-ghost">📝 View Request List</Link>
            <Link to="/library" className="btn btn-ghost">📚 View Library</Link>
            <Link to="/downloads" className="btn btn-ghost">⬇️ Manage Downloads</Link>
            <Link to="/settings" className="btn btn-ghost">⚙️ Configure</Link>
          </div>
        </div>

        {/* Recent requests */}
        {requests.length > 0 && (
          <div style={{ marginTop: '1.5rem' }}>
            <div className="section-header">
              <h2 style={{ fontSize: '1rem', fontWeight: 700 }}>Recent Requests</h2>
              <Link to="/requests" className="btn btn-ghost btn-sm">View all</Link>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {requests.slice(0, 5).map(item => (
                <div key={item.id} className="watchlist-item">
                  {item.cover_url ? (
                    <img className="watchlist-thumb" src={item.cover_url} alt={item.title} />
                  ) : (
                    <div className="watchlist-thumb-placeholder">
                      {item.content_type === 'book' ? '📖' : item.content_type === 'manga' ? '🎌' : '🦸'}
                    </div>
                  )}
                  <div className="watchlist-info">
                    <div className="watchlist-title">{item.title}</div>
                    {item.author && <div className="watchlist-author">{item.author}</div>}
                    <div className="watchlist-meta">
                      <span className={`tag ${item.content_type}`} style={{ fontSize: '0.68rem' }}>
                        {item.content_type}
                      </span>
                      <span className={`badge badge-${item.status}`}>{item.status}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
};

export default HomePage;
