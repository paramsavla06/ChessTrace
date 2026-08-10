import React, { useState, useEffect } from 'react';
import { Upload, Download, Database, Play, User, Search, AlertCircle } from 'lucide-react';
import { api } from '../api/client';
import type { GameSummary } from '../api/client';

interface CatalogPageProps {
  onSelectGame: (gameId: number) => void;
  onSelectProfile: (username: string) => void;
  currentUser?: string;
}

export const CatalogPage: React.FC<CatalogPageProps> = ({ onSelectGame, onSelectProfile, currentUser }) => {
  const [games, setGames] = useState<GameSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [uploading, setUploading] = useState<boolean>(false);
  const [lichessUser, setLichessUser] = useState<string>('');
  const [filterUser, setFilterUser] = useState<string>(currentUser || '');
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const fetchGames = async () => {
    setLoading(true);
    try {
      const response = await api.get<GameSummary[]>('/games', {
        params: filterUser ? { username: filterUser } : {},
      });
      setGames(response.data);
    } catch (err: any) {
      console.error('Failed fetching games', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGames();
  }, [filterUser]);

  useEffect(() => {
    if (currentUser !== undefined) {
      setFilterUser(currentUser);
    }
  }, [currentUser]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    setMessage(null);

    try {
      const response = await api.post('/upload/pgn', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setMessage({
        text: `Successfully imported ${response.data.imported} games (${response.data.skipped} skipped).`,
        type: 'success',
      });
      fetchGames();
    } catch (err: any) {
      setMessage({
        text: err.response?.data?.detail || 'Failed importing PGN file.',
        type: 'error',
      });
    } finally {
      setUploading(false);
    }
  };

  const handleLichessFetch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lichessUser.trim()) return;

    setUploading(true);
    setMessage(null);

    try {
      const response = await api.post(`/upload/lichess/${lichessUser.trim()}?max_games=50`);
      setMessage({
        text: `Downloaded and imported ${response.data.imported} games for '${lichessUser.trim()}'.`,
        type: 'success',
      });
      setFilterUser(lichessUser.trim());
      fetchGames();
    } catch (err: any) {
      setMessage({
        text: err.response?.data?.detail || `Failed fetching Lichess games for '${lichessUser}'.`,
        type: 'error',
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8 font-sans">
      {/* First-Time User Onboarding Banner */}
      <div className="glass-panel p-6 rounded-2xl bg-gradient-to-r from-indigo-950/60 via-slate-900 to-slate-900 border border-indigo-500/30 flex flex-wrap items-center justify-between gap-6">
        <div className="space-y-2 max-w-3xl">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 text-xs font-bold font-mono border border-indigo-500/30">
              Welcome to ChessTrace
            </span>
            <span className="text-xs text-slate-400 font-mono">• Human Cognition & Collapse Intelligence</span>
          </div>
          <h2 className="text-xl font-extrabold text-white">
            Analyze Time Pressure, Blunder Collapse Risks, and Cognitive Fingerprints
          </h2>
          <p className="text-xs text-slate-300">
            ChessTrace combines Stockfish 18 evaluations with 8 XGBoost ML models trained on 500k+ move plies to decode human time-stress behavior, SHAP plain-English explanations, counterfactual what-if branches, and grandmaster style matches.
          </p>
        </div>

        <button
          onClick={() => onSelectGame(1)}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 text-white font-bold text-xs transition-all shadow-lg shadow-indigo-600/30"
        >
          <Play className="w-4 h-4 fill-white" />
          <span>Launch Demo Game Review</span>
        </button>
      </div>
      {/* Header Notification */}
      {message && (
        <div
          className={`p-4 rounded-xl flex items-center gap-3 border ${
            message.type === 'success'
              ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300'
              : 'bg-rose-950/40 border-rose-800 text-rose-300'
          }`}
        >
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm font-medium">{message.text}</p>
        </div>
      )}

      {/* Top Controls Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* PGN Drag & Drop */}
        <div className="glass-panel p-6 rounded-2xl flex flex-col justify-between space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Upload className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Upload PGN File</h2>
              <p className="text-sm text-slate-400">Upload standalone PGN files with clock timestamps (%clk)</p>
            </div>
          </div>

          <label className="border-2 border-dashed border-slate-700 hover:border-indigo-500 rounded-xl p-6 text-center cursor-pointer transition-colors block bg-slate-900/30">
            <input type="file" accept=".pgn,.txt" onChange={handleFileUpload} className="hidden" />
            <p className="text-sm text-slate-300 font-medium">
              {uploading ? 'Processing PGN dataset...' : 'Click to browse or drop PGN file here'}
            </p>
            <p className="text-xs text-slate-500 mt-1">Supports multi-game PGN files</p>
          </label>
        </div>

        {/* Lichess Auto-Import */}
        <div className="glass-panel p-6 rounded-2xl flex flex-col justify-between space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-pink-500/10 border border-pink-500/20 text-pink-400">
              <Download className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Import from Lichess</h2>
              <p className="text-sm text-slate-400">Auto-fetch public game history with clock data</p>
            </div>
          </div>

          <form onSubmit={handleLichessFetch} className="flex gap-3">
            <input
              type="text"
              placeholder="Lichess username (e.g. MagnusCarlsen)"
              value={lichessUser}
              onChange={(e) => setLichessUser(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={uploading}
              className="bg-gradient-to-r from-pink-600 to-indigo-600 hover:from-pink-500 hover:to-indigo-500 text-white px-5 py-2.5 rounded-xl font-medium text-sm transition-all shadow-lg shadow-pink-600/20 disabled:opacity-50"
            >
              {uploading ? 'Fetching...' : 'Fetch'}
            </button>
          </form>
        </div>
      </div>

      {/* Catalog Table */}
      <div className="glass-panel p-6 rounded-2xl space-y-6">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Database className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-semibold text-white">Stored Games Catalog</h2>
            <span className="bg-slate-800 text-slate-300 text-xs px-2.5 py-1 rounded-full font-medium">
              {games.length} games
            </span>
          </div>

          <div className="relative w-full md:w-64">
            <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-500" />
            <input
              type="text"
              placeholder="Filter by player..."
              value={filterUser}
              onChange={(e) => setFilterUser(e.target.value)}
              className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center text-slate-500 text-sm">Loading games catalog...</div>
        ) : games.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-sm">
            No games stored in database. Upload a PGN or import from Lichess above!
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-900/60 text-xs uppercase text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3.5 px-4 font-semibold">ID</th>
                  <th className="py-3.5 px-4 font-semibold">Event</th>
                  <th className="py-3.5 px-4 font-semibold">White</th>
                  <th className="py-3.5 px-4 font-semibold">Black</th>
                  <th className="py-3.5 px-4 font-semibold">Result</th>
                  <th className="py-3.5 px-4 font-semibold">TC</th>
                  <th className="py-3.5 px-4 font-semibold">Moves</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {games.map((g) => (
                  <tr key={g.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3.5 px-4 text-xs font-mono text-slate-400">#{g.id}</td>
                    <td className="py-3.5 px-4 font-medium text-white truncate max-w-[180px]">
                      <div className="flex items-center gap-2">
                        <span className="truncate">{g.event || 'Standard Game'}</span>
                        {g.black_player === 'LiveBlack' && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 whitespace-nowrap">
                            Chess.com Import
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <button
                        onClick={() => g.white_player && onSelectProfile(g.white_player)}
                        className="hover:text-indigo-400 hover:underline flex items-center gap-1.5"
                      >
                        <User className="w-3.5 h-3.5 text-slate-500" />
                        {g.white_player || 'White'}
                        {g.white_elo && <span className="text-xs text-slate-500">({g.white_elo})</span>}
                      </button>
                    </td>
                    <td className="py-3.5 px-4">
                      <button
                        onClick={() => g.black_player && onSelectProfile(g.black_player)}
                        className="hover:text-indigo-400 hover:underline flex items-center gap-1.5"
                      >
                        <User className="w-3.5 h-3.5 text-slate-500" />
                        {g.black_player || 'Black'}
                        {g.black_elo && <span className="text-xs text-slate-500">({g.black_elo})</span>}
                      </button>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs font-semibold text-indigo-300">
                      {g.result}
                    </td>
                    <td className="py-3.5 px-4 text-xs text-slate-400">{g.time_control || 'Blitz'}</td>
                    <td className="py-3.5 px-4 text-xs text-slate-400">{g.move_count}</td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => onSelectGame(g.id)}
                        className="inline-flex items-center gap-1.5 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-all border border-indigo-500/30"
                      >
                        <Play className="w-3.5 h-3.5" />
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
