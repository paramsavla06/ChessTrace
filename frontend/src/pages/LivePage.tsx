import React, { useState, useEffect } from 'react';
import { Chessboard } from 'react-chessboard';
import { Chess } from 'chess.js';
import { motion, AnimatePresence } from 'framer-motion';
import { Radio, Zap, ArrowRightCircle, User, Loader2, AlertCircle } from 'lucide-react';
import { api } from '../api/client';

interface LivePageProps {
  gameId: number;
  username?: string | null;
  onSelectGame?: (gameId: number) => void;
}

interface LiveFrame {
  fen: string;
  win_probability?: number;
  collapse_probability?: number;
  narrative_summary?: string;
  ply?: number;
  san?: string;
  color?: string;
  move_number?: number;
  uci?: string;
  white_player?: string;
  black_player?: string;
  time_remaining_sec?: number;
}

export const LivePage: React.FC<LivePageProps> = ({ gameId, onSelectGame }) => {
  const [history, setHistory] = useState<LiveFrame[]>([]);
  const [viewIndex, setViewIndex] = useState(-1);
  const [connected, setConnected] = useState(false);
  const [inputGameId, setInputGameId] = useState('');
  const [boardOrientation, setBoardOrientation] = useState<'white' | 'black'>('white');
  const [isExporting, setIsExporting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const currentFrame = viewIndex === -1
    ? (history[history.length - 1] || { fen: 'start' })
    : history[viewIndex];

  const exportToReview = async () => {
    if (history.length === 0) return;
    setIsExporting(true);
    try {
      const game = new Chess();
      for (const frame of history) {
        if (!frame.uci) continue;
        try {
          game.move({ from: frame.uci.substring(0, 2), to: frame.uci.substring(2, 4), promotion: frame.uci.length > 4 ? frame.uci[4] : undefined });
        } catch { /* skip invalid */ }
      }
      const pgnMoves = game.history().reduce((acc, move, i) => {
        if (i % 2 === 0) return acc + `${Math.floor(i / 2) + 1}. ${move} `;
        return acc + `${move} `;
      }, '').trim();
      const whiteName = currentFrame.white_player || 'White';
      const blackName = currentFrame.black_player || 'Black';
      const pgnStr = `[Event "Live Spectate Export"]\n[Site "ChessTrace"]\n[Date "${new Date().toISOString().split('T')[0]}"]\n[White "${whiteName}"]\n[Black "${blackName}"]\n[Result "*"]\n\n${pgnMoves} *`;
      const blob = new Blob([pgnStr], { type: 'text/plain' });
      const file = new File([blob], 'live_export.pgn', { type: 'text/plain' });
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.post('/upload/pgn', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      if (res.data && (res.data.imported > 0 || res.data.skipped > 0)) {
        const gameIds = res.data.game_ids;
        if (gameIds && gameIds.length > 0 && onSelectGame) {
          onSelectGame(gameIds[0]);
        } else {
          window.location.hash = 'review';
        }
      } else {
        throw new Error('Failed to import game to database.');
      }
    } catch (err: any) {
      setErrorMsg(`Export failed: ${err.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  useEffect(() => {
    let cleanId = inputGameId.trim();
    let orientation: 'white' | 'black' = 'white';
    if (cleanId.endsWith('/black') || cleanId.endsWith('#black')) {
      orientation = 'black';
      cleanId = cleanId.replace(/\/black|#black$/, '');
    } else if (cleanId.endsWith('/white') || cleanId.endsWith('#white')) {
      cleanId = cleanId.replace(/\/white|#white$/, '');
    }
    if (cleanId.includes('lichess.org/')) {
      const parts = cleanId.split('lichess.org/')[1].split(/[/#]/);
      cleanId = parts[0];
      if (parts.length > 1 && parts[1] === 'black') orientation = 'black';
    }
    setBoardOrientation(orientation);
    if (!cleanId || cleanId.length < 8) { setConnected(false); return; }

    const apiBase = import.meta.env.VITE_API_URL as string | undefined;
    let wsUrl: string;
    if (apiBase) {
      const wsBase = apiBase.replace(/^https/, 'wss').replace(/^http/, 'ws');
      if (wsBase.endsWith('/api/v1') || wsBase.endsWith('/api/v1/')) {
        wsUrl = `${wsBase.endsWith('/') ? wsBase.slice(0, -1) : wsBase}/ws/live/${cleanId}`;
      } else {
        wsUrl = `${wsBase.endsWith('/') ? wsBase : `${wsBase}/`}api/v1/ws/live/${cleanId}`;
      }
    } else {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      wsUrl = `${proto}://${window.location.host}/api/v1/ws/live/${cleanId}`;
    }

    const socket = new WebSocket(wsUrl);
    socket.onopen = () => { setConnected(true); setErrorMsg(null); setHistory([]); setViewIndex(-1); };
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.error) { setErrorMsg(data.error); socket.close(); return; }
        setHistory(prev => {
          const newHistory = [...prev];
          const existingIdx = newHistory.findIndex(f => f.ply === data.ply);
          if (existingIdx !== -1) newHistory[existingIdx] = data;
          else newHistory.push(data);
          return newHistory.sort((a, b) => (a.ply || 0) - (b.ply || 0));
        });
      } catch (err) { console.error('Failed parsing WS frame', err); }
    };
    socket.onclose = () => setConnected(false);
    return () => socket.close();
  }, [inputGameId, gameId]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (history.length === 0) return;
      if (e.key === 'ArrowLeft') {
        setViewIndex(prev => { const current = prev === -1 ? history.length - 1 : prev; return Math.max(0, current - 1); });
      } else if (e.key === 'ArrowRight') {
        setViewIndex(prev => { if (prev === -1) return -1; const next = prev + 1; return next >= history.length - 1 ? -1 : next; });
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [history]);

  const formatClock = (seconds: number | null | undefined) => {
    if (seconds == null) return '--:--';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    const ms = (seconds % 1).toFixed(1).substring(2);
    return seconds < 10 ? `${m}:${s.toString().padStart(2, '0')}.${ms}` : `${m}:${s.toString().padStart(2, '0')}`;
  };

  const getPlayerClock = (color: 'white' | 'black') => {
    const activeIndex = viewIndex === -1 ? history.length - 1 : viewIndex;
    for (let i = activeIndex; i >= 0; i--) {
      if (history[i]?.color === color) return history[i].time_remaining_sec;
    }
    return null;
  };

  const whitePlayerName = currentFrame.white_player || 'White';
  const blackPlayerName = currentFrame.black_player || 'Black';
  const topPlayer = boardOrientation === 'white' ? blackPlayerName : whitePlayerName;
  const bottomPlayer = boardOrientation === 'white' ? whitePlayerName : blackPlayerName;
  const displayId = inputGameId.replace(/\/black|\/white|#black|#white/g, '').split('/').pop();

  return (
    <div className="space-y-5">
      {/* ── Header ───────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--ct-text-primary)' }}>
            <Radio
              className={`w-6 h-6 ${connected ? 'text-[#EF4444]' : ''}`}
              style={{ color: connected ? '#EF4444' : 'var(--ct-text-muted)' }}
            />
            Live Spectate
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--ct-text-muted)' }}>
            {connected ? (
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#EF4444] animate-pulse" />
                Connected — game #{displayId}
              </span>
            ) : 'Enter a Lichess game ID or URL to begin spectating'}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {history.length > 0 && (
            <button
              onClick={exportToReview}
              disabled={isExporting}
              className="btn-gold text-xs disabled:opacity-50"
            >
              {isExporting ? (
                <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Exporting…</>
              ) : (
                <><ArrowRightCircle className="w-3.5 h-3.5" /> Export to Review</>
              )}
            </button>
          )}
          <input
            type="text"
            placeholder="Enter Lichess Game ID or URL…"
            value={inputGameId}
            onChange={(e) => setInputGameId(e.target.value)}
            className="input-app text-xs w-64"
          />
        </div>
      </div>

      {/* Error */}
      <AnimatePresence>
        {errorMsg && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-center justify-between gap-3 px-5 py-4 rounded-xl text-sm"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#EF4444' }}
          >
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              {errorMsg}
            </div>
            <button onClick={() => setErrorMsg(null)} className="text-current opacity-60 hover:opacity-100">✕</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Main Grid ────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Board Column */}
        <div className="lg:col-span-5 flex flex-col gap-3 items-center">
          {/* Top Player */}
          <div
            className="w-full max-w-[460px] flex items-center justify-between rounded-xl px-4 py-2.5"
            style={{ background: 'rgba(23,30,64,0.8)', border: '1px solid rgba(255,255,255,0.06)' }}
          >
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: 'var(--ct-navy-3)' }}>
                <User className="w-4 h-4" style={{ color: 'var(--ct-text-muted)' }} />
              </div>
              <div>
                <div className="text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>{topPlayer}</div>
                {connected && (
                  <div className="text-[11px] flex items-center gap-1" style={{ color: '#EF4444' }}>
                    <span className="w-1.5 h-1.5 rounded-full bg-current" />Live
                  </div>
                )}
              </div>
            </div>
            <div
              className="px-3 py-1 rounded-lg font-mono text-base font-bold min-w-[76px] text-center"
              style={{ background: '#0A0E20', color: 'var(--ct-text-primary)', border: '1px solid rgba(255,255,255,0.06)' }}
            >
              {formatClock(getPlayerClock(boardOrientation === 'white' ? 'black' : 'white'))}
            </div>
          </div>

          {/* Chessboard */}
          <div
            className="w-full max-w-[460px] relative rounded-2xl overflow-hidden"
            style={{
              background: 'var(--ct-navy-2)',
              border: '1px solid rgba(255,255,255,0.08)',
              boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
              padding: '12px',
            }}
          >
            <Chessboard
              position={currentFrame.fen}
              boardOrientation={boardOrientation}
              arePiecesDraggable={false}
              customBoardStyle={{ borderRadius: '10px' }}
              customDarkSquareStyle={{ backgroundColor: '#B8944E' }}
              customLightSquareStyle={{ backgroundColor: '#E8D5A8' }}
            />
            {viewIndex !== -1 && (
              <div
                className="absolute top-3 right-3 text-xs font-bold px-2 py-1 rounded-md"
                style={{ background: 'rgba(232,182,106,0.9)', color: 'var(--ct-navy)' }}
              >
                Viewing History
              </div>
            )}
          </div>

          {/* Bottom Player */}
          <div
            className="w-full max-w-[460px] flex items-center justify-between rounded-xl px-4 py-2.5"
            style={{ background: 'rgba(23,30,64,0.8)', border: '1px solid rgba(255,255,255,0.06)' }}
          >
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: 'var(--ct-navy-3)' }}>
                <User className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
              </div>
              <div>
                <div className="text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>{bottomPlayer}</div>
              </div>
            </div>
            <div
              className="px-3 py-1 rounded-lg font-mono text-base font-bold min-w-[76px] text-center"
              style={{ background: '#0A0E20', color: 'var(--ct-gold)', border: '1px solid rgba(232,182,106,0.15)' }}
            >
              {formatClock(getPlayerClock(boardOrientation))}
            </div>
          </div>

          {/* Scrubber */}
          {history.length > 0 && (
            <div className="w-full max-w-[460px]">
              <div className="flex justify-between items-center text-xs mb-2" style={{ color: 'var(--ct-text-muted)' }}>
                <button
                  onClick={() => setViewIndex(0)}
                  disabled={viewIndex === 0}
                  className="hover:text-white disabled:opacity-40 transition-colors"
                >
                  Start
                </button>
                <span>{viewIndex === -1 ? '● Live' : `Move ${viewIndex + 1} / ${history.length}`}</span>
                <button
                  onClick={() => setViewIndex(-1)}
                  disabled={viewIndex === -1}
                  className="transition-colors disabled:opacity-40"
                  style={{ color: viewIndex === -1 ? '#EF4444' : 'var(--ct-text-muted)' }}
                >
                  Live ●
                </button>
              </div>
              <input
                type="range"
                min={0}
                max={history.length - 1}
                value={viewIndex === -1 ? history.length - 1 : viewIndex}
                onChange={(e) => {
                  const val = parseInt(e.target.value);
                  setViewIndex(val === history.length - 1 ? -1 : val);
                }}
                className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                style={{ accentColor: 'var(--ct-gold)' }}
              />
            </div>
          )}
        </div>

        {/* Analysis Column */}
        <div className="lg:col-span-7 space-y-4">
          <div className="glass-panel p-5 rounded-2xl space-y-5">
            {/* Win Gauge */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs uppercase font-bold tracking-wider" style={{ color: '#30C670' }}>
                  Win Probability
                </span>
                <span className="text-xl font-extrabold font-mono" style={{ color: '#30C670' }}>
                  {((currentFrame.win_probability ?? 0.5) * 100).toFixed(1)}%
                </span>
              </div>
              <div className="h-3 rounded-full overflow-hidden" style={{ background: 'var(--ct-navy)' }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${(currentFrame.win_probability ?? 0.5) * 100}%`,
                    background: 'linear-gradient(90deg, #30C670, var(--ct-gold))',
                  }}
                />
              </div>
            </div>

            {/* Collapse Gauge */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs uppercase font-bold tracking-wider" style={{ color: '#EF4444' }}>
                  Collapse Risk
                </span>
                <span className="text-xl font-extrabold font-mono" style={{ color: '#EF4444' }}>
                  {((currentFrame.collapse_probability ?? 0.1) * 100).toFixed(1)}%
                </span>
              </div>
              <div className="h-3 rounded-full overflow-hidden" style={{ background: 'var(--ct-navy)' }}>
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${(currentFrame.collapse_probability ?? 0.1) * 100}%`,
                    background: 'linear-gradient(90deg, #F97316, #DC2626)',
                  }}
                />
              </div>
            </div>

            {/* SHAP Narrative */}
            <div
              className="rounded-xl p-4 space-y-2"
              style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.05)' }}
            >
              <div className="flex items-center gap-2 text-xs font-bold" style={{ color: 'var(--ct-text-secondary)' }}>
                <Zap className="w-4 h-4" style={{ color: '#EF4444' }} />
                Live SHAP Narrative
              </div>
              <p className="text-sm italic leading-relaxed" style={{ color: 'var(--ct-text-secondary)' }}>
                {currentFrame.narrative_summary || 'Spectating live game stream…'}
              </p>
            </div>

            {/* Live Move List */}
            {history.length > 0 && (
              <div
                className="rounded-xl p-4 space-y-3"
                style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.05)' }}
              >
                <div className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--ct-text-muted)' }}>
                  Live Game Moves
                </div>
                <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto">
                  {history.map((m, i) => (
                    <button
                      key={i}
                      onClick={() => setViewIndex(i)}
                      className="text-xs px-2.5 py-1 rounded-lg font-mono font-medium transition-all duration-150"
                      style={
                        (viewIndex === -1 ? i === history.length - 1 : viewIndex === i)
                          ? { background: 'rgba(239,68,68,0.15)', color: '#EF4444', border: '1px solid rgba(239,68,68,0.25)' }
                          : { background: 'var(--ct-navy-2)', color: 'var(--ct-text-secondary)', border: '1px solid rgba(255,255,255,0.04)' }
                      }
                    >
                      {m.color === 'white' || !m.color ? `${m.move_number || Math.ceil((m.ply || 0) / 2)}.` : ''}{' '}
                      {m.san || m.uci || '…'}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
