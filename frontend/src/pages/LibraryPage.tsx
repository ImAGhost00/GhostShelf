import React, { useEffect, useMemo, useState } from 'react';
import { getLibraryOverview } from '@/services/api';
import { useToast } from '@/components/ToastProvider';
import type { LibraryOverview, LibraryOwnedItem } from '@/types';

type Tab = 'all' | 'komga' | 'calibre';

const LibraryPage: React.FC = () => {
  const { toast } = useToast();
  const [overview, setOverview] = useState<LibraryOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>('all');
  const [query, setQuery] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const data = await getLibraryOverview();
      setOverview(data);
      if (data.komga.error) {
        toast(`Komga library fetch issue: ${data.komga.error}`, 'error');
      }
      if (data.calibre.error) {
        toast(`Calibre library fetch issue: ${data.calibre.error}`, 'error');
      }
    } catch {
      toast('Failed to load library contents', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const rows = useMemo(() => {
    if (!overview) return [];
    let merged: LibraryOwnedItem[] = [];
    if (tab === 'all' || tab === 'komga') {
      merged = merged.concat(overview.komga.items);
    }
    if (tab === 'all' || tab === 'calibre') {
      merged = merged.concat(overview.calibre.items);
    }

    const q = query.trim().toLowerCase();
    if (!q) return merged;
    return merged.filter(item => {
      const haystack = `${item.title} ${item.author} ${item.library} ${item.source}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [overview, tab, query]);

  return (
    <>
      <div className="page-header">
        <h1>📚 Library</h1>
        <p>Browse what already exists in your Komga and Calibre libraries</p>
      </div>

      <div className="page-body">
        <div className="tabs" style={{ marginBottom: '0.9rem' }}>
          {(['all', 'komga', 'calibre'] as Tab[]).map(t => (
            <button key={t} className={`tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
              {t === 'all' ? 'All' : t === 'komga' ? 'Komga' : 'Calibre'}
            </button>
          ))}
        </div>

        <div className="search-form" style={{ marginBottom: '1rem' }}>
          <input
            className="search-input"
            value={query}
            placeholder="Filter by title, author, or library..."
            onChange={e => setQuery(e.target.value)}
          />
          <button className="btn btn-ghost" onClick={load} disabled={loading}>
            {loading ? <span className="spinner" /> : 'Refresh'}
          </button>
        </div>

        {overview && (
          <div className="stat-grid" style={{ marginBottom: '1rem' }}>
            <div className="stat-card">
              <span className="stat-icon">📚</span>
              <span className="stat-value">{overview.total}</span>
              <span className="stat-label">Total Library Items</span>
            </div>
            <div className="stat-card">
              <span className="stat-icon">🧭</span>
              <span className="stat-value">{overview.komga.count}</span>
              <span className="stat-label">Komga Series</span>
            </div>
            <div className="stat-card">
              <span className="stat-icon">📗</span>
              <span className="stat-value">{overview.calibre.count}</span>
              <span className="stat-label">Calibre Books</span>
            </div>
          </div>
        )}

        {loading && (
          <div style={{ textAlign: 'center', padding: '2rem' }}><span className="spinner" /></div>
        )}

        {!loading && rows.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">📚</div>
            <h3>No library entries found</h3>
            <p>Connect Komga/CWA in settings, then refresh this page</p>
          </div>
        )}

        <div className="watchlist-list">
          {rows.map(item => (
            <div key={`${item.source}-${item.id}`} className="watchlist-item">
              <div className="watchlist-thumb-placeholder">
                {item.content_type === 'book' ? '📖' : item.content_type === 'manga' ? '🎌' : '🦸'}
              </div>
              <div className="watchlist-info">
                <div className="watchlist-title">{item.title}</div>
                {item.author && <div className="watchlist-author">{item.author}</div>}
                <div className="watchlist-meta">
                  <span className={`tag ${item.content_type}`} style={{ fontSize: '0.68rem' }}>{item.content_type}</span>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{item.source}</span>
                  {item.library && (
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      {item.library}
                    </span>
                  )}
                  {item.books_count > 0 && (
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }}>
                      {item.books_count} file{item.books_count !== 1 ? 's' : ''}
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
};

export default LibraryPage;
