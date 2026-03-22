import React, { useEffect, useState } from 'react';
import { getKomgaStatus, getKomgaLibraries, scanKomgaLibrary } from '@/services/api';
import { useToast } from '@/components/ToastProvider';
import type { KomgaLibrary } from '@/types';

const KomgaPage: React.FC = () => {
  const { toast } = useToast();
  const [connected, setConnected] = useState<boolean | null>(null);
  const [statusMsg, setStatusMsg] = useState('');
  const [libraries, setLibraries] = useState<KomgaLibrary[]>([]);
  const [scanning, setScanning] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const checkStatus = async () => {
    setLoading(true);
    try {
      const status = await getKomgaStatus();
      setConnected(status.connected);
      setStatusMsg(status.connected ? `Logged in as ${status.user ?? ''}` : status.error ?? 'Disconnected');

      if (status.connected) {
        const libs = await getKomgaLibraries();
        setLibraries(libs);
      }
    } catch (err: unknown) {
      setConnected(false);
      setStatusMsg(err instanceof Error ? err.message : 'Connection error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { checkStatus(); }, []);

  const handleScan = async (libId: string, libName: string) => {
    setScanning(libId);
    try {
      await scanKomgaLibrary(libId);
      toast(`Scan triggered for "${libName}"`, 'success');
    } catch {
      toast('Failed to trigger scan', 'error');
    } finally {
      setScanning(null);
    }
  };

  const chipClass = connected === null ? 'unknown' : connected ? 'connected' : 'disconnected';

  return (
    <>
      <div className="page-header">
        <h1>📚 Komga</h1>
        <p>Manage your Komga comic &amp; manga server</p>
      </div>

      <div className="page-body">
        {/* Status card */}
        <div className="settings-section">
          <h2>🔌 Connection Status</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            {loading ? (
              <span className="spinner" />
            ) : (
              <span className={`status-chip ${chipClass}`}>
                <span className="dot" />
                {statusMsg || (connected ? 'Connected' : 'Disconnected')}
              </span>
            )}
            <button className="btn btn-ghost btn-sm" onClick={checkStatus} disabled={loading}>
              ↻ Refresh
            </button>
          </div>
          {!connected && !loading && (
            <p style={{ marginTop: '0.75rem', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              Configure Komga URL and credentials in{' '}
              <a href="/settings">Settings → Komga</a>.
            </p>
          )}
        </div>

        {/* Libraries */}
        {connected && (
          <div className="settings-section">
            <h2>📂 Libraries</h2>
            {libraries.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No libraries found.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                {libraries.map(lib => (
                  <div
                    key={lib.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      background: 'var(--bg-base)',
                      borderRadius: 'var(--radius)',
                      padding: '0.75rem 1rem',
                      border: '1px solid var(--border-soft)',
                      gap: '1rem',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{lib.name}</div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)', marginTop: '0.2rem' }}>
                        {lib.root}
                      </div>
                    </div>
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => handleScan(lib.id, lib.name)}
                      disabled={scanning === lib.id}
                    >
                      {scanning === lib.id ? <span className="spinner" /> : '↻ Scan'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
};

export default KomgaPage;
