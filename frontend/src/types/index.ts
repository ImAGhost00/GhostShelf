export type ContentType = 'book' | 'comic' | 'manga';
export type ItemStatus = 'wanted' | 'found' | 'downloading' | 'downloaded' | 'failed';

export interface SearchResult {
  source: string;
  source_id: string;
  content_type: ContentType;
  title: string;
  author: string;
  description: string;
  cover_url: string;
  year: string;
  genres: string[];
  isbn?: string;
}

export interface WatchlistItem {
  id: number;
  title: string;
  author: string | null;
  description: string | null;
  cover_url: string | null;
  content_type: ContentType;
  status: ItemStatus;
  source: string | null;
  source_id: string | null;
  year: string | null;
  genres: string[];
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface DownloadItem {
  id: number;
  watchlist_id: number | null;
  title: string;
  content_type: ContentType;
  download_url: string | null;
  status: string;
  destination: string | null;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface KomgaLibrary {
  id: string;
  name: string;
  root: string;
  count?: number;
}

export interface AppSettings {
  cwa_url?: string;
  cwa_ingest_folder?: string;
  komga_ingest_folder?: string;
  comic_ingest_folder?: string;
  manga_ingest_folder?: string;
  komga_url?: string;
  komga_username?: string;
  komga_password?: string;
  google_books_api_key?: string;
  comicvine_api_key?: string;
  prowlarr_url?: string;
  prowlarr_api_key?: string;
  qbittorrent_url?: string;
  qbittorrent_username?: string;
  qbittorrent_password?: string;
}
