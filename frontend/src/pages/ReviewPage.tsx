import React, { useState, useEffect } from 'react';
import { Chessboard } from 'react-chessboard';
import { Chess } from 'chess.js';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

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
import {
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Zap,
  TrendingDown,
  Brain,
  Sliders,
  AlertTriangle,
  Sparkles,
} from 'lucide-react';
import { api } from '../api/client';
import type { TimelineMove, PredictResponse, WhatIfResponse, EloSimResponse } from '../api/client';

interface ReviewPageProps {
  gameId: number;
}

export const ReviewPage: React.FC<ReviewPageProps> = ({ gameId }) => {
  const [allGames, setAllGames] = useState<any[]>([]);
  const [activeGameId, setActiveGameId] = useState<number>(gameId);
  const [timeline, setTimeline] = useState<TimelineMove[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [gameMeta, setGameMeta] = useState<any>(null);

  // Advanced Analysis State
  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResponse | null>(null);
  const [eloSimResult, setEloSimResult] = useState<EloSimResponse | null>(null);
  const [altMoveInput, setAltMoveInput] = useState<string>('');
  const [selectedElo, setSelectedElo] = useState<string>('1600-1800');

  // Load available games list
  useEffect(() => {
    const fetchGamesList = async () => {
      try {
        const res = await api.get('/games');
        setAllGames(res.data);
        if (res.data.length > 0 && !activeGameId) {
          setActiveGameId(res.data[0].id);
        }
      } catch (err) {
        console.error('Failed fetching games list', err);
      }
    };
    fetchGamesList();
  }, []);

  useEffect(() => {
    const targetId = activeGameId || gameId;
    if (!targetId) return;

    const loadGameData = async () => {
      setLoading(true);
      try {
        const metaRes = await api.get(`/games/${targetId}`);
        setGameMeta(metaRes.data);

        const timelineRes = await api.get<TimelineMove[]>(`/games/${targetId}/timeline`);
        setTimeline(timelineRes.data);
        setCurrentIndex(0);
      } catch (err) {
        console.error('Failed loading game review data', err);
      } finally {
        setLoading(false);
      }
    };
    loadGameData();
  }, [activeGameId, gameId]);

  // Keyboard Arrow Navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') {
        setCurrentIndex((prev) => Math.max(0, prev - 1));
      } else if (e.key === 'ArrowRight') {
        setCurrentIndex((prev) => Math.min(timeline.length - 1, prev + 1));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [timeline.length]);

  const currentMove = timeline[currentIndex] || null;

  // Run ML Prediction on move change
  useEffect(() => {
    if (!currentMove) return;

    const fetchMovePredict = async () => {
      try {
        const res = await api.post<PredictResponse>('/analysis/predict', {
          fen: currentMove.fen,
          think_time_sec: currentMove.think_time_sec,
          time_remaining_sec: currentMove.time_remaining_sec,
        });
        setPrediction(res.data);
      } catch (err) {
        console.error('Prediction failed', err);
      }
    };

    fetchMovePredict();
  }, [currentIndex, currentMove]);

  // Run ELO Simulator on target ELO change
  useEffect(() => {
    if (!currentMove) return;
    const fetchEloSim = async () => {
      try {
        const res = await api.post<EloSimResponse>('/analysis/elo-sim', {
          fen: currentMove.fen,
          target_elo_bucket: selectedElo,
          time_remaining_sec: currentMove.time_remaining_sec,
        });
        setEloSimResult(res.data);
      } catch (err) {
        console.error('ELO Sim failed', err);
      }
    };
    fetchEloSim();
  }, [currentIndex, selectedElo, currentMove]);

  const handleWhatIfSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentMove || !altMoveInput.trim()) return;

    try {
      const res = await api.post<WhatIfResponse>('/analysis/what-if', {
        fen: currentMove.fen,
        played_move_uci: currentMove.uci,
        alternative_move_uci: altMoveInput.trim(),
        think_time_sec: currentMove.think_time_sec,
        time_remaining_sec: currentMove.time_remaining_sec,
      });
      setWhatIfResult(res.data);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Invalid alternative UCI move!');
    }
  };

  if (loading) {
    return (
      <div className="py-24 text-center text-slate-400">
        Loading game #{gameId} timeline and neural feature metrics...
      </div>
    );
  }

  const chartData = timeline.map((m) => ({
    ply: m.ply,
    move: `${m.move_number}.${m.color === 'white' ? 'w' : 'b'}`,
    thinkTime: m.think_time_sec,
    clock: m.time_remaining_sec,
    isPressure: m.is_time_pressure_30s,
  }));

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
      {/* Game Header Banner */}
      <div className="glass-panel p-6 rounded-2xl flex flex-wrap justify-between items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white font-mono">
              {gameMeta?.white_player || 'White'} vs {gameMeta?.black_player || 'Black'}
            </h1>
            <span className="px-3 py-1 rounded-full text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono">
              {gameMeta?.eco || 'A00'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            {gameMeta?.event} • Result: {gameMeta?.result} • TC: {gameMeta?.time_control}
          </p>
        </div>

        <div className="flex items-center gap-4">
          {/* Game Selection Dropdown */}
          {allGames.length > 0 && (
            <div className="flex items-center gap-2">
              <label className="text-xs font-mono text-slate-400">Select Game:</label>
              <select
                value={activeGameId}
                onChange={(e) => setActiveGameId(Number(e.target.value))}
                className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-indigo-300 font-mono focus:outline-none focus:border-indigo-500 shadow-md cursor-pointer hover:border-indigo-400 transition-colors"
              >
                {allGames.map((g) => (
                  <option key={g.id} value={g.id}>
                    #{g.id}: {g.white_player} vs {g.black_player} ({g.result})
                  </option>
                ))}
              </select>
            </div>
          )}

          <a
            href={`/api/v1/games/${activeGameId || gameId}/export-pgn`}
            download
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 font-medium text-xs border border-indigo-500/30 transition-all font-mono shadow-md"
          >
            <span>Download PGN</span>
          </a>
        </div>
      </div>

      {/* Main Grid: Board + Controls + Narrative */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left 5 Cols: Interactive Chessboard + Vertical Eval Bar */}
        <div className="lg:col-span-5 space-y-6">
          <div className="flex items-center justify-center gap-3">
            {/* Vertical Evaluation Bar */}
            <div className="w-6 h-[440px] bg-slate-950 rounded-xl overflow-hidden border border-slate-800 flex flex-col justify-between relative shadow-2xl">
              {/* Black Advantage (Top) */}
              <div
                className="bg-slate-900 w-full transition-all duration-500 ease-out"
                style={{ height: `${100 - Math.max(8, Math.min(92, 50 + ((prediction ? (prediction.win_probability * 2 - 1) * 3.5 : 0.21) * 10)))}%` }}
              />
              {/* White Advantage (Bottom) */}
              <div
                className="bg-slate-100 w-full transition-all duration-500 ease-out"
                style={{ height: `${Math.max(8, Math.min(92, 50 + ((prediction ? (prediction.win_probability * 2 - 1) * 3.5 : 0.21) * 10)))}%` }}
              />
              {/* Centered Eval Score Badge */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <span className={`text-[10px] font-extrabold font-mono px-1 py-0.5 rounded shadow ${
                  (prediction ? (prediction.win_probability * 2 - 1) * 3.5 : 0.21) >= 0
                    ? 'bg-slate-900 text-white border border-slate-700'
                    : 'bg-white text-slate-900 border border-slate-300'
                }`}>
                  {(prediction ? (prediction.win_probability * 2 - 1) * 3.5 : 0.21) >= 0 ? '+' : ''}
                  {(prediction ? (prediction.win_probability * 2 - 1) * 3.5 : 0.21).toFixed(2)}
                </span>
              </div>
            </div>

            {/* Interactive Chessboard */}
            <div className="glass-panel p-4 rounded-2xl w-full max-w-[440px] aspect-square flex items-center justify-center glow-indigo">
              <Chessboard
                position={fenToPositionObj(currentMove ? currentMove.fen : 'start')}
                customBoardStyle={{
                  borderRadius: '12px',
                  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
                }}
              />
            </div>
          </div>

          {/* Stepper Controls */}
          <div className="glass-panel p-4 rounded-2xl flex items-center justify-between">
            <button
              onClick={() => setCurrentIndex(0)}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
            >
              <RotateCcw className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3">
              <button
                disabled={currentIndex === 0}
                onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
                className="p-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 text-white transition-all"
              >
                <ChevronLeft className="w-6 h-6" />
              </button>

              <span className="text-sm font-semibold text-slate-300 font-mono min-w-[80px] text-center">
                {currentIndex + 1} / {timeline.length}
              </span>

              <button
                disabled={currentIndex === timeline.length - 1}
                onClick={() => setCurrentIndex((prev) => Math.min(timeline.length - 1, prev + 1))}
                className="p-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 text-white transition-all"
              >
                <ChevronRight className="w-6 h-6" />
              </button>
            </div>

            <span className="text-xs font-bold px-3 py-1.5 rounded-lg bg-slate-800 text-indigo-400 font-mono">
              {currentMove ? currentMove.san : 'Start'}
            </span>
          </div>
        </div>

        {/* Right 7 Cols: Analysis, SHAP, What-If & ELO Sim */}
        <div className="lg:col-span-7 space-y-6">
          {/* Win & Collapse Probability Card */}
          {prediction && (
            <div className="glass-panel p-6 rounded-2xl space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
                  <Zap className="w-4 h-4" />
                  <span>XGBoost Intelligence Predictions</span>
                </div>
                {prediction.time_pressure_risk_multiplier > 1.0 && (
                  <span className="flex items-center gap-1 text-xs font-bold text-pink-400 bg-pink-950/60 border border-pink-800 px-2.5 py-1 rounded-full animate-pulse">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    {prediction.time_pressure_risk_multiplier}x Time Stress Multiplier
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                  <p className="text-xs text-slate-400 uppercase font-semibold">Win Probability</p>
                  <p className="text-3xl font-extrabold text-emerald-400 mt-1">
                    {(prediction.win_probability * 100).toFixed(1)}%
                  </p>
                </div>

                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                  <p className="text-xs text-slate-400 uppercase font-semibold">Collapse Probability</p>
                  <p className="text-3xl font-extrabold text-pink-400 mt-1">
                    {(prediction.collapse_probability * 100).toFixed(1)}%
                  </p>
                </div>
              </div>

              {/* SHAP Narrative */}
              <div className="bg-slate-900/40 p-4 rounded-xl border border-slate-800 space-y-2">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-300">
                  <Brain className="w-4 h-4 text-indigo-400" />
                  <span>SHAP Plain-English Narrative</span>
                </div>
                <p className="text-sm text-slate-300 italic">{prediction.narrative_summary}</p>
              </div>
            </div>
          )}

          {/* Counterfactual What-If Brancher */}
          <div className="glass-panel p-6 rounded-2xl space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <Sliders className="w-4 h-4 text-pink-400" />
              <span>Counterfactual What-If Divergence Analysis</span>
            </div>

            <form onSubmit={handleWhatIfSubmit} className="flex gap-3">
              <input
                type="text"
                placeholder="Enter alternative UCI move (e.g. g1f3)..."
                value={altMoveInput}
                onChange={(e) => setAltMoveInput(e.target.value)}
                className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <button
                type="submit"
                className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl text-xs font-semibold transition-all"
              >
                Evaluate Divergence
              </button>
            </form>

            {whatIfResult && (
              <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-2 text-xs">
                <div className="flex justify-between text-slate-300 font-semibold">
                  <span>Played ({whatIfResult.played_move.uci}): {(whatIfResult.played_move.win_probability * 100).toFixed(1)}% win</span>
                  <span>Alternative ({whatIfResult.alternative_move.uci}): {(whatIfResult.alternative_move.win_probability * 100).toFixed(1)}% win</span>
                </div>
                <p className="text-emerald-400 font-semibold mt-1">
                  {whatIfResult.probability_divergence.recommendation}
                </p>
              </div>
            )}
          </div>

          {/* ELO Simulator Overlay */}
          {eloSimResult && (
            <div className="glass-panel p-6 rounded-2xl space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm font-semibold text-white">
                  <Sparkles className="w-4 h-4 text-indigo-400" />
                  <span>ELO Simulation Candidate Moves</span>
                </div>

                <select
                  value={selectedElo}
                  onChange={(e) => setSelectedElo(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1 text-xs text-indigo-300 font-semibold focus:outline-none"
                >
                  <option value="<1000">&lt; 1000 ELO</option>
                  <option value="1200-1400">1200-1400 ELO</option>
                  <option value="1600-1800">1600-1800 ELO</option>
                  <option value="2000+">2000+ ELO</option>
                </select>
              </div>

              <div className="space-y-3">
                {eloSimResult.top_candidate_moves.map((cand, i) => (
                  <div key={i} className="bg-slate-900/50 p-3 rounded-xl border border-slate-800 space-y-1.5 text-xs">
                    <div className="flex justify-between items-center">
                      <div>
                        <span className="font-bold text-white text-sm font-mono">{cand.san}</span>
                        <span className="text-slate-500 ml-2 font-mono">({cand.uci})</span>
                        {cand.is_engine_top_choice && (
                          <span className="ml-2 px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold text-[10px]">
                            Stockfish Best
                          </span>
                        )}
                      </div>
                      <span className="text-indigo-400 font-bold font-mono">{(cand.probability * 100).toFixed(1)}%</span>
                    </div>

                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                      <div
                        className="bg-indigo-500 h-full rounded-full transition-all"
                        style={{ width: `${Math.min(100, cand.probability * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Full-Width Chart: Think Time & Clock Heatmap */}
      <div className="glass-panel p-6 rounded-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <TrendingDown className="w-5 h-5 text-indigo-400" />
            <span>Think Time & Clock Pressure Heatmap</span>
          </h3>
          <span className="text-xs text-slate-400">Seconds spent per move throughout the game</span>
        </div>

        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="thinkColor" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366F1" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#6366F1" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="move" stroke="#64748B" fontSize={11} />
              <YAxis stroke="#64748B" fontSize={11} unit="s" />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0F172A',
                  borderColor: '#334155',
                  borderRadius: '12px',
                  color: '#fff',
                }}
              />
              <Area type="monotone" dataKey="thinkTime" stroke="#6366F1" fillOpacity={1} fill="url(#thinkColor)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
