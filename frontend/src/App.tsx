import { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { CatalogPage } from './pages/CatalogPage';
import { ReviewPage } from './pages/ReviewPage';
import { ProfilePage } from './pages/ProfilePage';
import { LivePage } from './pages/LivePage';

export function App() {
  const [activeTab, setActiveTab] = useState<'catalog' | 'review' | 'profile' | 'live'>('catalog');
  const [selectedGameId, setSelectedGameId] = useState<number>(1);
  const [selectedUsername, setSelectedUsername] = useState<string>('PlayerA');

  // Sync activeTab with URL hash and listen to browser back/forward buttons
  useEffect(() => {
    const syncTabFromHash = () => {
      const hash = window.location.hash.replace('#', '');
      if (hash === 'catalog' || hash === 'review' || hash === 'profile' || hash === 'live') {
        setActiveTab(hash as any);
      } else {
        setActiveTab('catalog');
      }
    };

    syncTabFromHash();
    window.addEventListener('popstate', syncTabFromHash);
    window.addEventListener('hashchange', syncTabFromHash);
    return () => {
      window.removeEventListener('popstate', syncTabFromHash);
      window.removeEventListener('hashchange', syncTabFromHash);
    };
  }, []);

  const handleTabChange = (tab: 'catalog' | 'review' | 'profile' | 'live') => {
    setActiveTab(tab);
    window.location.hash = tab;
  };

  const handleSelectGame = (gameId: number) => {
    setSelectedGameId(gameId);
    handleTabChange('review');
  };

  const handleSelectProfile = (username: string) => {
    setSelectedUsername(username);
    handleTabChange('profile');
  };

  return (
    <div className="min-h-screen bg-[#0B0F19] text-slate-100 flex flex-col">
      <Navbar activeTab={activeTab} setActiveTab={handleTabChange} />

      <main className="flex-1">
        {activeTab === 'catalog' && (
          <CatalogPage onSelectGame={handleSelectGame} onSelectProfile={handleSelectProfile} />
        )}

        {activeTab === 'review' && <ReviewPage gameId={selectedGameId} />}

        {activeTab === 'profile' && <ProfilePage username={selectedUsername} />}

        {activeTab === 'live' && <LivePage gameId={selectedGameId} />}
      </main>

      <footer className="glass-panel border-t border-slate-800/80 py-6 text-center text-xs text-slate-500">
        <p>ChessTrace &copy; 2026 • Powered by Stockfish 18 UCI Engine & XGBoost Multi-Model Neural Intelligence</p>
      </footer>
    </div>
  );
}

export default App;
