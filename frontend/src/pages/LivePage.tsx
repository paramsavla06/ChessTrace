import React, { useState, useEffect } from 'react';
import { Chessboard } from 'react-chessboard';
import { Radio, Zap } from 'lucide-react';

interface LivePageProps {
  gameId: number;
}

export const LivePage: React.FC<LivePageProps> = ({ gameId }) => {
  const [fen, setFen] = useState<string>('start');
  const [winProb, setWinProb] = useState<number>(0.5);
  const [collapseProb, setCollapseProb] = useState<number>(0.1);
  const [narrative, setNarrative] = useState<string>('Spectating live game stream...');
  const [connected, setConnected] = useState<boolean>(false);
  const [inputGameId, setInputGameId] = useState<string>(gameId.toString());

  useEffect(() => {
    let cleanId = inputGameId.trim();
    if (cleanId.includes('lichess.org/')) {
      const parts = cleanId.split('lichess.org/')[1].split('/');
      cleanId = parts[0];
    }

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/api/v1/ws/live/${cleanId || gameId}`;

    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      setConnected(true);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.fen) setFen(data.fen);
        if (data.win_probability !== undefined) setWinProb(data.win_probability);
        if (data.collapse_probability !== undefined) setCollapseProb(data.collapse_probability);
        if (data.narrative_summary) setNarrative(data.narrative_summary);
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
      {/* Top Banner */}
      <div className="glass-panel p-6 rounded-2xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Radio className={`w-6 h-6 ${connected ? 'text-pink-500 animate-pulse' : 'text-slate-500'}`} />
          <div>
            <h1 className="text-2xl font-bold text-white">Live Spectate Room</h1>
            <p className="text-xs text-slate-400">
              {connected ? `Connected to live stream for game #${inputGameId}` : 'Disconnected'}
            </p>
          </div>
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

      {/* Main Spectating Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Board */}
        <div className="lg:col-span-5 flex justify-center">
          <div className="glass-panel p-4 rounded-2xl w-full max-w-[460px] aspect-square flex items-center justify-center glow-pink mx-auto">
            <Chessboard position={fen} />
          </div>
        </div>

        {/* Real-Time ML Gauges */}
        <div className="lg:col-span-7 space-y-6">
          <div className="glass-panel p-6 rounded-2xl space-y-6">
            <div className="flex justify-between items-center">
              <span className="text-xs uppercase font-bold text-indigo-400">Real-Time Win Gauge</span>
              <span className="text-2xl font-extrabold text-emerald-400">{(winProb * 100).toFixed(1)}%</span>
            </div>
            <div className="w-full bg-slate-900 h-4 rounded-full overflow-hidden p-0.5 border border-slate-800">
              <div
                className="bg-gradient-to-r from-emerald-500 to-indigo-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${winProb * 100}%` }}
              />
            </div>

            <div className="flex justify-between items-center">
              <span className="text-xs uppercase font-bold text-pink-400">Collapse Risk Gauge</span>
              <span className="text-2xl font-extrabold text-pink-400">{(collapseProb * 100).toFixed(1)}%</span>
            </div>
            <div className="w-full bg-slate-900 h-4 rounded-full overflow-hidden p-0.5 border border-slate-800">
              <div
                className="bg-gradient-to-r from-pink-500 to-rose-600 h-full rounded-full transition-all duration-500"
                style={{ width: `${collapseProb * 100}%` }}
              />
            </div>

            {/* Live SHAP Narrative Stream */}
            <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-300">
                <Zap className="w-4 h-4 text-pink-400" />
                <span>Sub-Second Live SHAP Stream</span>
              </div>
              <p className="text-sm text-slate-300 italic">{narrative}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
