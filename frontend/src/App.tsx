import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from '@/components/Sidebar';
import HomePage from '@/pages/HomePage';
import SearchPage from '@/pages/SearchPage';
import WatchlistPage from '@/pages/WatchlistPage';
import DownloadsPage from '@/pages/DownloadsPage';
import KomgaPage from '@/pages/KomgaPage';
import SettingsPage from '@/pages/SettingsPage';

const App: React.FC = () => {
  return (
    <Routes>
      <Route
        path="/*"
        element={
          <div className="app-shell">
            <Sidebar />
            <main className="main-content">
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/search" element={<SearchPage />} />
                <Route path="/watchlist" element={<WatchlistPage />} />
                <Route path="/downloads" element={<DownloadsPage />} />
                <Route path="/komga" element={<KomgaPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </main>
          </div>
        }
      />
    </Routes>
  );
};

export default App;
