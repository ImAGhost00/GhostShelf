import React, { useEffect, useState } from 'react';
import { getDownloads, removeDownload, updateDownloadStatus } from '@/services/api';
import { useToast } from '@/components/ToastProvider';
import type { DownloadItem } from '@/types';

const statusIcon: Record<string, string> = {
  queued:      '🕐',
  downloading: '⬇️',
  done:        '✅',
  failed:      '❌',
  cancelled:   '🚫',
};

const DownloadsPage: React.FC = () => {
  const { toast } = useToast();
  const [items, setItems] = useState<DownloadItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = (silent = false) => {
    if (!silent) setLoading(true);
    getDownloads()
      .then(setItems)
      .catch(() => toast('Failed to load downloads', 'error'))
      .finally(() => {
        if (!silent) setLoading(false);
      });
  };

  useEffect(() => {
    load();
    const interval = window.setInterval(() => load(true), 5000);
    return () => window.clearInterval(interval);
  }, []);

  const formatEta = (eta?: number) => {
    if (!eta || eta < 0) return null;
    const minutes = Math.floor(eta / 60);
    const seconds = eta % 60;
    if (minutes <= 0) return `${seconds}s left`;
    return `${minutes}m ${seconds}s left`;
  };

  const formatSpeed = (speed?: number) => {
    if (!speed || speed <= 0) return null;
    const mib = speed / (1024 * 1024);
    return `${mib.toFixed(1)} MiB/s`;
  };

  const handleCancel = async (id: number) => {
    try {
      const updated = await updateDownloadStatus(id, 'cancelled');
      setItems(prev => prev.map(i => (i.id === id ? updated : i)));
    } catch {
      toast('Failed to cancel', 'error');
    }
  };

  const handleRemove = async (id: number) => {
    try {
      await removeDownload(id);
      setItems(prev => prev.filter(i => i.id !== id));
    } catch {
      toast('Failed to remove', 'error');
    }
  };

  const active = items.filter(i => i.status === 'queued' || i.status === 'downloading');
  const done   = items.filter(i => i.status === 'done' || i.status === 'cancelled' || i.status === 'failed');

  const renderItem = (item: DownloadItem) => (
    <div key={item.id} className="download-item">
      <span className="download-status-icon">{statusIcon[item.status] || '❓'}</span>
      <div className="download-info">
        <div className="download-title">{item.title}</div>
        <div className="download-detail">
          <span className={`tag ${item.content_type}`} style={{ fontSize: '0.65rem' }}>
            {item.content_type}
          </span>
          {' '}
          {item.download_url ? (
            <a href={item.download_url} target="_blank" rel="noopener noreferrer"
               style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Download link ↗
            </a>
          ) : (
            <span style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }}>No direct URL</span>
          )}
          {item.error_message && (
            <span style={{ fontSize: '0.72rem', color: 'var(--red)', marginLeft: '0.5rem' }}>
              {item.error_message}
            </span>
          )}
        </div>
        {typeof item.progress === 'number' && item.status !== 'done' && item.status !== 'failed' && item.status !== 'cancelled' && (
          <div style={{ marginTop: '0.45rem' }}>
            <div style={{ height: '8px', background: 'var(--surface-3)', borderRadius: '999px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${Math.max(0, Math.min(100, item.progress * 100))}%`,
                  height: '100%',
                  background: 'linear-gradient(90deg, #1f7a8c 0%, #7bd389 100%)',
                }}
              />
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <span>{Math.round(item.progress * 100)}%</span>
              {item.state && <span>{item.state}</span>}
              {formatSpeed(item.speed) && <span>{formatSpeed(item.speed)}</span>}
              {formatEta(item.eta) && <span>{formatEta(item.eta)}</span>}
            </div>
          </div>
        )}
      </div>
      <div style={{ display: 'flex', gap: '0.35rem' }}>
        {(item.status === 'queued' || item.status === 'downloading') && (
          <button className="btn btn-ghost btn-sm" onClick={() => handleCancel(item.id)}>Cancel</button>
        )}
        <button className="btn btn-danger btn-icon" onClick={() => handleRemove(item.id)}>🗑️</button>
      </div>
    </div>
  );

  return (
    <>
      <div className="page-header">
        <h1>⬇️ Downloads</h1>
        <p>Track your queued and completed downloads</p>
      </div>

      <div className="page-body">
        {loading && (
          <div style={{ textAlign: 'center', padding: '2rem' }}><span className="spinner" /></div>
        )}

        {!loading && items.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">⬇️</div>
            <h3>No downloads yet</h3>
            <p>Add items to your watchlist and queue downloads from there</p>
          </div>
        )}

        {active.length > 0 && (
          <>
            <h2 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.6rem' }}>
              Active ({active.length})
            </h2>
            <div className="downloads-list">{active.map(renderItem)}</div>
          </>
        )}

        {done.length > 0 && (
          <div style={{ marginTop: '1.5rem' }}>
            <h2 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.6rem' }}>
              History ({done.length})
            </h2>
            <div className="downloads-list">{done.map(renderItem)}</div>
          </div>
        )}
      </div>
    </>
  );
};

export default DownloadsPage;
