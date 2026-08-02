import React, { useState, useEffect } from 'react';
import { Activity, Radio, User, Upload, Swords } from 'lucide-react';

interface NavbarProps {
  activeTab: 'catalog' | 'review' | 'profile' | 'live' | 'compare';
  setActiveTab: (tab: 'catalog' | 'review' | 'profile' | 'live' | 'compare') => void;
  currentUser: string;
  setCurrentUser: (user: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab, currentUser, setCurrentUser }) => {
  const [inputValue, setInputValue] = useState(currentUser);

  useEffect(() => {
    setInputValue(currentUser);
  }, [currentUser]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      setCurrentUser(inputValue);
      e.currentTarget.blur();
    }
  };

  const handleBlur = () => {
    setCurrentUser(inputValue);
  };
  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-slate-800 px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand Logo */}
        <div 
          onClick={() => setActiveTab('catalog')}
          className="flex items-center gap-3 cursor-pointer group"
        >
          <img 
            src="/ChessTraceLogo.png" 
            alt="ChessTrace Logo" 
            className="w-11 h-11 rounded-2xl group-hover:scale-105 transition-transform shadow-lg shadow-indigo-500/20 object-cover" 
          />
          <div>
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-indigo-400 bg-clip-text text-transparent">
              ChessTrace
            </h1>
            <p className="text-xs text-slate-400 font-sans">Human Cognition & Collapse Intelligence</p>
          </div>
        </div>

        {/* Nav Links */}
        <nav className="flex items-center gap-2 bg-slate-900/60 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab('catalog')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'catalog'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
            }`}
          >
            <Upload className="w-4 h-4" />
            Import & Catalog
          </button>

          <button
            onClick={() => setActiveTab('review')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'review'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
            }`}
          >
            <Activity className="w-4 h-4" />
            Game Review
          </button>

          <button
            onClick={() => setActiveTab('profile')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'profile'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
            }`}
          >
            <User className="w-4 h-4" />
            Personal Profile
          </button>

          <button
            onClick={() => setActiveTab('compare')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'compare'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
            }`}
          >
            <Swords className="w-4 h-4" />
            Head-to-Head
          </button>

          <button
            onClick={() => setActiveTab('live')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === 'live'
                ? 'bg-pink-600 text-white shadow-lg shadow-pink-600/30'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
            }`}
          >
            <Radio className="w-4 h-4 animate-pulse text-pink-300" />
            Live Spectate
          </button>
          
          <div className="w-px h-6 bg-slate-700 mx-2"></div>
          
          <div className="relative group">
            <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Your Username"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={handleBlur}
              className="bg-slate-800/50 border border-slate-700 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 w-40 transition-all focus:w-48"
            />
          </div>
        </nav>
      </div>
    </header>
  );
};
