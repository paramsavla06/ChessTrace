import { useState } from 'react';
import { Navbar } from './components/Navbar';
import { CatalogPage } from './pages/CatalogPage';
import { ReviewPage } from './pages/ReviewPage';
import { ProfilePage } from './pages/ProfilePage';
import { LivePage } from './pages/LivePage';

export function App() {
  const [activeTab, setActiveTab] = useState<'catalog' | 'review' | 'profile' | 'live'>('catalog');
  const [selectedGameId, setSelectedGameId] = useState<number>(1);
  const [selectedUsername, setSelectedUsername] = useState<string>('PlayerA');

  const handleSelectGame = (gameId: number) => {
    setSelectedGameId(gameId);
    setActiveTab('review');
  };

  const handleSelectProfile = (username: string) => {
    setSelectedUsername(username);
    setActiveTab('profile');
  };

  return (
    <div className="min-h-screen bg-[#0B0F19] text-slate-100 flex flex-col">
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

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
