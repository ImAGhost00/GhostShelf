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

  const formatBytes = (bytes?: number) => {
    if (!bytes || bytes <= 0) return null;
    const gib = 1024 * 1024 * 1024;
    const mib = 1024 * 1024;
    if (bytes >= gib) return `${(bytes / gib).toFixed(2)} GiB`;
    return `${(bytes / mib).toFixed(1)} MiB`;
  };

  const progressPercent = (item: DownloadItem) => {
    const progress = typeof item.progress === 'number' ? item.progress : item.status === 'done' ? 1 : 0;
    return Math.max(0, Math.min(100, Math.round(progress * 100)));
  };

  const progressColor = (item: DownloadItem) => {
    if (item.status === 'failed' || item.status === 'cancelled') return 'linear-gradient(90deg, #8f2d56 0%, #d1495b 100%)';
    if (item.status === 'done') return 'linear-gradient(90deg, #2d6a4f 0%, #74c69d 100%)';
    if (item.state === 'stalledDL' || item.state === 'metaDL') return 'linear-gradient(90deg, #b08900 0%, #ffcb77 100%)';
    return 'linear-gradient(90deg, #1f7a8c 0%, #7bd389 100%)';
  };

  const formatTimestamp = (value?: string | null) => {
    if (!value) return null;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    return date.toLocaleString();
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

  const active = [...items]
    .filter(i => i.status === 'queued' || i.status === 'downloading')
    .sort((a, b) => (b.updated_at || b.created_at || '').localeCompare(a.updated_at || a.created_at || ''));
  const done = [...items]
    .filter(i => i.status === 'done' || i.status === 'cancelled' || i.status === 'failed')
    .sort((a, b) => (b.updated_at || b.created_at || '').localeCompare(a.updated_at || a.created_at || ''));

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
          <span className={`badge badge-${item.status === 'done' ? 'downloaded' : item.status === 'failed' ? 'failed' : item.status === 'cancelled' ? 'failed' : 'downloading'}`}>
            {item.status === 'done' ? 'completed' : item.status}
          </span>
          {item.category && (
            <>
              {' '}
              <span className="tag" style={{ fontSize: '0.65rem' }}>{item.category}</span>
            </>
          )}
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
        {(typeof item.progress === 'number' || item.status === 'queued' || item.status === 'downloading' || item.status === 'done') && (
          <div style={{ marginTop: '0.45rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', alignItems: 'center', marginBottom: '0.3rem' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                qBittorrent status: {item.state_label || item.state || (item.status === 'done' ? 'Completed' : item.status)}
              </span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                {progressPercent(item)}%
              </span>
            </div>
            <div style={{ height: '8px', background: 'var(--surface-3)', borderRadius: '999px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${progressPercent(item)}%`,
                  height: '100%',
                  background: progressColor(item),
                  transition: 'width 240ms ease',
                }}
              />
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              {item.state_label && <span>{item.state_label}</span>}
              {formatSpeed(item.speed) && <span>{formatSpeed(item.speed)}</span>}
              {formatSpeed(item.upload_speed) && <span>up {formatSpeed(item.upload_speed)}</span>}
              {formatEta(item.eta) && <span>{formatEta(item.eta)}</span>}
              {formatBytes(item.downloaded) && item.size ? (
                <span>{formatBytes(item.downloaded)} / {formatBytes(item.size)}</span>
              ) : null}
              {formatBytes(item.amount_left) && item.status !== 'done' ? <span>{formatBytes(item.amount_left)} left</span> : null}
              {typeof item.seeders === 'number' ? <span>{item.seeders} seeders</span> : null}
              {typeof item.leechers === 'number' ? <span>{item.leechers} peers</span> : null}
              {typeof item.ratio === 'number' && item.ratio > 0 ? <span>ratio {item.ratio.toFixed(2)}</span> : null}
            </div>
            {(item.hash || item.save_path) && (
              <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)', marginTop: '0.25rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                {item.hash && <span>hash {item.hash.slice(0, 12)}...</span>}
                {item.save_path && <span>{item.save_path}</span>}
              </div>
            )}
          </div>
        )}
        <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)', marginTop: '0.35rem', display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          {formatTimestamp(item.created_at) && <span>Queued {formatTimestamp(item.created_at)}</span>}
          {item.status === 'done' && formatTimestamp(item.updated_at) && <span>Completed {formatTimestamp(item.updated_at)}</span>}
          {item.status === 'failed' && formatTimestamp(item.updated_at) && <span>Failed {formatTimestamp(item.updated_at)}</span>}
          {item.status === 'cancelled' && formatTimestamp(item.updated_at) && <span>Cancelled {formatTimestamp(item.updated_at)}</span>}
        </div>
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
            <p>Add items to your request list and queue downloads from there</p>
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
