import React, { useState, useEffect } from 'react';
import { Chessboard } from 'react-chessboard';
import { Chess } from 'chess.js';
import { Radio, Zap } from 'lucide-react';

function fenToPositionObj(fen: string): Record<string, string> | 'start' {
  if (!fen || fen === 'start') return 'start';
  try {
    const chess = new Chess(fen);
    const board = chess.board();
    const pos: Record<string, string> = {};
    const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        const piece = board[r][c];
        if (piece) {
          const square = `${files[c]}${8 - r}`;
          pos[square] = `${piece.color}${piece.type.toUpperCase()}`;
        }
      }
    }
    return pos;
  } catch (err) {
    return 'start';
  }
}

interface LivePageProps {
  gameId: number;
}

interface LiveFrame {
  fen: string;
  win_probability?: number;
  collapse_probability?: number;
  narrative_summary?: string;
  ply?: number;
}

export const LivePage: React.FC<LivePageProps> = ({ gameId }) => {
  const [history, setHistory] = useState<LiveFrame[]>([]);
  const [viewIndex, setViewIndex] = useState<number>(-1); // -1 means live (latest)

  const [connected, setConnected] = useState<boolean>(false);
  const [inputGameId, setInputGameId] = useState<string>('');
  const [boardOrientation, setBoardOrientation] = useState<'white' | 'black'>('white');

  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const currentFrame = viewIndex === -1 ? (history[history.length - 1] || { fen: 'start' }) : history[viewIndex];

  useEffect(() => {
    let cleanId = inputGameId.trim();
    let orientation: 'white' | 'black' = 'white';
    
    // Parse /black or /white from the end of the URL
    if (cleanId.endsWith('/black') || cleanId.endsWith('#black')) {
      orientation = 'black';
      cleanId = cleanId.replace(/\/black|#black$/, '');
    } else if (cleanId.endsWith('/white') || cleanId.endsWith('#white')) {
      cleanId = cleanId.replace(/\/white|#white$/, '');
    }

    if (cleanId.includes('lichess.org/')) {
      const parts = cleanId.split('lichess.org/')[1].split(/[/#]/);
      cleanId = parts[0];
      if (parts.length > 1 && parts[1] === 'black') {
        orientation = 'black';
      }
    }
    
    setBoardOrientation(orientation);

    if (!cleanId || cleanId.length < 8) {
      setConnected(false);
      setErrorMsg(null);
      return;
    }

    const wsUrl = `ws://localhost:8000/api/v1/ws/live/${cleanId}`;

    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      setConnected(true);
      setErrorMsg(null);
      setHistory([]);
      setViewIndex(-1);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.error) {
          setErrorMsg(data.error);
          socket.close();
          return;
        }
        
        setHistory(prev => {
          const newHistory = [...prev];
          const existingIdx = newHistory.findIndex(f => f.ply === data.ply);
          if (existingIdx !== -1) {
            newHistory[existingIdx] = data;
          } else {
            newHistory.push(data);
          }
          return newHistory.sort((a, b) => (a.ply || 0) - (b.ply || 0));
        });
      } catch (err) {
        console.error('Failed parsing WS frame', err);
      }
    };

    socket.onclose = () => {
      setConnected(false);
    };

    return () => {
      socket.close();
    };
  }, [inputGameId, gameId]);

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
      {/* Top Bar */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2 text-white">
            <Radio className="w-6 h-6 text-pink-500" />
            Live Spectate Room
          </h2>
          <p className="text-sm text-slate-400">
            {connected
              ? `Connected to live stream for game #${inputGameId.trim().split('/').pop()}`
              : 'Disconnected'}
          </p>
        </div>

        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Enter Lichess / Local Game ID..."
            value={inputGameId}
            onChange={(e) => setInputGameId(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 text-xs text-white focus:outline-none focus:border-pink-500"
          />
        </div>
      </div>

      {errorMsg && (
        <div className="bg-red-500/20 border border-red-500/50 text-red-400 px-4 py-3 rounded-xl text-sm flex justify-between items-center">
          <p>{errorMsg}</p>
          <button onClick={() => setErrorMsg(null)} className="text-red-400 hover:text-white font-bold ml-4">✕</button>
        </div>
      )}

      {/* Main Spectating Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Board & Controls */}
        <div className="lg:col-span-5 flex flex-col justify-center gap-4">
          <div className="glass-panel p-4 rounded-2xl w-full max-w-[460px] aspect-square flex items-center justify-center glow-pink mx-auto relative">
            <Chessboard position={currentFrame.fen} boardOrientation={boardOrientation} arePiecesDraggable={false} />
            
            {viewIndex !== -1 && (
              <div className="absolute top-2 right-2 bg-yellow-500 text-black text-xs font-bold px-2 py-1 rounded">
                Viewing History
              </div>
            )}
          </div>
          
          {history.length > 0 && (
            <div className="w-full max-w-[460px] mx-auto space-y-2">
              <div className="flex justify-between items-center text-xs text-slate-400 font-bold px-2">
                <button 
                  onClick={() => setViewIndex(0)}
                  disabled={viewIndex === 0}
                  className="hover:text-white disabled:opacity-50"
                >Start</button>
                <div className="flex-1 px-4">
                  <input
                    type="range"
                    min={0}
                    max={history.length - 1}
                    value={viewIndex === -1 ? history.length - 1 : viewIndex}
                    onChange={(e) => {
                      const val = parseInt(e.target.value);
                      if (val === history.length - 1) setViewIndex(-1);
                      else setViewIndex(val);
                    }}
                    className="w-full h-1 bg-slate-700 rounded-lg appearance-none cursor-pointer"
                  />
                </div>
                <button 
                  onClick={() => setViewIndex(-1)}
                  disabled={viewIndex === -1}
                  className="hover:text-white disabled:opacity-50 text-pink-400"
                >Live</button>
              </div>
            </div>
          )}
        </div>

        {/* Real-Time ML Gauges */}
        <div className="lg:col-span-7 space-y-6">
          <div className="glass-panel p-6 rounded-2xl space-y-6">
            <div className="flex justify-between items-center">
              <span className="text-xs uppercase font-bold text-indigo-400">Real-Time Win Gauge</span>
              <span className="text-2xl font-extrabold text-emerald-400">{((currentFrame.win_probability ?? 0.5) * 100).toFixed(1)}%</span>
            </div>
            <div className="w-full bg-slate-900 h-4 rounded-full overflow-hidden p-0.5 border border-slate-800">
              <div
                className="bg-gradient-to-r from-emerald-500 to-indigo-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${(currentFrame.win_probability ?? 0.5) * 100}%` }}
              />
            </div>

            <div className="flex justify-between items-center">
              <span className="text-xs uppercase font-bold text-pink-400">Collapse Risk Gauge</span>
              <span className="text-2xl font-extrabold text-pink-400">{((currentFrame.collapse_probability ?? 0.1) * 100).toFixed(1)}%</span>
            </div>
            <div className="w-full bg-slate-900 h-4 rounded-full overflow-hidden p-0.5 border border-slate-800">
              <div
                className="bg-gradient-to-r from-pink-500 to-rose-600 h-full rounded-full transition-all duration-500"
                style={{ width: `${(currentFrame.collapse_probability ?? 0.1) * 100}%` }}
              />
            </div>

            {/* Live SHAP Narrative Stream */}
            <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-300">
                <Zap className="w-4 h-4 text-pink-400" />
                <span>Sub-Second Live SHAP Stream</span>
              </div>
              <p className="text-sm text-slate-300 italic">{currentFrame.narrative_summary || 'Spectating live game stream...'}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
