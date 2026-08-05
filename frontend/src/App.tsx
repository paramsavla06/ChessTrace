import { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { CatalogPage } from './pages/CatalogPage';
import { ReviewPage } from './pages/ReviewPage';
import { ProfilePage } from './pages/ProfilePage';
import { LivePage } from './pages/LivePage';
import { ComparePage } from './pages/ComparePage';

export function App() {
  const [activeTab, setActiveTab] = useState<'catalog' | 'review' | 'profile' | 'live' | 'compare'>('catalog');
  const [selectedGameId, setSelectedGameId] = useState<number>(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('gameId');
    return id ? parseInt(id) : 1;
  });
  const [currentUser, setCurrentUser] = useState<string>(() => localStorage.getItem('chessTraceUser') || '');
  const [selectedUsername, setSelectedUsername] = useState<string>(currentUser || '');

  const handleSetCurrentUser = (user: string) => {
    setCurrentUser(user);
    localStorage.setItem('chessTraceUser', user);
    setSelectedUsername(user);
  };

  // Sync activeTab with URL hash and listen to browser back/forward buttons
  useEffect(() => {
    const syncTabFromHash = () => {
      const hash = window.location.hash.replace('#', '');
      if (hash === 'catalog' || hash === 'review' || hash === 'profile' || hash === 'live' || hash === 'compare') {
        setActiveTab(hash as any);
      } else if (window.location.search.includes('gameId=')) {
        setActiveTab('review');
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

  const handleTabChange = (tab: 'catalog' | 'review' | 'profile' | 'live' | 'compare') => {
    setActiveTab(tab);
    window.location.hash = tab;
  };

  const handleSelectGame = (gameId: number) => {
    setSelectedGameId(gameId);
    const url = new URL(window.location.href);
    url.searchParams.set('gameId', gameId.toString());
    window.history.replaceState({}, '', url);
    handleTabChange('review');
  };

  const handleSelectProfile = (username: string) => {
    setSelectedUsername(username);
    handleTabChange('profile');
  };

  return (
    <div className="min-h-screen bg-[#0B0F19] text-slate-100 flex flex-col font-sans">
      <Navbar 
        activeTab={activeTab} 
        setActiveTab={handleTabChange} 
        currentUser={currentUser}
        setCurrentUser={handleSetCurrentUser}
      />

      <main className="flex-1">
        {activeTab === 'catalog' && (
          <CatalogPage 
            onSelectGame={handleSelectGame} 
            onSelectProfile={handleSelectProfile}
            currentUser={currentUser}
          />
        )}

        {activeTab === 'review' && <ReviewPage gameId={selectedGameId} username={currentUser} />}

        {activeTab === 'profile' && <ProfilePage username={selectedUsername} />}

        {activeTab === 'compare' && <ComparePage currentUser={currentUser} />}

        {activeTab === 'live' && (
          <LivePage 
            gameId={selectedGameId} 
            username={currentUser} 
            onSelectGame={handleSelectGame} 
          />
        )}
      </main>

      <footer className="glass-panel border-t border-slate-800/80 py-6 text-center text-xs text-slate-500 font-mono">
        <p>ChessTrace &copy; 2026 • Powered by Stockfish 18 UCI Engine & XGBoost Multi-Model Neural Intelligence</p>
      </footer>
    </div>
  );
}

export default App;
