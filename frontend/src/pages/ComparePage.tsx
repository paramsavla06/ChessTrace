import React, { useState, useEffect } from 'react';
import { Swords, Trophy } from 'lucide-react';
import { api } from '../api/client';
import type { CompareResponse } from '../api/client';

interface ComparePageProps {
  currentUser?: string;
}

export const ComparePage: React.FC<ComparePageProps> = ({ currentUser }) => {
  const [user1, setUser1] = useState<string>(currentUser || '');
  const [user2, setUser2] = useState<string>('');
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    if (currentUser !== undefined) {
      setUser1(currentUser);
    }
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
    } finally {
      setLoading(false);
    }
  };

  if (!currentUser) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-24 text-center space-y-6">
        <div className="w-24 h-24 bg-pink-600/20 rounded-full flex items-center justify-center mx-auto">
          <Swords className="w-12 h-12 text-pink-400" />
        </div>
        <h2 className="text-3xl font-bold text-white">Enter Your Username</h2>
        <p className="text-slate-400 max-w-lg mx-auto">
          To compare your cognitive fingerprint against opponents, please enter your username in the top right corner first.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
      {/* Header Banner */}
      <div className="glass-panel p-6 rounded-2xl flex flex-wrap items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-gradient-to-tr from-pink-600 to-indigo-600 text-white shadow-lg shadow-pink-600/30">
            <Swords className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-3xl font-extrabold text-white">Head-to-Head Comparison</h1>
            <p className="text-sm text-slate-400 mt-1">
              Compare cognitive signatures, tilt resilience, and collapse vulnerability side-by-side
            </p>
          </div>
        </div>

        <form onSubmit={handleCompareSubmit} className="flex flex-wrap gap-3 items-center">
          <input
            type="text"
            placeholder="Player 1..."
            value={user1}
            onChange={(e) => setUser1(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 w-36"
          />
          <span className="text-xs font-bold text-pink-400">VS</span>
          <input
            type="text"
            placeholder="Player 2..."
            value={user2}
            onChange={(e) => setUser2(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 w-36"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-gradient-to-r from-pink-600 to-indigo-600 hover:from-pink-500 hover:to-indigo-500 text-white px-5 py-2 rounded-xl font-medium text-xs transition-all shadow-lg shadow-pink-600/20 disabled:opacity-50"
          >
            {loading ? 'Comparing...' : 'Compare Fingerprints'}
          </button>
        </form>
      </div>

      {/* Comparison Grid */}
      {result && (
        <div className="space-y-6">
          {/* Battle Summary Verdict */}
          <div className="glass-panel p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-500/30 text-center space-y-2">
            <span className="text-xs uppercase font-bold text-indigo-400 tracking-wider flex items-center justify-center gap-1.5">
              <Trophy className="w-4 h-4 text-amber-400" />
              Pressure Resilience Analysis
            </span>
            <h2 className="text-2xl font-bold text-white">
              Who Collapses First Under Time Pressure?
            </h2>
            <p className="text-sm text-indigo-300 font-semibold italic">
              {result.head_to_head_summary.comparison_verdict}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Player 1 Card */}
            <div className="glass-panel p-6 rounded-2xl space-y-4 border-l-4 border-l-indigo-500">
              <div className="flex justify-between items-center">
                <h3 className="text-2xl font-bold text-white">{result.player1.username}</h3>
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                  {result.player1.archetype}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400">Normal Think Pace</span>
                  <p className="text-lg font-bold text-white mt-1">
                    {result.player1.normal_think_pace_sec.toFixed(2)}s
                  </p>
                </div>
                <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400">Post-Blunder Pace</span>
                  <p className="text-lg font-bold text-rose-400 mt-1">
                    {result.player1.post_blunder_pace_sec.toFixed(2)}s
                  </p>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs flex justify-between items-center">
                <span className="text-slate-300">Tilt Speedup Factor</span>
                <span className="font-bold text-rose-400">
                  {result.player1.tilt_speedup_pct.toFixed(1)}% speedup
                </span>
              </div>
            </div>

            {/* Player 2 Card */}
            <div className="glass-panel p-6 rounded-2xl space-y-4 border-l-4 border-l-pink-500">
              <div className="flex justify-between items-center">
                <h3 className="text-2xl font-bold text-white">{result.player2.username}</h3>
                <span className="px-3 py-1 rounded-full text-xs font-bold bg-pink-500/20 text-pink-300 border border-pink-500/30">
                  {result.player2.archetype}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400">Normal Think Pace</span>
                  <p className="text-lg font-bold text-white mt-1">
                    {result.player2.normal_think_pace_sec.toFixed(2)}s
                  </p>
                </div>
                <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400">Post-Blunder Pace</span>
                  <p className="text-lg font-bold text-pink-400 mt-1">
                    {result.player2.post_blunder_pace_sec.toFixed(2)}s
                  </p>
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs flex justify-between items-center">
                <span className="text-slate-300">Tilt Speedup Factor</span>
                <span className="font-bold text-pink-400">
                  {result.player2.tilt_speedup_pct.toFixed(1)}% speedup
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
