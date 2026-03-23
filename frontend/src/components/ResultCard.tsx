import React from 'react';
import type { SearchResult } from '@/types';

interface Props {
  item: SearchResult;
  onAdd: (item: SearchResult) => void;
  onAutoDownload?: (item: SearchResult) => void;
  onManualSearch?: (item: SearchResult) => void;
  autoDownloading?: boolean;
  downloadDisabled?: boolean;
  manualSearching?: boolean;
  ownedLabel?: string | null;
  alreadyAdded?: boolean;
}

const typeLabel: Record<string, string> = {
  book: 'Book',
  comic: 'Comic',
  manga: 'Manga',
};

const ResultCard: React.FC<Props> = ({ item, onAdd, onAutoDownload, onManualSearch, autoDownloading, downloadDisabled, manualSearching, ownedLabel, alreadyAdded }) => {
  const typeClass = item.content_type;
  const sourceLabels = item.available_sources?.length ? item.available_sources : [item.source];

  return (
    <div className="card">
      {item.cover_url ? (
        <img
          className="card-cover"
          src={item.cover_url}
          alt={item.title}
          loading="lazy"
          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
        />
      ) : (
        <div className="card-cover-placeholder">
          {item.content_type === 'book' ? '📖' : item.content_type === 'manga' ? '🎌' : '🦸'}
        </div>
      )}

      <div className="card-body">
        <div className="card-title">{item.title}</div>
        {item.author && <div className="card-author">{item.author}</div>}
        <div className="card-meta">
          {item.year && <span>{item.year} · </span>}
          <span style={{ textTransform: 'capitalize' }}>{(item.source || '').replace('_', ' ')}</span>
        </div>
        <div className="card-tags">
          <span className={`tag ${typeClass}`}>{typeLabel[item.content_type]}</span>
          {item.genres.slice(0, 2).map(g => (
            <span key={g} className="tag">{g}</span>
          ))}
          {sourceLabels.map(source => (
            <span key={source} className="tag">{source.replace(/_/g, ' ')}</span>
          ))}
        </div>
      </div>

      <div className="card-actions" style={{ flexWrap: 'wrap' }}>
        <button
          className="btn btn-ghost btn-sm"
          disabled={downloadDisabled}
          onClick={() => onAutoDownload?.(item)}
          style={{ flex: 1 }}
        >
          {autoDownloading ? 'Searching...' : downloadDisabled ? (ownedLabel ? 'Already Owned' : 'Downloading...') : 'Auto Search'}
        </button>
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => onManualSearch?.(item)}
          disabled={manualSearching}
          style={{ flex: 1 }}
        >
          {manualSearching ? 'Searching...' : 'Manual Search'}
        </button>
        <button
          className={`btn btn-sm ${alreadyAdded ? 'btn-ghost' : 'btn-primary'}`}
          disabled={alreadyAdded}
          onClick={() => onAdd(item)}
          style={{ flex: 1 }}
        >
          {alreadyAdded ? '✓ Requested' : '+ Request'}
        </button>
      </div>

      {ownedLabel && (
        <div style={{ padding: '0 0.75rem 0.75rem', fontSize: '0.72rem', color: 'var(--green)' }}>
          In library: {ownedLabel}
        </div>
      )}
    </div>
  );
};

export default ResultCard;
