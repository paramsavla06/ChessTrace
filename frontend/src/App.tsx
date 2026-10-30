import { useState, useEffect } from 'react';
import { LandingPage } from './pages/LandingPage';
import { AppShell } from './components/AppShell';
import { CatalogPage } from './pages/CatalogPage';
import { ReviewPage } from './pages/ReviewPage';
import { ProfilePage } from './pages/ProfilePage';
import { LivePage } from './pages/LivePage';
import { ComparePage } from './pages/ComparePage';

type AppTab = 'catalog' | 'review' | 'profile' | 'live' | 'compare';

export function App() {
  const [showLanding, setShowLanding] = useState<boolean>(() => {
    const hash = window.location.hash.replace('#', '');
    const hasGameId = window.location.search.includes('gameId=');
    const knownTabs: AppTab[] = ['catalog', 'review', 'profile', 'live', 'compare'];
    if (knownTabs.includes(hash as AppTab) || hasGameId) return false;
    return true;
  });

  const [activeTab, setActiveTab] = useState<AppTab>(() => {
    const hash = window.location.hash.replace('#', '') as AppTab;
    const knownTabs: AppTab[] = ['catalog', 'review', 'profile', 'live', 'compare'];
    if (knownTabs.includes(hash)) return hash;
    if (window.location.search.includes('gameId=')) return 'review';
    return 'catalog';
  });

  const [selectedGameId, setSelectedGameId] = useState<number>(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get('gameId');
    return id ? parseInt(id) : 1;
  });

  const [currentUser, setCurrentUser] = useState<string>(
    () => localStorage.getItem('chessTraceUser') || ''
  );
  const [selectedUsername, setSelectedUsername] = useState<string>(currentUser || '');

  const handleSetCurrentUser = (user: string) => {
    setCurrentUser(user);
    localStorage.setItem('chessTraceUser', user);
    setSelectedUsername(user);
  };

  // Sync activeTab with URL hash
  useEffect(() => {
    const syncTabFromHash = () => {
      const hash = window.location.hash.replace('#', '') as AppTab;
      const knownTabs: AppTab[] = ['catalog', 'review', 'profile', 'live', 'compare'];
      if (knownTabs.includes(hash)) {
        setActiveTab(hash);
        setShowLanding(false);
      } else if (window.location.search.includes('gameId=')) {
        setActiveTab('review');
        setShowLanding(false);
      }
    };
    window.addEventListener('popstate', syncTabFromHash);
    window.addEventListener('hashchange', syncTabFromHash);
    return () => {
      window.removeEventListener('popstate', syncTabFromHash);
      window.removeEventListener('hashchange', syncTabFromHash);
    };
  }, []);

  const handleTabChange = (tab: AppTab) => {
    setActiveTab(tab);
    setShowLanding(false);
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

  const handleEnterApp = () => {
    setShowLanding(false);
    setActiveTab('catalog');
    window.location.hash = 'catalog';
  };

  if (showLanding) {
    return (
      <div className="landing-env">
        <LandingPage onEnterApp={handleEnterApp} />
      </div>
    );
  }

  return (
    <div className="app-env">
      <AppShell
        activeTab={activeTab}
        setActiveTab={handleTabChange}
        currentUser={currentUser}
        setCurrentUser={handleSetCurrentUser}
        onShowLanding={() => setShowLanding(true)}
      >
        {activeTab === 'catalog' && (
          <CatalogPage
            onSelectGame={handleSelectGame}
            onSelectProfile={handleSelectProfile}
            currentUser={currentUser}
          />
        )}
        {activeTab === 'review' && (
          <ReviewPage gameId={selectedGameId} username={currentUser} />
        )}
        {activeTab === 'profile' && (
          <ProfilePage username={selectedUsername} />
        )}
        {activeTab === 'compare' && (
          <ComparePage currentUser={currentUser} />
        )}
        {activeTab === 'live' && (
          <LivePage
            gameId={selectedGameId}
            username={currentUser}
            onSelectGame={handleSelectGame}
          />
        )}
      </AppShell>
    </div>
  );
}

export default App;
