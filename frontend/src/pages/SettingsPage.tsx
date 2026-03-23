import React, { useEffect, useState } from 'react';
import {
  getSettings,
  saveSettings,
  getCwaStatus,
  getKomgaStatus,
  getProwlarrStatus,
  getQbittorrentStatus,
} from '@/services/api';
  import {
    testCwaConnection,
    testKomgaConnection,
    testProwlarrConnection,
    testQbittorrentConnection,
  } from '@/services/api';
import { useToast } from '@/components/ToastProvider';
import type { AppSettings } from '@/types';

const SettingsPage: React.FC = () => {
  const { toast } = useToast();
  const [form, setForm] = useState<AppSettings>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [cwaStatus, setCwaStatus] = useState<{ connected: boolean; error?: string } | null>(null);
  const [komgaStatus, setKomgaStatus] = useState<{ connected: boolean; error?: string } | null>(null);
  const [prowlarrStatus, setProwlarrStatus] = useState<{ connected: boolean; error?: string; version?: string } | null>(null);
  const [qbittorrentStatus, setQbittorrentStatus] = useState<{ connected: boolean; error?: string; version?: string } | null>(null);

  useEffect(() => {
    getSettings()
      .then(s => setForm(s))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const set = (key: keyof AppSettings) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(prev => ({ ...prev, [key]: e.target.value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveSettings(form);
      toast('Settings saved', 'success');
    } catch {
      toast('Failed to save settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  const testCwa = async () => {
    setCwaStatus(null);
    try {
        const r = await testCwaConnection({ url: form.cwa_url ?? '' });
      setCwaStatus(r);
    } catch {
      setCwaStatus({ connected: false, error: 'Request failed' });
    }
  };

  const testKomga = async () => {
    setKomgaStatus(null);
    try {
      const r = await testKomgaConnection({
        url: form.komga_url ?? '',
      });
      setKomgaStatus(r);
    } catch {
      setKomgaStatus({ connected: false, error: 'Request failed' });
    }
  };

  const testProwlarr = async () => {
    setProwlarrStatus(null);
    try {
        const r = await testProwlarrConnection({
          url: form.prowlarr_url ?? '',
          api_key: form.prowlarr_api_key ?? '',
        });
      setProwlarrStatus(r);
    } catch {
      setProwlarrStatus({ connected: false, error: 'Request failed' });
    }
  };

  const testQbittorrent = async () => {
    setQbittorrentStatus(null);
    try {
        const r = await testQbittorrentConnection({
          url: form.qbittorrent_url ?? '',
          username: form.qbittorrent_username ?? '',
          password: form.qbittorrent_password ?? '',
        });
      setQbittorrentStatus(r);
    } catch {
      setQbittorrentStatus({ connected: false, error: 'Request failed' });
    }
  };

  if (loading) return <div style={{ padding: '2rem', textAlign: 'center' }}><span className="spinner" /></div>;

  return (
    <>
      <div className="page-header">
        <h1>⚙️ Settings</h1>
        <p>Configure integrations and API keys</p>
      </div>

      <div className="page-body">
        {/* CWA */}
        <div className="settings-section">
          <h2>📗 Calibre-Web Automated (CWA)</h2>
          <div className="settings-grid">
            <div className="form-field">
              <label>CWA URL</label>
              <input
                type="url"
                placeholder="http://localhost:8083"
                value={form.cwa_url ?? ''}
                onChange={set('cwa_url')}
              />
              <span className="hint">Base URL of your Calibre-Web instance</span>
            </div>
            <div className="form-field">
              <label>Ingest Folder Path</label>
              <input
                type="text"
                placeholder="/books/ingest"
                value={form.cwa_ingest_folder ?? ''}
                onChange={set('cwa_ingest_folder')}
              />
              <span className="hint">CWA watch folder where books are dropped for import</span>
            </div>
          </div>
          <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button className="btn btn-ghost btn-sm" onClick={testCwa}>Test Connection</button>
            {cwaStatus && (
              <span className={`status-chip ${cwaStatus.connected ? 'connected' : 'disconnected'}`}>
                <span className="dot" />
                {cwaStatus.connected ? 'Connected' : cwaStatus.error ?? 'Disconnected'}
              </span>
            )}
          </div>
        </div>

        {/* Komga */}
        <div className="settings-section">
          <h2>📚 Komga</h2>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
            Komga is accessed via your Wizarr login. Configure the URL and download folders below.
          </p>
          <div className="settings-grid">
            <div className="form-field">
              <label>Komga URL</label>
              <input
                type="url"
                placeholder="http://localhost:25600"
                value={form.komga_url ?? ''}
                onChange={set('komga_url')}
              />
            </div>
            <div className="form-field">
              <label>Comic Ingest Folder</label>
              <input
                type="text"
                placeholder="/media/comics/incoming"
                value={form.comic_ingest_folder ?? ''}
                onChange={set('comic_ingest_folder')}
              />
              <span className="hint">Used for comic downloads. Falls back to shared Komga folder if empty.</span>
            </div>
            <div className="form-field">
              <label>Manga Ingest Folder</label>
              <input
                type="text"
                placeholder="/media/manga/incoming"
                value={form.manga_ingest_folder ?? ''}
                onChange={set('manga_ingest_folder')}
              />
              <span className="hint">Used for manga downloads. Falls back to shared Komga folder if empty.</span>
            </div>
            <div className="form-field">
              <label>Shared Komga Ingest Folder (Legacy Fallback)</label>
              <input
                type="text"
                placeholder="/comics/incoming"
                value={form.komga_ingest_folder ?? ''}
                onChange={set('komga_ingest_folder')}
              />
              <span className="hint">Optional fallback if comic/manga-specific folders are not set.</span>
            </div>
          </div>
          <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button className="btn btn-ghost btn-sm" onClick={testKomga}>Test Connection</button>
            {komgaStatus && (
              <span className={`status-chip ${komgaStatus.connected ? 'connected' : 'disconnected'}`}>
                <span className="dot" />
                {komgaStatus.connected ? 'Connected' : komgaStatus.error ?? 'Disconnected'}
              </span>
            )}
          </div>
        </div>

        {/* Prowlarr */}
        <div className="settings-section">
          <h2>🛰️ Prowlarr</h2>
          <div className="settings-grid">
            <div className="form-field">
              <label>Prowlarr URL</label>
              <input
                type="url"
                placeholder="http://localhost:9696"
                value={form.prowlarr_url ?? ''}
                onChange={set('prowlarr_url')}
              />
            </div>
            <div className="form-field">
              <label>Prowlarr API Key</label>
              <input
                type="password"
                placeholder="Settings > General > Security"
                value={form.prowlarr_api_key ?? ''}
                onChange={set('prowlarr_api_key')}
              />
            </div>
          </div>
          <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button className="btn btn-ghost btn-sm" onClick={testProwlarr}>Test Connection</button>
            {prowlarrStatus && (
              <span className={`status-chip ${prowlarrStatus.connected ? 'connected' : 'disconnected'}`}>
                <span className="dot" />
                {prowlarrStatus.connected
                  ? `Connected${prowlarrStatus.version ? ` (v${prowlarrStatus.version})` : ''}`
                  : prowlarrStatus.error ?? 'Disconnected'}
              </span>
            )}
          </div>
        </div>

        {/* qBittorrent */}
        <div className="settings-section">
          <h2>🧲 qBittorrent</h2>
          <div className="settings-grid">
            <div className="form-field">
              <label>qBittorrent URL</label>
              <input
                type="url"
                placeholder="http://localhost:8080"
                value={form.qbittorrent_url ?? ''}
                onChange={set('qbittorrent_url')}
              />
            </div>
            <div className="form-field">
              <label>qBittorrent Username</label>
              <input
                type="text"
                placeholder="admin"
                value={form.qbittorrent_username ?? ''}
                onChange={set('qbittorrent_username')}
              />
            </div>
            <div className="form-field">
              <label>qBittorrent Password</label>
              <input
                type="password"
                placeholder="••••••••"
                value={form.qbittorrent_password ?? ''}
                onChange={set('qbittorrent_password')}
              />
            </div>
          </div>
          <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button className="btn btn-ghost btn-sm" onClick={testQbittorrent}>Test Connection</button>
            {qbittorrentStatus && (
              <span className={`status-chip ${qbittorrentStatus.connected ? 'connected' : 'disconnected'}`}>
                <span className="dot" />
                {qbittorrentStatus.connected
                  ? `Connected${qbittorrentStatus.version ? ` (v${qbittorrentStatus.version})` : ''}`
                  : qbittorrentStatus.error ?? 'Disconnected'}
              </span>
            )}
          </div>
        </div>

        {/* API Keys */}
        <div className="settings-section">
          <h2>🔑 API Keys</h2>
          <div className="settings-grid">
            <div className="form-field">
              <label>Google Books API Key</label>
              <input
                type="password"
                placeholder="Optional — improves book search quota"
                value={form.google_books_api_key ?? ''}
                onChange={set('google_books_api_key')}
              />
              <span className="hint">
                Get a key at{' '}
                <a href="https://console.cloud.google.com" target="_blank" rel="noopener noreferrer">
                  Google Cloud Console
                </a>
              </span>
            </div>
            <div className="form-field">
              <label>ComicVine API Key</label>
              <input
                type="password"
                placeholder="Required for Western comics search"
                value={form.comicvine_api_key ?? ''}
                onChange={set('comicvine_api_key')}
              />
              <span className="hint">
                Get a free key at{' '}
                <a href="https://comicvine.gamespot.com/api/" target="_blank" rel="noopener noreferrer">
                  ComicVine API
                </a>
              </span>
            </div>
          </div>
        </div>

        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? <><span className="spinner" /> Saving…</> : '💾 Save All Settings'}
        </button>
      </div>
    </>
  );
};

export default SettingsPage;
