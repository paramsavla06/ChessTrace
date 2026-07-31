import React, { useState, useEffect } from 'react';
import { Chessboard } from 'react-chessboard';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
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

  useEffect(() => {
    const loadGameData = async () => {
      setLoading(true);
      try {
        const metaRes = await api.get(`/games/${gameId}`);
        setGameMeta(metaRes.data);

        const timelineRes = await api.get<TimelineMove[]>(`/games/${gameId}/timeline`);
        setTimeline(timelineRes.data);
        setCurrentIndex(0);
      } catch (err) {
        console.error('Failed loading game review data', err);
      } finally {
        setLoading(false);
      }
    };
    loadGameData();
  }, [gameId]);

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
      {/* Header Bar */}
      {gameMeta && (
        <div className="glass-panel p-6 rounded-2xl flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs text-indigo-400 font-semibold uppercase tracking-wider">
              <span>{gameMeta.event || 'Blitz Game'}</span>
              <span>•</span>
              <span>{gameMeta.time_control || 'Blitz'}</span>
            </div>
            <h1 className="text-2xl font-bold text-white mt-1">
              {gameMeta.white_player || 'White'} ({gameMeta.white_elo || '?'}) vs{' '}
              {gameMeta.black_player || 'Black'} ({gameMeta.black_elo || '?'})
            </h1>
          </div>

          <div className="flex items-center gap-4 bg-slate-900/60 px-4 py-2 rounded-xl border border-slate-800">
            <span className="text-sm font-semibold text-slate-300">Result: {gameMeta.result}</span>
            <span className="text-xs text-slate-500 font-mono">ECO: {gameMeta.eco || 'A00'}</span>
          </div>
        </div>
      )}

      {/* Main Grid: Board + Controls + Narrative */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left 5 Cols: Interactive Chessboard */}
        <div className="lg:col-span-5 space-y-6">
          <div className="glass-panel p-4 rounded-2xl aspect-square flex items-center justify-center glow-indigo">
            <Chessboard
              options={{
                position: currentMove ? currentMove.fen : 'start',
              }}
            />
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

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {eloSimResult.top_candidate_moves.map((cand, i) => (
                  <div key={i} className="bg-slate-900/50 p-3 rounded-xl border border-slate-800 text-xs flex justify-between items-center">
                    <div>
                      <span className="font-bold text-white text-sm">{cand.san}</span>
                      <span className="text-slate-500 ml-2">({cand.uci})</span>
                    </div>
                    <div className="text-right">
                      <span className="text-indigo-400 font-bold">{(cand.probability * 100).toFixed(1)}%</span>
                      <p className="text-[10px] text-slate-500">{cand.expected_think_time_sec}s think</p>
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
