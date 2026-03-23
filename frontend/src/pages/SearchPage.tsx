import React, { useState, useEffect, useRef } from 'react';
import {
  searchBooks,
  searchComics,
  addToWatchlist,
  getDownloads,
  getWatchlist,
  startSmartAutoDownload,
} from '@/services/api';
import ResultCard from '@/components/ResultCard';
import { useToast } from '@/components/ToastProvider';
import type { SearchResult, WatchlistItem } from '@/types';

type Mode = 'books' | 'comics' | 'manga';

const BOOK_SOURCES  = ['all', 'open_library', 'google_books'];
const COMIC_SOURCES = ['all', 'comicvine'];
const MANGA_SOURCES = ['all', 'mangadex', 'anilist'];

const SearchPage: React.FC = () => {
  const { toast } = useToast();
  const [mode, setMode] = useState<Mode>('books');
  const [query, setQuery] = useState('');
  const [source, setSource] = useState('all');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [processingKeys, setProcessingKeys] = useState<Set<string>>(new Set());
  const [activeDownloadKeys, setActiveDownloadKeys] = useState<Set<string>>(new Set());
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getWatchlist().then(setWatchlist).catch(() => {});
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

  // Reset source when mode changes
  useEffect(() => {
    setSource('all');
    setResults([]);
    setError('');
  }, [mode]);

  const sources =
    mode === 'books' ? BOOK_SOURCES :
    mode === 'comics' ? COMIC_SOURCES : MANGA_SOURCES;

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
        resp = await searchComics(query, source, mode === 'comics' ? 'comic' : 'manga');
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
      const added = await addToWatchlist(item);
      setWatchlist(prev => [...prev, added]);
      toast(`"${item.title}" added to watchlist`, 'success');
    } catch {
      toast('Failed to add to watchlist', 'error');
    }
  };

  const isAdded = (item: SearchResult) =>
    watchlist.some(
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
      toast(`Processing "${item.title}" and queued in downloader`, 'success');
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
          <select
            className="search-select"
            value={source}
            onChange={e => setSource(e.target.value)}
          >
            {sources.map(s => (
              <option key={s} value={s}>{s === 'all' ? 'All Sources' : s.replace('_', ' ')}</option>
            ))}
          </select>
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

        <div className="results-grid">
          {results.map((item, idx) => {
            const key = titleDownloadKey(item.title, item.content_type);
            const autoDownloading = processingKeys.has(key);
            const isActiveDownload = activeDownloadKeys.has(key);
            return (
              <ResultCard
                key={`${item.source}-${item.source_id}-${idx}`}
                item={item}
                onAdd={handleAdd}
                onAutoDownload={handleAutoDownload}
                autoDownloading={autoDownloading}
                downloadDisabled={autoDownloading || isActiveDownload}
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
