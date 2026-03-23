import type {
  SearchResult,
  RequestItem,
  DownloadItem,
  AppSettings,
  ContentType,
  ItemStatus,
  KomgaLibrary,
  LibraryOverview,
  LibraryOwnedCheck,
} from '@/types';

const BASE = '/api';

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };

  const res = await fetch(`${BASE}${path}`, {
    headers: { ...headers, ...((options?.headers as Record<string, string>) || {}) },
    ...options,
  });
  
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ─── Search ───────────────────────────────────────────────────────────────────

export interface SearchResponse {
  query: string;
  source: string;
  total: number;
  results: SearchResult[];
}

export const searchBooks = (q: string, source = 'all', limit = 20): Promise<SearchResponse> =>
  request(`/books/search?q=${encodeURIComponent(q)}&source=${source}&limit=${limit}`);

export const searchComics = (
  q: string,
  source = 'all',
  content_type = 'all',
  limit = 20,
): Promise<SearchResponse> =>
  request(
    `/comics/search?q=${encodeURIComponent(q)}&source=${source}&content_type=${content_type}&limit=${limit}`,
  );

// ─── Request List ─────────────────────────────────────────────────────────────

export const getRequests = (): Promise<RequestItem[]> => request('/requests');

export const addToRequestList = (item: Omit<SearchResult, 'isbn'> & { notes?: string }): Promise<RequestItem> =>
  request('/requests', {
    method: 'POST',
    body: JSON.stringify(item),
  });

export const updateRequestItem = (
  id: number,
  patch: { status?: ItemStatus; notes?: string },
): Promise<RequestItem> =>
  request(`/requests/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });

export const removeFromRequestList = (id: number): Promise<void> =>
  request(`/requests/${id}`, { method: 'DELETE' });

// Backward-compatible aliases while components are migrated.
export const getWatchlist = getRequests;
export const addToWatchlist = addToRequestList;
export const updateWatchlistItem = updateRequestItem;
export const removeFromWatchlist = removeFromRequestList;

// ─── Downloads ────────────────────────────────────────────────────────────────

export const getDownloads = (): Promise<DownloadItem[]> => request('/downloads');

export const queueDownload = (data: {
  title: string;
  content_type: ContentType;
  download_url?: string;
  watchlist_id?: number;
}): Promise<DownloadItem> =>
  request('/downloads', { method: 'POST', body: JSON.stringify(data) });

export const startDirectDownload = (data: {
  title: string;
  content_type: ContentType;
  download_url: string;
  mirror_urls?: string[];
  watchlist_id?: number;
}) => request('/downloads/direct', { method: 'POST', body: JSON.stringify(data) });

export const startProwlarrAutoDownload = (data: {
  title: string;
  content_type: ContentType;
  watchlist_id?: number;
}) => request('/downloads/prowlarr/auto', { method: 'POST', body: JSON.stringify(data) });

export const startSmartAutoDownload = (data: {
  title: string;
  content_type: ContentType;
  watchlist_id?: number;
}) => request('/downloads/auto', { method: 'POST', body: JSON.stringify(data) });

export const updateDownloadStatus = (id: number, status: string): Promise<DownloadItem> =>
  request(`/downloads/${id}/status?status=${status}`, { method: 'PATCH' });

export const removeDownload = (id: number): Promise<void> =>
  request(`/downloads/${id}`, { method: 'DELETE' });

// ─── Integrations ─────────────────────────────────────────────────────────────

export const getKomgaStatus = () => request<{ connected: boolean; error?: string; user?: string }>('/integrations/komga/status');
export const getKomgaLibraries = (): Promise<KomgaLibrary[]> => request('/integrations/komga/libraries');
export const scanKomgaLibrary = (id: string) => request(`/integrations/komga/libraries/${id}/scan`, { method: 'POST' });
export const getCwaStatus = () => request<{ connected: boolean; error?: string; ingest_folder?: string }>('/integrations/cwa/status');
export const getCwaInfo = () => request<{ cwa_url: string; ingest_folder: string; configured: boolean }>('/integrations/cwa/info');
export const getProwlarrStatus = () => request<{ connected: boolean; error?: string; version?: string }>('/integrations/prowlarr/status');
export const getQbittorrentStatus = () => request<{ connected: boolean; error?: string; version?: string }>('/integrations/qbittorrent/status');

// ─── Library ──────────────────────────────────────────────────────────────────

export const getLibraryOverview = (): Promise<LibraryOverview> => request('/library');

export const checkOwnedBatch = (items: Array<{ title: string; content_type: ContentType }>) =>
  request<{ items: LibraryOwnedCheck[] }>('/library/owned/batch', {
    method: 'POST',
    body: JSON.stringify({ items }),
  });

export const testKomgaConnection = (data: { url: string }) =>
  request<{ connected: boolean; error?: string; user?: string }>('/integrations/komga/test', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const testCwaConnection = (data: { url: string }) =>
  request<{ connected: boolean; error?: string; status_code?: number }>('/integrations/cwa/test', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const testProwlarrConnection = (data: { url: string; api_key?: string }) =>
  request<{ connected: boolean; error?: string; version?: string }>('/integrations/prowlarr/test', {
    method: 'POST',
    body: JSON.stringify(data),
  });

export const testQbittorrentConnection = (data: { url: string; username?: string; password?: string }) =>
  request<{ connected: boolean; error?: string; version?: string }>('/integrations/qbittorrent/test', {
    method: 'POST',
    body: JSON.stringify(data),
  });

// ─── Settings ─────────────────────────────────────────────────────────────────

export const getSettings = (): Promise<AppSettings> => request('/settings');

export const saveSettings = (data: AppSettings): Promise<{ saved: string[] }> =>
  request('/settings/bulk', { method: 'POST', body: JSON.stringify(data) });
