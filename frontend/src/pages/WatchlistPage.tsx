import React, { useEffect, useState } from 'react';
import { getWatchlist, removeFromWatchlist, updateWatchlistItem } from '@/services/api';
import { useToast } from '@/components/ToastProvider';
import type { WatchlistItem, ItemStatus } from '@/types';
import { startDirectDownload, startProwlarrAutoDownload } from '@/services/api';

type Filter = 'all' | 'book' | 'comic' | 'manga';

const statusOptions: ItemStatus[] = ['wanted', 'found', 'downloading', 'downloaded', 'failed'];

const WatchlistPage: React.FC = () => {
  const { toast } = useToast();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [filter, setFilter] = useState<Filter>('all');
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    getWatchlist()
      .then(setItems)
      .catch(() => toast('Failed to load watchlist', 'error'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleRemove = async (id: number, title: string) => {
    try {
      await removeFromWatchlist(id);
      setItems(prev => prev.filter(i => i.id !== id));
      toast(`Removed "${title}"`, 'info');
    } catch {
      toast('Failed to remove item', 'error');
    }
  };

  const handleStatusChange = async (id: number, status: ItemStatus) => {
    try {
      const updated = await updateWatchlistItem(id, { status });
      setItems(prev => prev.map(i => (i.id === id ? updated : i)));
    } catch {
      toast('Failed to update status', 'error');
    }
  };

  const handleDirectDownload = async (item: WatchlistItem) => {
    const input = window.prompt(
      `Paste direct URL and optional mirrors for ${item.title}\n` +
      `Format: primary_url, mirror_url_1, mirror_url_2`
    );
    if (!input) return;
    const parts = input
      .split(',')
      .map(p => p.trim())
      .filter(Boolean);
    if (parts.length === 0) return;
    const [url, ...mirrors] = parts;
    try {
      await startDirectDownload({
        title: item.title,
        content_type: item.content_type,
        download_url: url,
        mirror_urls: mirrors,
        watchlist_id: item.id,
      });
      toast(`Download started: ${item.title}`, 'success');
      await handleStatusChange(item.id, 'downloading');
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Direct download failed', 'error');
    }
  };

  const handleProwlarrDownload = async (item: WatchlistItem) => {
    try {
      await startProwlarrAutoDownload({
        title: item.title,
        content_type: item.content_type,
        watchlist_id: item.id,
      });
      toast(`Prowlarr download started: ${item.title}`, 'success');
      await handleStatusChange(item.id, 'downloading');
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Prowlarr download failed', 'error');
    }
  };

  const filtered = filter === 'all' ? items : items.filter(i => i.content_type === filter);

  return (
    <>
      <div className="page-header">
        <h1>👁️ Watchlist</h1>
        <p>{items.length} item{items.length !== 1 ? 's' : ''} tracked</p>
      </div>

      <div className="page-body">
        <div className="section-header">
          {/* Filter tabs */}
          <div className="tabs">
            {(['all', 'book', 'comic', 'manga'] as Filter[]).map(f => (
              <button key={f} className={`tab${filter === f ? ' active' : ''}`} onClick={() => setFilter(f)}>
                {f === 'all' ? 'All' : f === 'book' ? '📖 Books' : f === 'comic' ? '🦸 Comics' : '🎌 Manga'}
              </button>
            ))}
          </div>
        </div>

        {loading && (
          <div style={{ textAlign: 'center', padding: '2rem' }}><span className="spinner" /></div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">👁️</div>
            <h3>Nothing here</h3>
            <p>Search for books or comics and add them to your watchlist</p>
          </div>
        )}

        <div className="watchlist-list">
          {filtered.map(item => (
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
                  {item.year && (
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }}>{item.year}</span>
                  )}
                  {item.source && (
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }}>
                      via {item.source.replace('_', ' ')}
                    </span>
                  )}
                </div>
              </div>

              <div className="watchlist-actions">
                <select
                  value={item.status}
                  onChange={e => handleStatusChange(item.id, e.target.value as ItemStatus)}
                  style={{ fontSize: '0.78rem', padding: '0.3rem 0.5rem' }}
                >
                  {statusOptions.map(s => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <button
                  className="btn btn-ghost btn-sm"
                  title="Auto-download from Prowlarr"
                  onClick={() => handleProwlarrDownload(item)}
                >
                  Prowlarr
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  title="Download from direct URL"
                  onClick={() => handleDirectDownload(item)}
                >
                  Direct
                </button>
                <button
                  className="btn btn-danger btn-icon"
                  title="Remove"
                  onClick={() => handleRemove(item.id, item.title)}
                >
                  🗑️
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
};

export default WatchlistPage;
