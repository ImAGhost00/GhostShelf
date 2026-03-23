import React, { useState, useEffect, useRef } from 'react';
import {
  searchBooks,
  searchComics,
  addToRequestList,
  getDownloads,
  getRequests,
  checkOwnedBatch,
  searchProwlarrReleases,
  startDirectDownload,
  startSmartAutoDownload,
} from '@/services/api';
import ResultCard from '@/components/ResultCard';
import { useToast } from '@/components/ToastProvider';
import type { SearchResult, RequestItem, ReleaseSearchResult } from '@/types';

type Mode = 'books' | 'comics' | 'manga';

const BOOK_SOURCES = ['all', 'libgen', 'annas_archive', 'prowlarr'];
const PROWLARR_ONLY = ['prowlarr'];

const SearchPage: React.FC = () => {
  const { toast } = useToast();
  const [mode, setMode] = useState<Mode>('books');
  const [query, setQuery] = useState('');
  const [source, setSource] = useState('all');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [processingKeys, setProcessingKeys] = useState<Set<string>>(new Set());
  const [manualLoadingKeys, setManualLoadingKeys] = useState<Set<string>>(new Set());
  const [activeDownloadKeys, setActiveDownloadKeys] = useState<Set<string>>(new Set());
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [ownedMap, setOwnedMap] = useState<Record<string, string>>({});
  const [manualResults, setManualResults] = useState<ReleaseSearchResult[]>([]);
  const [manualTarget, setManualTarget] = useState<SearchResult | null>(null);
  const [manualError, setManualError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getRequests().then(setRequests).catch(() => {});
  }, []);

  const titleDownloadKey = (title: string, contentType: string) =>
    `${contentType}-${title.trim().replace(/\s+/g, ' ').toLowerCase()}`;

  const refreshActiveDownloads = async () => {
    try {
      const downloads = await getDownloads();
      const active = new Set(
        downloads
          .filter(d => d.status === 'queued' || d.status === 'downloading')
          .map(d => titleDownloadKey(d.title, d.content_type)),
      );
      setActiveDownloadKeys(active);
    } catch {
      // Keep existing state when polling fails.
    }
  };

  useEffect(() => {
    refreshActiveDownloads();
    const timer = setInterval(refreshActiveDownloads, 5000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const runOwnedCheck = async () => {
      if (results.length === 0) {
        setOwnedMap({});
        return;
      }
      try {
        const batch = await checkOwnedBatch(
          results.map(r => ({ title: r.title, content_type: r.content_type })),
        );
        const next: Record<string, string> = {};
        for (const item of batch.items) {
          if (item.owned && item.match) {
            const key = titleDownloadKey(item.title, item.content_type);
            const label = [item.match.library, item.match.source].filter(Boolean).join(' · ');
            next[key] = label || 'Owned';
          }
        }
        setOwnedMap(next);
      } catch {
        // Ignore ownership check failures so search remains usable.
      }
    };
    runOwnedCheck();
  }, [results]);

  // Reset source when mode changes
  useEffect(() => {
    setSource(mode === 'books' ? 'all' : 'prowlarr');
    setResults([]);
    setError('');
    setManualResults([]);
    setManualTarget(null);
    setManualError('');
  }, [mode]);

  const sources =
    mode === 'books' ? BOOK_SOURCES : PROWLARR_ONLY;

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setResults([]);
    try {
      let resp;
      if (mode === 'books') {
        resp = await searchBooks(query, source);
      } else {
        resp = await searchComics(query, 'prowlarr', mode === 'comics' ? 'comic' : 'manga');
      }
      setResults(resp.results);
      if (resp.results.length === 0) setError('No results found. Try a different query or source.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (item: SearchResult) => {
    try {
      const added = await addToRequestList(item);
      setRequests(prev => [...prev, added]);
      toast(`"${item.title}" added to request list`, 'success');
    } catch {
      toast('Failed to add to request list', 'error');
    }
  };

  const isAdded = (item: SearchResult) =>
    requests.some(
      w => w.source === item.source && w.source_id === item.source_id,
    );

  const handleAutoDownload = async (item: SearchResult) => {
    const key = titleDownloadKey(item.title, item.content_type);
    if (processingKeys.has(key) || activeDownloadKeys.has(key)) {
      return;
    }

    setProcessingKeys(prev => {
      const next = new Set(prev);
      next.add(key);
      return next;
    });
    try {
      await startSmartAutoDownload({
        title: item.title,
        content_type: item.content_type,
      });
      toast(`Auto search queued "${item.title}"`, 'success');
      await refreshActiveDownloads();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Auto-download failed';
      toast(msg, 'error');
    } finally {
      setProcessingKeys(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const handleManualSearch = async (item: SearchResult) => {
    const key = titleDownloadKey(item.title, item.content_type);
    setManualLoadingKeys(prev => {
      const next = new Set(prev);
      next.add(key);
      return next;
    });
    setManualTarget(item);
    setManualError('');
    try {
      const resp = await searchProwlarrReleases(item.title, item.content_type, 25);
      setManualResults(resp.results);
      if (resp.results.length === 0) {
        setManualError('No Prowlarr releases found for this item.');
      }
    } catch (err: unknown) {
      setManualResults([]);
      setManualError(err instanceof Error ? err.message : 'Manual search failed');
    } finally {
      setManualLoadingKeys(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const handleManualDownload = async (release: ReleaseSearchResult) => {
    if (!manualTarget) return;
    try {
      await startDirectDownload({
        title: manualTarget.title,
        content_type: manualTarget.content_type,
        download_url: release.downloadUrl,
      });
      toast(`Queued release from ${release.indexer || 'Prowlarr'}`, 'success');
      setManualResults([]);
      setManualTarget(null);
      setManualError('');
      await refreshActiveDownloads();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Failed to queue release', 'error');
    }
  };

  const formatReleaseSize = (size: number) => {
    if (!size || size <= 0) return 'Unknown size';
    const gib = 1024 * 1024 * 1024;
    const mib = 1024 * 1024;
    if (size >= gib) return `${(size / gib).toFixed(2)} GiB`;
    return `${(size / mib).toFixed(1)} MiB`;
  };

  return (
    <>
      <div className="page-header">
        <h1>🔍 Search</h1>
        <p>Discover books, comics &amp; manga from multiple sources</p>
      </div>

      <div className="page-body">
        {/* Mode tabs */}
        <div className="tabs" style={{ marginBottom: '1rem' }}>
          {(['books', 'comics', 'manga'] as Mode[]).map(m => (
            <button key={m} className={`tab${mode === m ? ' active' : ''}`} onClick={() => setMode(m)}>
              {m === 'books' ? '📖 Books' : m === 'comics' ? '🦸 Comics' : '🎌 Manga'}
            </button>
          ))}
        </div>

        {/* Search form */}
        <form className="search-form" onSubmit={handleSearch}>
          <input
            ref={inputRef}
            className="search-input"
            type="text"
            placeholder={
              mode === 'books'  ? 'Search books by title, author, ISBN…' :
              mode === 'comics' ? 'Search comics by title, series…' :
              'Search manga by title…'
            }
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          {sources.length > 1 && (
            <select
              className="search-select"
              value={source}
              onChange={e => setSource(e.target.value)}
            >
              {sources.map(s => (
                <option key={s} value={s}>{s === 'all' ? 'All Sources' : s.replace('_', ' ')}</option>
              ))}
            </select>
          )}
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? <span className="spinner" /> : 'Search'}
          </button>
        </form>

        {error && <div className="alert alert-error" style={{ marginTop: '1rem' }}>{error}</div>}

        {results.length > 0 && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.75rem' }}>
            {results.length} result{results.length !== 1 ? 's' : ''}
          </p>
        )}

        {manualTarget && (
          <div className="settings-section" style={{ marginTop: '1rem' }}>
            <div className="section-header" style={{ marginBottom: '0.75rem' }}>
              <h2 style={{ fontSize: '1rem', fontWeight: 700 }}>Manual Search: {manualTarget.title}</h2>
              <button className="btn btn-ghost btn-sm" onClick={() => { setManualTarget(null); setManualResults([]); setManualError(''); }}>
                Close
              </button>
            </div>
            {manualError && <div className="alert alert-error" style={{ marginBottom: '0.75rem' }}>{manualError}</div>}
            {manualResults.length > 0 ? (
              <div className="downloads-list" style={{ marginTop: 0 }}>
                {manualResults.map((release, index) => (
                  <div key={`${release.guid}-${index}`} className="download-item">
                    <span className="download-status-icon">🛰️</span>
                    <div className="download-info">
                      <div className="download-title">{release.title}</div>
                      <div className="download-detail" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                        <span>{release.indexer || 'Indexer'}</span>
                        <span>{formatReleaseSize(release.size)}</span>
                        <span>{release.seeders > 0 ? `${release.seeders} seeders` : 'Seeders unknown'}</span>
                        {release.publishDate && <span>{new Date(release.publishDate).toLocaleDateString()}</span>}
                      </div>
                    </div>
                    <button className="btn btn-primary btn-sm" onClick={() => handleManualDownload(release)}>
                      Download
                    </button>
                  </div>
                ))}
              </div>
            ) : !manualError ? (
              <div style={{ padding: '1rem 0', color: 'var(--text-muted)' }}>Searching indexers...</div>
            ) : null}
          </div>
        )}

        <div className="results-grid">
          {results.map((item, idx) => {
            const key = titleDownloadKey(item.title, item.content_type);
            const autoDownloading = processingKeys.has(key);
            const manualSearching = manualLoadingKeys.has(key);
            const isActiveDownload = activeDownloadKeys.has(key);
            const ownedLabel = ownedMap[key];
            return (
              <ResultCard
                key={`${item.source}-${item.source_id}-${idx}`}
                item={item}
                onAdd={handleAdd}
                onAutoDownload={handleAutoDownload}
                onManualSearch={handleManualSearch}
                autoDownloading={autoDownloading}
                manualSearching={manualSearching}
                downloadDisabled={autoDownloading || isActiveDownload || Boolean(ownedLabel)}
                ownedLabel={ownedLabel || null}
                alreadyAdded={isAdded(item)}
              />
            );
          })}
        </div>

        {!loading && results.length === 0 && !error && (
          <div className="empty-state">
            <div className="empty-icon">🔍</div>
            <h3>Start searching</h3>
            <p>Enter a title, author, or keyword above</p>
          </div>
        )}
      </div>
    </>
  );
};

export default SearchPage;
