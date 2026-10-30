import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  Download,
  Database,
  Play,
  User,
  Search,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileText,
} from 'lucide-react';
import { api } from '../api/client';
import type { GameSummary } from '../api/client';

interface CatalogPageProps {
  onSelectGame: (gameId: number) => void;
  onSelectProfile: (username: string) => void;
  currentUser?: string;
}

function ResultBadge({ result }: { result: string }) {
  const cfg =
    result === '1-0'
      ? { text: '1-0', cls: 'text-[#E8B66A] bg-[#E8B66A]/10 border-[#E8B66A]/20' }
      : result === '0-1'
      ? { text: '0-1', cls: 'text-[#A5ADC6] bg-[#A5ADC6]/10 border-[#A5ADC6]/20' }
      : { text: '½-½', cls: 'text-[#30C670] bg-[#30C670]/10 border-[#30C670]/20' };
  return (
    <span
      className={`px-2.5 py-0.5 rounded-md text-xs font-bold font-mono border ${cfg.cls}`}
    >
      {cfg.text}
    </span>
  );
}

export const CatalogPage: React.FC<CatalogPageProps> = ({
  onSelectGame,
  onSelectProfile,
  currentUser,
}) => {
  const [games, setGames] = useState<GameSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [lichessUser, setLichessUser] = useState('');
  const [filterUser, setFilterUser] = useState(currentUser || '');
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchGames = async () => {
    setLoading(true);
    try {
      const response = await api.get<GameSummary[]>('/games', {
        params: filterUser ? { username: filterUser } : {},
      });
      setGames(response.data);
    } catch (err) {
      console.error('Failed fetching games', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchGames(); }, [filterUser]);
  useEffect(() => {
    if (currentUser !== undefined) setFilterUser(currentUser);
  }, [currentUser]);

  const uploadFile = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    setUploading(true);
    setMessage(null);
    try {
      const response = await api.post('/upload/pgn', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setMessage({
        text: `Successfully imported ${response.data.imported} game${response.data.imported !== 1 ? 's' : ''} (${response.data.skipped} skipped).`,
        type: 'success',
      });
      fetchGames();
    } catch (err: any) {
      setMessage({ text: err.response?.data?.detail || 'Failed importing PGN file.', type: 'error' });
    } finally {
      setUploading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    uploadFile(e.target.files[0]);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file && (file.name.endsWith('.pgn') || file.name.endsWith('.txt'))) {
      uploadFile(file);
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
    <div className="space-y-6">
      {/* ── Page Header ──────────────────────────────────────── */}
      <div>
        <h1 className="text-2xl font-bold" style={{ color: 'var(--ct-text-primary)', fontFamily: 'var(--font-sans)' }}>
          Import &amp; Catalog
        </h1>
        <p className="text-sm mt-1" style={{ color: 'var(--ct-text-muted)' }}>
          Upload PGN files or fetch from Lichess to analyze your games.
        </p>
      </div>

      {/* ── Status Message ───────────────────────────────────── */}
      <AnimatePresence>
        {message && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25 }}
            className={`flex items-start gap-3 px-5 py-4 rounded-xl border text-sm ${
              message.type === 'success'
                ? 'bg-[#30C670]/8 border-[#30C670]/20 text-[#30C670]'
                : 'bg-[#DC2626]/8 border-[#DC2626]/20 text-[#EF4444]'
            }`}
          >
            {message.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            )}
            <p>{message.text}</p>
            <button
              onClick={() => setMessage(null)}
              className="ml-auto text-current opacity-60 hover:opacity-100 transition-opacity"
            >
              ✕
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Import Controls ──────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* PGN Upload */}
        <div className="glass-panel rounded-2xl p-6 space-y-4">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(232,182,106,0.1)', border: '1px solid rgba(232,182,106,0.2)' }}
            >
              <FileText className="w-5 h-5" style={{ color: 'var(--ct-gold)' }} />
            </div>
            <div>
              <h2 className="text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
                Upload PGN File
              </h2>
              <p className="text-xs" style={{ color: 'var(--ct-text-muted)' }}>
                Supports multi-game PGN files with clock timestamps
              </p>
            </div>
          </div>

          <div
            role="button"
            tabIndex={0}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
            onKeyDown={(e) => e.key === 'Enter' && !uploading && fileInputRef.current?.click()}
            className={`rounded-xl p-8 text-center cursor-pointer transition-all duration-200 border-2 border-dashed ${
              dragOver
                ? 'border-[#E8B66A]/60 bg-[#E8B66A]/5'
                : 'border-white/[0.08] hover:border-[#E8B66A]/30 hover:bg-white/[0.02]'
            }`}
            aria-label="Upload PGN file"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pgn,.txt"
              onChange={handleFileUpload}
              className="hidden"
              disabled={uploading}
            />
            {uploading ? (
              <div className="flex flex-col items-center gap-3">
                <Loader2
                  className="w-8 h-8 animate-spin"
                  style={{ color: 'var(--ct-gold)' }}
                />
                <p className="text-sm font-medium" style={{ color: 'var(--ct-text-secondary)' }}>
                  Processing PGN dataset…
                </p>
              </div>
            ) : (
              <>
                <Upload className="w-8 h-8 mx-auto mb-3" style={{ color: 'var(--ct-text-muted)' }} />
                <p className="text-sm font-medium" style={{ color: 'var(--ct-text-secondary)' }}>
                  Click to browse or drag &amp; drop
                </p>
                <p className="text-xs mt-1" style={{ color: 'var(--ct-text-muted)' }}>
                  .pgn or .txt files accepted
                </p>
              </>
            )}
          </div>
        </div>

        {/* Lichess Import */}
        <div className="glass-panel rounded-2xl p-6 space-y-4">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(165,173,198,0.1)', border: '1px solid rgba(165,173,198,0.15)' }}
            >
              <Download className="w-5 h-5" style={{ color: 'var(--ct-text-secondary)' }} />
            </div>
            <div>
              <h2 className="text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
                Import from Lichess
              </h2>
              <p className="text-xs" style={{ color: 'var(--ct-text-muted)' }}>
                Auto-fetch public game history with clock data (up to 50 games)
              </p>
            </div>
          </div>

          <form onSubmit={handleLichessFetch} className="space-y-3">
            <input
              type="text"
              placeholder="Lichess username (e.g. MagnusCarlsen)"
              value={lichessUser}
              onChange={(e) => setLichessUser(e.target.value)}
              className="input-app w-full"
            />
            <button
              type="submit"
              disabled={uploading || !lichessUser.trim()}
              className="btn-gold w-full justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Fetching…
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  Fetch Games
                </>
              )}
            </button>
          </form>

          {/* Demo Game Button */}
          <button
            onClick={() => onSelectGame(1)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200"
            style={{
              background: 'rgba(232,182,106,0.06)',
              border: '1px solid rgba(232,182,106,0.15)',
              color: 'var(--ct-gold)',
            }}
          >
            <Play className="w-4 h-4 fill-current" />
            Open Demo Game Review
          </button>
        </div>
      </div>

      {/* ── Games Catalog ────────────────────────────────────── */}
      <div className="glass-panel rounded-2xl overflow-hidden">
        {/* Catalog Header */}
        <div
          className="px-6 py-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b"
          style={{ borderColor: 'rgba(255,255,255,0.05)' }}
        >
          <div className="flex items-center gap-3">
            <Database className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
            <span className="text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
              Stored Games
            </span>
            <span
              className="px-2.5 py-0.5 rounded-md text-xs font-bold font-mono"
              style={{
                background: 'rgba(232,182,106,0.1)',
                color: 'var(--ct-gold)',
                border: '1px solid rgba(232,182,106,0.2)',
              }}
            >
              {games.length}
            </span>
          </div>

          <div className="relative w-full sm:w-56">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
              style={{ color: 'var(--ct-text-muted)' }}
            />
            <input
              type="text"
              placeholder="Filter by player…"
              value={filterUser}
              onChange={(e) => setFilterUser(e.target.value)}
              className="input-app pl-9 w-full text-xs"
            />
          </div>
        </div>

        {/* Catalog Content */}
        {loading ? (
          <div className="py-16 flex flex-col items-center gap-4">
            <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'var(--ct-gold)' }} />
            <p className="text-sm" style={{ color: 'var(--ct-text-muted)' }}>
              Loading game catalog…
            </p>
          </div>
        ) : games.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <Database className="w-12 h-12 mx-auto opacity-20" style={{ color: 'var(--ct-text-muted)' }} />
            <p className="text-sm font-medium" style={{ color: 'var(--ct-text-secondary)' }}>
              No games found
            </p>
            <p className="text-xs" style={{ color: 'var(--ct-text-muted)' }}>
              {filterUser ? `No games found for "${filterUser}". Try a different filter.` : 'Upload a PGN or import from Lichess above.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="text-xs uppercase tracking-wider"
                  style={{
                    background: 'rgba(255,255,255,0.02)',
                    color: 'var(--ct-text-muted)',
                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                  }}
                >
                  <th className="px-5 py-3 text-left font-semibold">ID</th>
                  <th className="px-5 py-3 text-left font-semibold">Event</th>
                  <th className="px-5 py-3 text-left font-semibold">White</th>
                  <th className="px-5 py-3 text-left font-semibold">Black</th>
                  <th className="px-5 py-3 text-left font-semibold">Result</th>
                  <th className="px-5 py-3 text-left font-semibold">TC</th>
                  <th className="px-5 py-3 text-left font-semibold">Moves</th>
                  <th className="px-5 py-3 text-right font-semibold">Action</th>
                </tr>
              </thead>
              <tbody>
                {games.map((g, i) => (
                  <motion.tr
                    key={g.id}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2, delay: Math.min(i * 0.03, 0.4) }}
                    className="group transition-colors duration-150"
                    style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}
                    onMouseEnter={(e) =>
                      (e.currentTarget.style.background = 'rgba(255,255,255,0.025)')
                    }
                    onMouseLeave={(e) =>
                      (e.currentTarget.style.background = 'transparent')
                    }
                  >
                    <td className="px-5 py-3.5">
                      <span
                        className="text-xs font-mono"
                        style={{ color: 'var(--ct-text-muted)' }}
                      >
                        #{g.id}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <span
                          className="font-medium truncate max-w-[160px]"
                          style={{ color: 'var(--ct-text-primary)' }}
                        >
                          {g.event || 'Standard Game'}
                        </span>
                        {g.event === 'Live Spectate Export' && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded font-bold border"
                            style={{ background: 'rgba(236,72,153,0.1)', color: '#f472b6', borderColor: 'rgba(236,72,153,0.25)' }}>
                            Live
                          </span>
                        )}
                        {g.site === 'Chess.com' && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded font-bold border"
                            style={{ background: 'rgba(48,198,112,0.1)', color: '#30C670', borderColor: 'rgba(48,198,112,0.25)' }}>
                            Chess.com
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <button
                        onClick={() => g.white_player && onSelectProfile(g.white_player)}
                        className="flex items-center gap-1.5 transition-colors duration-150 group/player"
                        style={{ color: 'var(--ct-text-secondary)' }}
                      >
                        <User className="w-3.5 h-3.5 opacity-50" />
                        <span className="group-hover/player:text-[#E8B66A] transition-colors">
                          {g.white_player || 'White'}
                        </span>
                        {g.white_elo && (
                          <span className="text-xs" style={{ color: 'var(--ct-text-muted)' }}>
                            ({g.white_elo})
                          </span>
                        )}
                      </button>
                    </td>
                    <td className="px-5 py-3.5">
                      <button
                        onClick={() => g.black_player && onSelectProfile(g.black_player)}
                        className="flex items-center gap-1.5 transition-colors duration-150 group/player"
                        style={{ color: 'var(--ct-text-secondary)' }}
                      >
                        <User className="w-3.5 h-3.5 opacity-50" />
                        <span className="group-hover/player:text-[#E8B66A] transition-colors">
                          {g.black_player || 'Black'}
                        </span>
                        {g.black_elo && (
                          <span className="text-xs" style={{ color: 'var(--ct-text-muted)' }}>
                            ({g.black_elo})
                          </span>
                        )}
                      </button>
                    </td>
                    <td className="px-5 py-3.5">
                      <ResultBadge result={g.result} />
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="text-xs font-mono" style={{ color: 'var(--ct-text-muted)' }}>
                        {g.time_control || 'Blitz'}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="text-xs font-mono" style={{ color: 'var(--ct-text-muted)' }}>
                        {g.move_count}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={() => onSelectGame(g.id)}
                        className="btn-gold py-1.5 px-3 text-xs"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                        Review
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
