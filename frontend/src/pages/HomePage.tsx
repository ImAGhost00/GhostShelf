import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getWatchlist, getDownloads, getCwaStatus, getKomgaStatus } from '@/services/api';
import type { WatchlistItem, DownloadItem } from '@/types';

const HomePage: React.FC = () => {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const [cwaOk, setCwaOk] = useState<boolean | null>(null);
  const [komgaOk, setKomgaOk] = useState<boolean | null>(null);

  useEffect(() => {
    getWatchlist().then(setWatchlist).catch(() => {});
    getDownloads().then(setDownloads).catch(() => {});
    getCwaStatus().then(r => setCwaOk(r.connected)).catch(() => setCwaOk(false));
    getKomgaStatus().then(r => setKomgaOk(r.connected)).catch(() => setKomgaOk(false));
  }, []);

  const books  = watchlist.filter(i => i.content_type === 'book').length;
  const comics = watchlist.filter(i => i.content_type === 'comic').length;
  const manga  = watchlist.filter(i => i.content_type === 'manga').length;
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
        <h1>👻 GhostShelf</h1>
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
            <span className="stat-value">{books}</span>
            <span className="stat-label">Books tracked</span>
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
            <span className="stat-value">{watchlist.length}</span>
            <span className="stat-label">Total watchlist</span>
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
            <Link to="/watchlist" className="btn btn-ghost">👁️ View Watchlist</Link>
            <Link to="/downloads" className="btn btn-ghost">⬇️ Manage Downloads</Link>
            <Link to="/settings" className="btn btn-ghost">⚙️ Configure</Link>
          </div>
        </div>

        {/* Recent watchlist */}
        {watchlist.length > 0 && (
          <div style={{ marginTop: '1.5rem' }}>
            <div className="section-header">
              <h2 style={{ fontSize: '1rem', fontWeight: 700 }}>Recently Added</h2>
              <Link to="/watchlist" className="btn btn-ghost btn-sm">View all</Link>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {watchlist.slice(0, 5).map(item => (
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
