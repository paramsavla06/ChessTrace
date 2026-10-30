import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Swords, Trophy, Loader2, TrendingDown, Clock, Zap } from 'lucide-react';
import { api } from '../api/client';
import type { CompareResponse } from '../api/client';

interface ComparePageProps {
  currentUser?: string;
}

export const ComparePage: React.FC<ComparePageProps> = ({ currentUser }) => {
  const [user1, setUser1] = useState(currentUser || '');
  const [user2, setUser2] = useState('');
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (currentUser !== undefined) setUser1(currentUser);
  }, [currentUser]);

  const handleCompareSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user1.trim() || !user2.trim()) return;
    setLoading(true);
    try {
      const res = await api.get<CompareResponse>(`/analysis/compare/${user1.trim()}/${user2.trim()}`);
      setResult(res.data);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed fetching player comparison!');
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  if (!currentUser) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-6 text-center">
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center"
          style={{ background: 'rgba(232,182,106,0.1)', border: '1px solid rgba(232,182,106,0.2)' }}
        >
          <Swords className="w-10 h-10" style={{ color: 'var(--ct-gold)' }} />
        </div>
        <div>
          <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--ct-text-primary)' }}>
            Enter Your Username
          </h2>
          <p className="text-sm max-w-md" style={{ color: 'var(--ct-text-muted)' }}>
            To compare cognitive fingerprints, enter your username in the top navigation bar first.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ── Header ───────────────────────────────────────────── */}
      <div>
        <h1 className="text-2xl font-bold" style={{ color: 'var(--ct-text-primary)' }}>
          Head-to-Head Comparison
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--ct-text-muted)' }}>
          Compare cognitive signatures, tilt resilience, and collapse vulnerability side-by-side.
        </p>
      </div>

      {/* ── Compare Form ─────────────────────────────────────── */}
      <div className="glass-panel rounded-2xl p-6">
        <form onSubmit={handleCompareSubmit} className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[160px]">
            <label className="text-xs uppercase font-semibold tracking-wider mb-2 block" style={{ color: 'var(--ct-text-muted)' }}>
              Player 1
            </label>
            <input
              type="text"
              placeholder="Username…"
              value={user1}
              onChange={(e) => setUser1(e.target.value)}
              className="input-app w-full"
            />
          </div>

          <div className="flex items-center pb-2">
            <span className="text-xl font-black" style={{ color: 'var(--ct-gold)' }}>VS</span>
          </div>

          <div className="flex-1 min-w-[160px]">
            <label className="text-xs uppercase font-semibold tracking-wider mb-2 block" style={{ color: 'var(--ct-text-muted)' }}>
              Player 2
            </label>
            <input
              type="text"
              placeholder="Username…"
              value={user2}
              onChange={(e) => setUser2(e.target.value)}
              className="input-app w-full"
            />
          </div>

          <button
            type="submit"
            disabled={loading || !user1.trim() || !user2.trim()}
            className="btn-gold disabled:opacity-50"
          >
            {loading ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Comparing…</>
            ) : (
              <><Swords className="w-4 h-4" /> Compare Fingerprints</>
            )}
          </button>
        </form>
      </div>

      {/* ── Results ──────────────────────────────────────────── */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="space-y-5"
          >
            {/* Verdict Banner */}
            <div
              className="glass-panel rounded-2xl px-6 py-5 text-center space-y-2"
              style={{ borderColor: 'rgba(232,182,106,0.15)' }}
            >
              <div className="flex items-center justify-center gap-2 text-xs uppercase font-bold tracking-wider" style={{ color: 'var(--ct-gold)' }}>
                <Trophy className="w-4 h-4" />
                Pressure Resilience Analysis
              </div>
              <h2 className="text-xl font-bold" style={{ color: 'var(--ct-text-primary)' }}>
                Who Collapses First Under Time Pressure?
              </h2>
              <p className="text-sm italic max-w-lg mx-auto" style={{ color: 'var(--ct-text-secondary)' }}>
                {result.head_to_head_summary.comparison_verdict}
              </p>
            </div>

            {/* Player Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {[
                { player: result.player1, accent: 'var(--ct-gold)', borderAccent: 'rgba(232,182,106,0.4)' },
                { player: result.player2, accent: '#A5ADC6', borderAccent: 'rgba(165,173,198,0.3)' },
              ].map(({ player, accent, borderAccent }) => (
                <div
                  key={player.username}
                  className="glass-panel rounded-2xl p-5 space-y-4"
                  style={{ borderLeft: `3px solid ${accent}` }}
                >
                  <div className="flex justify-between items-center">
                    <h3 className="text-xl font-bold" style={{ color: 'var(--ct-text-primary)' }}>
                      {player.username}
                    </h3>
                    <span
                      className="px-3 py-1 rounded-full text-xs font-bold"
                      style={{
                        background: `${accent}18`,
                        color: accent,
                        border: `1px solid ${borderAccent}`,
                      }}
                    >
                      {player.archetype}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { icon: <Clock className="w-4 h-4" />, label: 'Normal Think Pace', value: `${player.normal_think_pace_sec.toFixed(2)}s`, color: 'var(--ct-text-primary)' },
                      { icon: <TrendingDown className="w-4 h-4" />, label: 'Post-Blunder Pace', value: `${player.post_blunder_pace_sec.toFixed(2)}s`, color: '#EF4444' },
                    ].map((stat) => (
                      <div
                        key={stat.label}
                        className="rounded-xl p-3"
                        style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.05)' }}
                      >
                        <div className="flex items-center gap-1.5 mb-1" style={{ color: 'var(--ct-text-muted)' }}>
                          {stat.icon}
                          <span className="text-xs">{stat.label}</span>
                        </div>
                        <p className="text-xl font-bold font-mono" style={{ color: stat.color }}>
                          {stat.value}
                        </p>
                      </div>
                    ))}
                  </div>

                  <div
                    className="flex justify-between items-center px-4 py-3 rounded-xl text-sm"
                    style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.05)' }}
                  >
                    <div className="flex items-center gap-2" style={{ color: 'var(--ct-text-muted)' }}>
                      <Zap className="w-4 h-4" />
                      <span>Tilt Speedup</span>
                    </div>
                    <span className="font-bold font-mono" style={{ color: '#EF4444' }}>
                      {player.tilt_speedup_pct.toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Final Verdict */}
            <div
              className="glass-panel rounded-2xl p-6 text-center space-y-3"
              style={{ borderColor: 'rgba(232,182,106,0.2)' }}
            >
              <h3 className="text-base font-bold flex items-center justify-center gap-2" style={{ color: 'var(--ct-text-primary)' }}>
                <Swords className="w-5 h-5" style={{ color: 'var(--ct-gold)' }} />
                Verdict: Who Collapses First?
              </h3>
              <p style={{ color: 'var(--ct-text-secondary)' }}>
                {result.head_to_head_summary.tilt_vulnerability_winner === 'Equal pressure resilience'
                  ? 'Both players show equal resilience under pressure.'
                  : (
                    <>
                      <strong style={{ color: 'var(--ct-gold)' }}>
                        {result.head_to_head_summary.tilt_vulnerability_winner}
                      </strong>{' '}
                      is statistically more likely to collapse under time pressure and tilt after a blunder.
                    </>
                  )}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
