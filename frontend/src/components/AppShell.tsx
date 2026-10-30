import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  Activity,
  User,
  Swords,
  Radio,
  ChevronLeft,
  Menu,
  X,
  Home,
} from 'lucide-react';

type AppTab = 'catalog' | 'review' | 'profile' | 'live' | 'compare';

interface AppShellProps {
  activeTab: AppTab;
  setActiveTab: (tab: AppTab) => void;
  currentUser: string;
  setCurrentUser: (user: string) => void;
  onShowLanding: () => void;
  children: React.ReactNode;
}

const NAV_ITEMS: {
  key: AppTab;
  label: string;
  icon: React.ReactNode;
  live?: boolean;
}[] = [
  { key: 'catalog', label: 'Import & Catalog', icon: <Upload className="w-4 h-4" /> },
  { key: 'review', label: 'Game Review', icon: <Activity className="w-4 h-4" /> },
  { key: 'profile', label: 'Player Profile', icon: <User className="w-4 h-4" /> },
  { key: 'compare', label: 'Head-to-Head', icon: <Swords className="w-4 h-4" /> },
  { key: 'live', label: 'Live Spectate', icon: <Radio className="w-4 h-4" />, live: true },
];

export const AppShell: React.FC<AppShellProps> = ({
  activeTab,
  setActiveTab,
  currentUser,
  setCurrentUser,
  onShowLanding,
  children,
}) => {
  const [inputValue, setInputValue] = useState(currentUser);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    setInputValue(currentUser);
  }, [currentUser]);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 10);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      setCurrentUser(inputValue);
      e.currentTarget.blur();
    }
  };

  const handleBlur = () => setCurrentUser(inputValue);

  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--ct-navy)' }}>
      {/* ── Top Header ─────────────────────────────────────── */}
      <header
        className={`sticky top-0 z-50 transition-all duration-300 ${
          scrolled
            ? 'border-b border-white/[0.06] backdrop-blur-xl'
            : 'border-b border-transparent'
        }`}
        style={{ background: 'rgba(16, 21, 47, 0.96)' }}
      >
        <div className="max-w-[1440px] mx-auto px-4 md:px-6 flex items-center justify-between h-[60px] gap-4">
          {/* Brand */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <button
              onClick={onShowLanding}
              className="flex items-center gap-2.5 group"
              title="Back to home"
            >
              <img
                src="/ChessTraceLogo.png"
                alt="ChessTrace"
                className="w-8 h-8 rounded-xl object-cover transition-transform duration-200 group-hover:scale-105"
              />
              <div className="hidden sm:block">
                <div className="text-sm font-bold tracking-tight text-[#F3F0E8] leading-none">
                  ChessTrace
                </div>
                <div
                  className="text-[10px] leading-none mt-0.5"
                  style={{ color: 'var(--ct-text-muted)' }}
                >
                  Chess Intelligence
                </div>
              </div>
            </button>

            <button
              onClick={onShowLanding}
              className="hidden sm:flex items-center gap-1 text-[10px] font-medium px-2.5 py-1 rounded-md transition-all duration-200"
              style={{
                color: 'var(--ct-text-muted)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
              title="Back to landing page"
            >
              <Home className="w-3 h-3" />
              <ChevronLeft className="w-3 h-3" />
            </button>
          </div>

          {/* Desktop Nav */}
          <nav className="hidden lg:flex items-center gap-1 flex-1 justify-center">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.key}
                onClick={() => setActiveTab(item.key)}
                className={`relative flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  activeTab === item.key
                    ? item.live
                      ? 'text-white'
                      : 'text-[#E8B66A]'
                    : 'text-[#6B7394] hover:text-[#A5ADC6] hover:bg-white/[0.04]'
                }`}
              >
                {/* Active indicator */}
                {activeTab === item.key && (
                  <motion.div
                    layoutId="active-tab-bg"
                    className="absolute inset-0 rounded-lg"
                    style={{
                      background: item.live
                        ? 'rgba(236, 72, 153, 0.12)'
                        : 'rgba(232, 182, 106, 0.1)',
                      border: `1px solid ${item.live ? 'rgba(236, 72, 153, 0.2)' : 'rgba(232, 182, 106, 0.2)'}`,
                    }}
                    transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                  />
                )}
                <span className={`relative z-10 ${activeTab === item.key && item.live ? 'text-pink-400' : ''}`}>
                  {item.live ? (
                    <Radio
                      className={`w-4 h-4 ${activeTab === item.key ? 'animate-pulse text-pink-400' : ''}`}
                    />
                  ) : (
                    item.icon
                  )}
                </span>
                <span className="relative z-10">{item.label}</span>
              </button>
            ))}
          </nav>

          {/* Right: Username + Mobile Menu */}
          <div className="flex items-center gap-3 flex-shrink-0">
            {/* Username Input */}
            <div className="hidden md:flex items-center gap-2">
              <div className="relative flex items-center">
                <User
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 pointer-events-none z-10"
                  style={{ color: 'var(--ct-text-muted)' }}
                />
                <input
                  type="text"
                  placeholder="Your username"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onBlur={handleBlur}
                  className="input-app pr-3 py-1.5 text-xs w-40 focus:w-48 transition-all duration-200"
                  style={{ fontSize: '12px', paddingLeft: '34px' }}
                />
              </div>
            </div>

            {/* Mobile menu toggle */}
            <button
              className="lg:hidden p-2 rounded-lg transition-colors"
              style={{ color: 'var(--ct-text-muted)' }}
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Toggle navigation"
            >
              {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Dropdown */}
        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2, ease: 'easeInOut' }}
              className="lg:hidden overflow-hidden border-t"
              style={{
                borderColor: 'rgba(255,255,255,0.06)',
                background: 'var(--ct-navy-2)',
              }}
            >
              <div className="px-4 py-3 space-y-1">
                {/* Mobile username */}
                <div className="relative flex items-center mb-3">
                  <User
                    className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 pointer-events-none z-10"
                    style={{ color: 'var(--ct-text-muted)' }}
                  />
                  <input
                    type="text"
                    placeholder="Your username"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onBlur={handleBlur}
                    className="input-app pr-3 py-2 text-xs w-full"
                    style={{ paddingLeft: '34px' }}
                  />
                </div>
                {NAV_ITEMS.map((item) => (
                  <button
                    key={item.key}
                    onClick={() => {
                      setActiveTab(item.key);
                      setMobileOpen(false);
                    }}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                      activeTab === item.key
                        ? item.live
                          ? 'bg-pink-500/10 text-pink-400 border border-pink-500/20'
                          : 'bg-[#E8B66A]/10 text-[#E8B66A] border border-[#E8B66A]/20'
                        : 'text-[#6B7394] hover:text-[#A5ADC6] hover:bg-white/[0.04]'
                    }`}
                  >
                    {item.icon}
                    {item.label}
                  </button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* ── Main Content ────────────────────────────────────── */}
      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 md:px-6 py-6">
        {children}
      </main>

      {/* ── Footer ──────────────────────────────────────────── */}
      <footer
        className="border-t py-4 text-center text-xs font-mono"
        style={{
          borderColor: 'rgba(255,255,255,0.05)',
          color: 'var(--ct-text-muted)',
        }}
      >
        ChessTrace © 2026 &nbsp;·&nbsp; Stockfish 18 UCI &nbsp;·&nbsp; XGBoost ML Intelligence
      </footer>
    </div>
  );
};
