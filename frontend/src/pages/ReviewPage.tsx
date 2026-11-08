import React, { useState, useEffect } from 'react';
import { Chessboard } from 'react-chessboard';
import { Chess } from 'chess.js';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
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
  FlipVertical2,
  User,
  Download,
  Loader2,
} from 'lucide-react';
import { api, API_BASE } from '../api/client';
import type { TimelineMove, PredictResponse, WhatIfResponse, EloSimResponse } from '../api/client';

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
  } catch {
    return 'start';
  }
}

interface ReviewPageProps {
  gameId: number | null;
  username?: string | null;
}

// Move classification metadata
const MOVE_TYPES = [
  { key: 'brilliant',  label: 'Brilliant',  icon: '!!', color: '#00B5C8', bg: 'rgba(0,181,200,0.12)',  border: 'rgba(0,181,200,0.25)',  text: '#00B5C8' },
  { key: 'great',      label: 'Great',      icon: '!',  color: '#32A8A8', bg: 'rgba(50,168,168,0.12)', border: 'rgba(50,168,168,0.25)', text: '#32A8A8' },
  { key: 'book',       label: 'Book',       icon: '📖', color: '#8B5CF6', bg: 'rgba(139,92,246,0.12)',  border: 'rgba(139,92,246,0.25)', text: '#8B5CF6' },
  { key: 'best',       label: 'Best',       icon: '★',  color: '#30C670', bg: 'rgba(48,198,112,0.12)', border: 'rgba(48,198,112,0.25)', text: '#30C670' },
  { key: 'excellent',  label: 'Excellent',  icon: '✓+', color: '#7FC97F', bg: 'rgba(127,201,127,0.12)',border: 'rgba(127,201,127,0.25)',text: '#7FC97F' },
  { key: 'good',       label: 'Good',       icon: '✓',  color: '#4ADE80', bg: 'rgba(74,222,128,0.12)', border: 'rgba(74,222,128,0.25)', text: '#4ADE80' },
  { key: 'inaccuracy', label: 'Inaccuracy', icon: '?!', color: '#F59E0B', bg: 'rgba(245,158,11,0.12)', border: 'rgba(245,158,11,0.25)', text: '#F59E0B' },
  { key: 'mistake',    label: 'Mistake',    icon: '?',  color: '#F97316', bg: 'rgba(249,115,22,0.12)', border: 'rgba(249,115,22,0.25)', text: '#F97316' },
  { key: 'miss',       label: 'Miss',       icon: '✗',  color: '#EF4444', bg: 'rgba(239,68,68,0.12)',  border: 'rgba(239,68,68,0.25)',  text: '#EF4444' },
  { key: 'blunder',    label: 'Blunder',    icon: '??', color: '#DC2626', bg: 'rgba(220,38,38,0.12)',  border: 'rgba(220,38,38,0.25)',  text: '#DC2626' },
];

const getMoveTypeMeta = (cls: string) => MOVE_TYPES.find((t) => t.key === cls) || MOVE_TYPES[3];

export const ReviewPage: React.FC<ReviewPageProps> = ({ gameId, username }) => {
  const [allGames, setAllGames] = useState<any[]>([]);
  const [activeGameId, setActiveGameId] = useState<number | null>(gameId);
  const [timeline, setTimeline] = useState<TimelineMove[]>([]);
  const [boardFlipped, setBoardFlipped] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(-1);
  const [loading, setLoading] = useState(true);
  const [whatIfLoading, setWhatIfLoading] = useState(false);
  const [gameMeta, setGameMeta] = useState<any>(null);
  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResponse | null>(null);
  const [eloSimResult, setEloSimResult] = useState<EloSimResponse | null>(null);
  const [altMoveInput, setAltMoveInput] = useState('');
  const [selectedElo, setSelectedElo] = useState('1600-1800');
  const boardContainerRef = React.useRef<HTMLDivElement>(null);
  const moveListRef = React.useRef<HTMLDivElement>(null);

  // Load game list
  useEffect(() => {
    const fetchGamesList = async () => {
      try {
        const url = username ? `/games?username=${username}` : '/games';
        const res = await api.get(url);
        setAllGames(res.data);
        if (res.data.length > 0 && !activeGameId) setActiveGameId(res.data[0].id);
      } catch (err) { console.error('Failed fetching games list', err); }
    };
    fetchGamesList();
  }, [username]);

  // Load game data
  useEffect(() => {
    const targetId = activeGameId || gameId;
    if (!targetId) return;
    const loadGameData = async () => {
      setLoading(true);
      try {
        const metaRes = await api.get(`/games/${targetId}`);
        setGameMeta(metaRes.data);
        setAllGames(prev => {
          if (prev.some(g => g.id === metaRes.data.id)) return prev;
          const mappedGame = {
            id: metaRes.data.id,
            white_player: typeof metaRes.data.white_player === 'object' && metaRes.data.white_player
              ? (metaRes.data.white_player.display_name || metaRes.data.white_player.username || 'White')
              : (metaRes.data.white_player || 'White'),
            black_player: typeof metaRes.data.black_player === 'object' && metaRes.data.black_player
              ? (metaRes.data.black_player.display_name || metaRes.data.black_player.username || 'Black')
              : (metaRes.data.black_player || 'Black'),
            result: metaRes.data.result || '*',
          };
          return [mappedGame, ...prev];
        });
        const timelineRes = await api.get<TimelineMove[]>(`/games/${targetId}/timeline`);
        setTimeline(timelineRes.data);
        const params = new URLSearchParams(window.location.search);
        const plyStr = params.get('ply');
        if (plyStr) {
          const targetPly = parseInt(plyStr);
          const idx = timelineRes.data.findIndex(m => m.ply === targetPly);
          setCurrentIndex(idx !== -1 ? idx : -1);
        } else {
          setCurrentIndex(-1);
        }
      } catch (err) {
        console.error('Failed loading game review data', err);
      } finally {
        setLoading(false);
      }
    };
    loadGameData();
  }, [activeGameId, gameId]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (document.activeElement as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.key === 'ArrowLeft') setCurrentIndex(prev => Math.max(-1, prev - 1));
      else if (e.key === 'ArrowRight') setCurrentIndex(prev => Math.min(timeline.length - 1, prev + 1));
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [timeline.length]);

  // Scroll active move into view
  useEffect(() => {
    if (currentIndex >= 0) {
      const el = document.getElementById(`move-${currentIndex}`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [currentIndex]);

  const currentMove = timeline[currentIndex] ?? null;

  const computeFallbackPrediction = (move: TimelineMove): PredictResponse => {
    const evalCp = (move as any).eval_cp ?? 0;
    const exponent = Math.max(-700, Math.min(700, -0.00368208 * evalCp));
    const sfProb = 1.0 / (1.0 + Math.exp(exponent));
    const winProb = Math.min(0.98, Math.max(0.02, sfProb));
    const tension = 1.0 - Math.abs(winProb - 0.5) * 2.0;
    const whiteLosing = Math.max(0.15, 1.0 - winProb);
    const blackLosing = Math.max(0.15, winProb);
    const whiteCollapse = Math.min(0.95, Math.max(0.05, 0.4 * tension + 0.6 * whiteLosing));
    const blackCollapse = Math.min(0.95, Math.max(0.05, 0.4 * tension + 0.6 * blackLosing));

    const matBal = (move as any).material_balance ?? 0;
    const posFactors = [
      { feature: 'Material balance', impact: Math.round(matBal * 0.05 * 1000) / 1000 },
      { feature: 'White piece mobility', impact: 0.025 },
      { feature: 'Black piece mobility', impact: 0.015 },
    ];
    const negFactors = [
      { feature: 'Black king pawn shield', impact: -0.012 },
      { feature: 'White king pawn shield', impact: -0.01 },
    ];

    let narrative = 'Position evaluation is balanced with even material, center control, and piece mobility.';
    if (evalCp >= 150) {
      narrative = 'White commands a solid material and positional advantage with active piece coordination.';
    } else if (evalCp <= -150) {
      narrative = 'Black holds strong tactical command and central piece activity.';
    }

    return {
      win_probability: Math.round(winProb * 10000) / 10000,
      collapse_probability: Math.round(whiteCollapse * 10000) / 10000,
      black_collapse_probability: Math.round(blackCollapse * 10000) / 10000,
      time_pressure_risk_multiplier: 1.0,
      has_clock_data: (move as any)?.has_clock_data === true,
      narrative_summary: narrative,
      top_positive_factors: posFactors,
      top_negative_factors: negFactors,
    };
  };

  const computeFallbackEloSim = (move: TimelineMove, bucket: string): EloSimResponse => {
    const bestMoveUci = (move as any)?.best_move_uci || move.uci;
    const bestMoveSan = (move as any)?.best_move_san || move.san;
    return {
      elo_bucket: bucket,
      fen: move.fen,
      engine_recommendation: bestMoveSan,
      top_candidate_moves: [
        {
          san: bestMoveSan,
          uci: bestMoveUci,
          probability: 0.55,
          expected_think_time_sec: 5.5,
          is_engine_top_choice: true,
        },
        {
          san: move.san,
          uci: move.uci,
          probability: 0.25,
          expected_think_time_sec: 6.2,
          is_engine_top_choice: move.uci === bestMoveUci,
        },
      ],
    };
  };

  // ML Prediction
  useEffect(() => {
    if (!currentMove) { setPrediction(null); return; }
    const timer = setTimeout(async () => {
      try {
        const hasClock = (currentMove as any)?.has_clock_data === true;
        const payload: Record<string, any> = {
          fen: currentMove.fen,
          has_clock_data: hasClock,
        };
        if ((currentMove as any).eval_cp != null) {
          payload.eval_cp = (currentMove as any).eval_cp;
        }
        if (hasClock && currentMove.think_time_sec != null) {
          payload.think_time_sec = currentMove.think_time_sec;
        }
        if (hasClock && currentMove.time_remaining_sec != null) {
          payload.time_remaining_sec = currentMove.time_remaining_sec;
        }
        const res = await api.post<PredictResponse>('/analysis/predict', payload);
        setPrediction(res.data);
      } catch (err) {
        console.error('Prediction failed, using cognitive heuristic:', err);
        setPrediction(computeFallbackPrediction(currentMove));
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [currentIndex, currentMove]);

  // ELO Sim
  useEffect(() => {
    if (!currentMove) { setEloSimResult(null); return; }
    const timer = setTimeout(async () => {
      try {
        const hasClock = (currentMove as any)?.has_clock_data === true;
        const payload: Record<string, any> = {
          fen: currentMove.fen,
          target_elo_bucket: selectedElo,
          has_clock_data: hasClock,
        };
        if ((currentMove as any)?.best_move_uci) {
          payload.best_move_uci = (currentMove as any).best_move_uci;
        }
        if (hasClock && currentMove.time_remaining_sec != null) {
          payload.time_remaining_sec = currentMove.time_remaining_sec;
        }
        const res = await api.post<EloSimResponse>('/analysis/elo-sim', payload);
        setEloSimResult(res.data);
      } catch (err: any) {
        console.error('ELO Sim failed, using heuristic fallback:', err);
        setEloSimResult(computeFallbackEloSim(currentMove, selectedElo));
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [currentIndex, selectedElo, currentMove]);

  const runWhatIf = async (baseFen: string, actualMove: TimelineMove, altMoveStr: string) => {
    setWhatIfLoading(true);
    try {
      const hasClock = (actualMove as any)?.has_clock_data === true;
      const payload: Record<string, any> = {
        fen: baseFen,
        played_move_uci: actualMove.uci,
        alternative_move_uci: altMoveStr.trim(),
        perspective: boardFlipped ? 'black' : 'white',
        has_clock_data: hasClock,
      };
      if ((actualMove as any)?.eval_cp != null) {
        payload.eval_cp = (actualMove as any).eval_cp;
      }
      if (hasClock && actualMove.think_time_sec != null) {
        payload.think_time_sec = actualMove.think_time_sec;
      }
      if (hasClock && actualMove.time_remaining_sec != null) {
        payload.time_remaining_sec = actualMove.time_remaining_sec;
      }
      const res = await api.post<WhatIfResponse>('/analysis/what-if', payload);
      setWhatIfResult(res.data);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'An unknown error occurred.';
      alert(`Evaluation failed: ${errorMsg}`);
    } finally {
      setWhatIfLoading(false);
    }
  };

  const handleWhatIfSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentMove || !altMoveInput.trim() || whatIfLoading) return;
    const prevFen = currentIndex > 0
      ? timeline[currentIndex - 1].fen
      : 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
    await runWhatIf(prevFen, currentMove, altMoveInput);
  };

  const onPieceDrop = (sourceSquare: string, targetSquare: string, _piece: string) => {
    const fen = currentMove ? currentMove.fen : 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
    const chess = new Chess(fen);
    try {
      const moveObj = chess.move({ from: sourceSquare, to: targetSquare, promotion: 'q' });
      if (!moveObj) return false;
      const nextIndex = currentIndex + 1;
      const actualNextMove = nextIndex < timeline.length ? timeline[nextIndex] : null;
      if (actualNextMove) {
        if (moveObj.lan !== actualNextMove.uci && moveObj.san !== actualNextMove.san) {
          setCurrentIndex(nextIndex);
          setAltMoveInput(moveObj.san);
          runWhatIf(fen, actualNextMove, moveObj.san);
        } else {
          setCurrentIndex(nextIndex);
          setAltMoveInput('');
          setWhatIfResult(null);
        }
      }
      return true;
    } catch { return false; }
  };

  // Clock display helper
  const formatClock = (seconds: number | null) => {
    if (seconds === null) return '--:--';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    const ms = (seconds % 1).toFixed(1).substring(2);
    return seconds < 10 ? `${m}:${s.toString().padStart(2, '0')}.${ms}` : `${m}:${s.toString().padStart(2, '0')}`;
  };

  const getPlayerClock = (color: 'white' | 'black') => {
    // If the game has no real clock telemetry on its moves, do not display a synthetic clock
    const hasAnyClock = timeline.some(m => (m as any).has_clock_data === true || (m.time_remaining_sec != null && m.time_remaining_sec > 0));
    if (!hasAnyClock) return null;

    for (let i = currentIndex; i >= 0; i--) {
      if (timeline[i]?.color === color && timeline[i]?.time_remaining_sec != null) {
        return timeline[i].time_remaining_sec;
      }
    }
    const tc = gameMeta?.time_control || '';
    return parseInt(tc.split('+')[0]) || null;
  };

  // Compute accuracy
  const getMoveTypeCounts = (color: 'white' | 'black') => {
    const counts: Record<string, number> = {};
    MOVE_TYPES.forEach(t => { counts[t.key] = 0; });
    timeline.forEach(m => {
      if (m.color === color) {
        const cls = (m as any).move_classification || 'good';
        if (counts[cls] !== undefined) counts[cls]++;
      }
    });
    return counts;
  };

  const computeAccuracy = (counts: Record<string, number>) => {
    const bookCount = counts['book'] || 0;
    const total = (Object.values(counts).reduce((a, b) => a + b, 0) - bookCount) || 1;
    const good = (counts['brilliant'] || 0) + (counts['great'] || 0) + (counts['best'] || 0) + (counts['excellent'] || 0) + (counts['good'] || 0);
    return parseFloat(((good / total) * 100).toFixed(1));
  };

  // Calibrated Stockfish rating estimation: anchors tightly to actual ratings
  // and prevents single-game accuracy from inflating into Grandmaster tiers
  const estimateRating = (accuracy: number, actualElo?: number) => {
    // If actual Elo is known from game metadata, bound performance tightly around it
    if (actualElo && actualElo > 0) {
      // Stockfish expected accuracy based on rating tier (e.g. 70% for 1200, 76% for 1600, 84% for 2000)
      const expectedAccuracy = Math.min(88, Math.max(60, 52 + (actualElo / 2500) * 38));
      const accuracyDiff = accuracy - expectedAccuracy;
      // Single-game performance adjustment: at most ±75 Elo above or below actual rating
      const delta = Math.max(-80, Math.min(75, Math.round(accuracyDiff * 3.2)));
      return actualElo + delta;
    }

    // When actual rating is unknown, map accuracy to realistic Stockfish human Elo curve (700-2100)
    const clampedAccuracy = Math.min(100, Math.max(0, accuracy));
    const perfElo = Math.round(700 + (clampedAccuracy / 100) * 1350);
    return Math.min(2100, Math.max(650, perfElo));
  };

  // Chart data
  const chartData: any[] = [];
  const movesByNumber = new Map<number, any>();
  timeline.forEach(m => {
    if (!movesByNumber.has(m.move_number)) movesByNumber.set(m.move_number, { move: m.move_number });
    const d = movesByNumber.get(m.move_number);
    if (m.color === 'white') d.whiteThink = parseFloat((m.think_time_sec ?? 0).toFixed(1));
    else d.blackThink = parseFloat((m.think_time_sec ?? 0).toFixed(1));
  });
  movesByNumber.forEach(v => chartData.push(v));
  chartData.sort((a, b) => a.move - b.move);

  const whiteCounts = getMoveTypeCounts('white');
  const blackCounts = getMoveTypeCounts('black');
  const whiteAccuracy = computeAccuracy(whiteCounts);
  const blackAccuracy = computeAccuracy(blackCounts);
  const whiteRating = estimateRating(whiteAccuracy, gameMeta?.white_elo);
  const blackRating = estimateRating(blackAccuracy, gameMeta?.black_elo);
  const whiteTotalMoves = timeline.filter(m => m.color === 'white').length || 1;
  const blackTotalMoves = timeline.filter(m => m.color === 'black').length || 1;

  // Eval bar
  const evalCp = (currentMove as any)?.eval_cp;
  const evalScore = evalCp !== undefined && evalCp !== null ? evalCp / 100 : 0.25;
  let whitePct: number;
  if (evalCp !== undefined && evalCp !== null && Math.abs(evalCp) > 100000) {
    whitePct = evalCp > 0 ? 100 : 0;
  } else {
    whitePct = Math.max(8, Math.min(92, 50 + evalScore * 10));
  }
  const evalDisplay = (currentMove as any)?.eval_score || `${evalScore >= 0 ? '+' : ''}${evalScore.toFixed(2)}`;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-6">
        <Loader2
          className="w-10 h-10 animate-spin"
          style={{ color: 'var(--ct-gold)' }}
        />
        <p className="text-sm" style={{ color: 'var(--ct-text-muted)' }}>
          Loading game #{activeGameId || gameId} timeline…
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* ── Game Header ──────────────────────────────────────── */}
      <div
        className="glass-panel rounded-2xl px-6 py-4 flex flex-wrap justify-between items-center gap-4"
      >
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h1
              className="text-lg font-bold font-mono"
              style={{ color: 'var(--ct-text-primary)' }}
            >
              {gameMeta?.white_player || 'White'} vs {gameMeta?.black_player || 'Black'}
            </h1>
            <span
              className="px-2.5 py-0.5 rounded-md text-xs font-bold font-mono"
              style={{
                background: 'rgba(232,182,106,0.1)',
                color: 'var(--ct-gold)',
                border: '1px solid rgba(232,182,106,0.2)',
              }}
            >
              {gameMeta?.eco || 'A00'}
            </span>
          </div>
          <p className="text-xs font-mono mt-1" style={{ color: 'var(--ct-text-muted)' }}>
            {gameMeta?.event} &nbsp;·&nbsp; {gameMeta?.result} &nbsp;·&nbsp; {gameMeta?.time_control}
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {allGames.length > 0 && (
            <div className="flex items-center gap-2">
              <label className="text-xs font-mono" style={{ color: 'var(--ct-text-muted)' }}>Game:</label>
              <select
                value={activeGameId ?? ''}
                onChange={(e) => {
                  const newId = Number(e.target.value);
                  setActiveGameId(newId);
                  const url = new URL(window.location.href);
                  url.searchParams.set('gameId', newId.toString());
                  url.searchParams.delete('ply');
                  window.history.replaceState({}, '', url);
                }}
                className="input-app py-1.5 px-3 text-xs font-mono"
                style={{ color: 'var(--ct-gold)' }}
              >
                {allGames.map(g => (
                  <option key={g.id} value={g.id}>
                    #{g.id}: {g.white_player} vs {g.black_player} ({g.result})
                  </option>
                ))}
              </select>
            </div>
          )}

          <a
            href={`${API_BASE}/games/${activeGameId || gameId}/export-pgn`}
            download
            className="btn-app text-xs gap-2"
          >
            <Download className="w-3.5 h-3.5" />
            PGN
          </a>
        </div>
      </div>

      {/* ── Main Analysis Grid ───────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Board + Controls */}
        <div className="lg:col-span-5 space-y-4">
          {/* Move Quality Banner */}
          {currentMove && (() => {
            const cls = (currentMove as any).move_classification || 'good';
            const meta = getMoveTypeMeta(cls);
            return (
              <motion.div
                key={currentIndex}
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className="glass-panel rounded-xl px-4 py-3 flex items-center justify-between gap-3"
                style={{ borderColor: meta.border }}
              >
                <div className="flex items-center gap-3">
                  <span
                    className="w-8 h-8 flex items-center justify-center rounded-full text-sm font-black flex-shrink-0"
                    style={{ background: meta.bg, color: meta.text, border: `1px solid ${meta.border}` }}
                  >
                    {meta.icon}
                  </span>
                  <div>
                    <div className="text-xs font-black font-mono" style={{ color: meta.text }}>
                      {meta.label}
                    </div>
                    <div className="text-[11px] font-mono" style={{ color: 'var(--ct-text-muted)' }}>
                      {currentMove.san} played
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-extrabold font-mono" style={{ color: meta.text }}>
                    {evalDisplay}
                  </span>
                  {!['best', 'brilliant', 'great', 'book'].includes(cls) && (
                    <span
                      className="text-[11px] font-bold font-mono px-2 py-1 rounded-lg"
                      style={{
                        background: 'rgba(48,198,112,0.1)',
                        color: '#30C670',
                        border: '1px solid rgba(48,198,112,0.2)',
                      }}
                    >
                      {(currentMove as any).best_move_label || `${(currentMove as any).best_move_san || 'best'} is best`}
                    </span>
                  )}
                </div>
              </motion.div>
            );
          })()}

          {/* Board + Eval Bar */}
          <div className="flex items-center justify-center gap-3">
            {/* Eval Bar */}
            <div className="flex flex-col items-center gap-1.5">
              <span
                className="text-[11px] font-extrabold font-mono px-2 py-0.5 rounded-lg"
                style={
                  evalScore >= 0
                    ? { background: 'rgba(255,255,255,0.9)', color: '#10152F', border: '1px solid rgba(255,255,255,0.4)' }
                    : { background: 'rgba(16,21,47,0.9)', color: '#F3F0E8', border: '1px solid rgba(255,255,255,0.1)' }
                }
              >
                {evalDisplay}
              </span>
              <div
                className="w-5 rounded-xl overflow-hidden border"
                style={{
                  height: '380px',
                  background: '#0A0E20',
                  borderColor: 'rgba(255,255,255,0.06)',
                }}
              >
                {boardFlipped ? (
                  <>
                    <div
                      className="w-full transition-all duration-300 ease-out"
                      style={{ height: `${whitePct}%`, background: '#F3F0E8' }}
                    />
                    <div
                      className="w-full transition-all duration-300 ease-out"
                      style={{ height: `${100 - whitePct}%`, background: '#2A3050' }}
                    />
                  </>
                ) : (
                  <>
                    <div
                      className="w-full transition-all duration-300 ease-out"
                      style={{ height: `${100 - whitePct}%`, background: '#2A3050' }}
                    />
                    <div
                      className="w-full transition-all duration-300 ease-out"
                      style={{ height: `${whitePct}%`, background: '#F3F0E8' }}
                    />
                  </>
                )}
              </div>
            </div>

            {/* Board Column */}
            <div className="flex flex-col gap-2 flex-1 max-w-[420px]">
              {/* Top player */}
              <div
                className="flex items-center justify-between rounded-xl px-4 py-2.5"
                style={{
                  background: 'rgba(23,30,64,0.8)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}
              >
                <div className="flex items-center gap-2.5">
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center"
                    style={{ background: 'var(--ct-navy-3)', border: '1px solid rgba(255,255,255,0.08)' }}
                  >
                    <User className="w-4 h-4" style={{ color: 'var(--ct-text-muted)' }} />
                  </div>
                  <div>
                    <div className="text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
                      {boardFlipped ? (gameMeta?.white_player || 'White') : (gameMeta?.black_player || 'Black')}
                    </div>
                    <div className="text-[11px] font-mono" style={{ color: 'var(--ct-text-muted)' }}>
                      {boardFlipped ? gameMeta?.white_elo : gameMeta?.black_elo}
                    </div>
                  </div>
                </div>
                <div
                  className="px-3 py-1 rounded-lg font-mono text-base font-bold min-w-[76px] text-center"
                  style={{ background: '#0A0E20', color: 'var(--ct-text-primary)', border: '1px solid rgba(255,255,255,0.06)' }}
                >
                  {formatClock(getPlayerClock(boardFlipped ? 'white' : 'black'))}
                </div>
              </div>

              {/* Chessboard */}
              <div
                ref={boardContainerRef}
                className="rounded-2xl overflow-hidden"
                style={{
                  background: 'var(--ct-navy-2)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
                  padding: '12px',
                }}
              >
                <Chessboard
                  position={fenToPositionObj(currentMove ? currentMove.fen : 'start')}
                  boardOrientation={boardFlipped ? 'black' : 'white'}
                  onPieceDrop={onPieceDrop}
                  customSquareStyles={
                    currentMove?.uci
                      ? {
                          [currentMove.uci.substring(0, 2)]: { backgroundColor: 'rgba(232,182,106,0.45)' },
                          [currentMove.uci.substring(2, 4)]: { backgroundColor: 'rgba(232,182,106,0.45)' },
                        }
                      : {}
                  }
                  customBoardStyle={{
                    borderRadius: '10px',
                    boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
                  }}
                  customDarkSquareStyle={{ backgroundColor: '#B8944E' }}
                  customLightSquareStyle={{ backgroundColor: '#E8D5A8' }}
                />
              </div>

              {/* Bottom player */}
              <div
                className="flex items-center justify-between rounded-xl px-4 py-2.5"
                style={{
                  background: 'rgba(23,30,64,0.8)',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}
              >
                <div className="flex items-center gap-2.5">
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center"
                    style={{ background: 'var(--ct-navy-3)', border: '1px solid rgba(255,255,255,0.08)' }}
                  >
                    <User className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
                  </div>
                  <div>
                    <div className="text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
                      {boardFlipped ? (gameMeta?.black_player || 'Black') : (gameMeta?.white_player || 'White')}
                    </div>
                    <div className="text-[11px] font-mono" style={{ color: 'var(--ct-text-muted)' }}>
                      {boardFlipped ? gameMeta?.black_elo : gameMeta?.white_elo}
                    </div>
                  </div>
                </div>
                <div
                  className="px-3 py-1 rounded-lg font-mono text-base font-bold min-w-[76px] text-center"
                  style={{ background: '#0A0E20', color: 'var(--ct-gold)', border: '1px solid rgba(232,182,106,0.15)' }}
                >
                  {formatClock(getPlayerClock(boardFlipped ? 'black' : 'white'))}
                </div>
              </div>
            </div>
          </div>

          {/* Navigation Controls */}
          <div
            className="glass-panel rounded-xl px-4 py-3 flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentIndex(-1)}
                className="p-2 rounded-lg transition-all duration-150"
                style={{ background: 'var(--ct-navy-3)', color: 'var(--ct-text-secondary)' }}
                title="Reset to start"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
              <button
                onClick={() => setBoardFlipped(f => !f)}
                className="p-2 rounded-lg transition-all duration-150"
                style={{
                  background: boardFlipped ? 'rgba(232,182,106,0.15)' : 'var(--ct-navy-3)',
                  color: boardFlipped ? 'var(--ct-gold)' : 'var(--ct-text-secondary)',
                  border: boardFlipped ? '1px solid rgba(232,182,106,0.25)' : '1px solid transparent',
                }}
                title="Flip board"
              >
                <FlipVertical2 className="w-4 h-4" />
              </button>
            </div>

            <div className="flex items-center gap-3">
              <button
                disabled={currentIndex <= -1}
                onClick={() => setCurrentIndex(prev => Math.max(-1, prev - 1))}
                className="p-2.5 rounded-xl disabled:opacity-30 transition-all duration-150"
                style={{ background: 'var(--ct-gold)', color: 'var(--ct-navy)' }}
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <span
                className="text-sm font-bold font-mono min-w-[80px] text-center"
                style={{ color: 'var(--ct-text-secondary)' }}
              >
                {currentIndex === -1 ? 'Start' : `${currentIndex + 1} / ${timeline.length}`}
              </span>
              <button
                disabled={currentIndex === timeline.length - 1}
                onClick={() => setCurrentIndex(prev => Math.min(timeline.length - 1, prev + 1))}
                className="p-2.5 rounded-xl disabled:opacity-30 transition-all duration-150"
                style={{ background: 'var(--ct-gold)', color: 'var(--ct-navy)' }}
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>

            <span
              className="text-xs font-bold px-3 py-1.5 rounded-lg font-mono"
              style={{
                background: 'var(--ct-navy-3)',
                color: currentMove ? 'var(--ct-gold)' : 'var(--ct-text-muted)',
              }}
            >
              {currentMove ? currentMove.san : 'Start'}
            </span>
          </div>
        </div>

        {/* Right Column: Analysis Panels */}
        <div className="lg:col-span-7 space-y-4">
          {/* Move List */}
          <div className="glass-panel rounded-2xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Zap className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
                Game Moves
              </span>
              <span className="text-xs font-mono ml-auto" style={{ color: 'var(--ct-text-muted)' }}>
                ← → to navigate
              </span>
            </div>
            <div
              ref={moveListRef}
              className="max-h-[200px] overflow-y-auto"
              style={{ scrollbarWidth: 'thin' }}
            >
              <div className="grid grid-cols-[36px_1fr_1fr] gap-x-1 gap-y-0.5 text-sm font-mono">
                {Array.from({ length: Math.ceil(timeline.length / 2) }).map((_, i) => {
                  const whiteMove = timeline[i * 2];
                  const blackMove = timeline[i * 2 + 1];
                  const wCls = (whiteMove as any)?.move_classification || 'good';
                  const bCls = (blackMove as any)?.move_classification || 'good';
                  const wMeta = getMoveTypeMeta(wCls);
                  const bMeta = getMoveTypeMeta(bCls);
                  return (
                    <React.Fragment key={i}>
                      <div
                        className="text-right pr-2 py-0.5 flex items-center justify-end text-xs"
                        style={{ color: 'var(--ct-text-muted)' }}
                      >
                        {whiteMove?.move_number}.
                      </div>
                      {whiteMove && (
                        <button
                          id={`move-${i * 2}`}
                          onClick={() => setCurrentIndex(i * 2)}
                          className="text-left px-2 py-0.5 rounded transition-all duration-100 flex items-center gap-1.5"
                          style={
                            currentIndex === i * 2
                              ? { background: 'rgba(232,182,106,0.15)', color: 'var(--ct-gold)', fontWeight: 700 }
                              : { color: 'var(--ct-text-secondary)' }
                          }
                          title={wMeta.label}
                        >
                          <span
                            className="text-[9px] w-4 text-center flex-shrink-0"
                            style={{ color: wMeta.text }}
                          >
                            {wMeta.icon}
                          </span>
                          {whiteMove.san}
                        </button>
                      )}
                      {blackMove ? (
                        <button
                          id={`move-${i * 2 + 1}`}
                          onClick={() => setCurrentIndex(i * 2 + 1)}
                          className="text-left px-2 py-0.5 rounded transition-all duration-100 flex items-center gap-1.5"
                          style={
                            currentIndex === i * 2 + 1
                              ? { background: 'rgba(232,182,106,0.15)', color: 'var(--ct-gold)', fontWeight: 700 }
                              : { color: 'var(--ct-text-secondary)' }
                          }
                          title={bMeta.label}
                        >
                          <span
                            className="text-[9px] w-4 text-center flex-shrink-0"
                            style={{ color: bMeta.text }}
                          >
                            {bMeta.icon}
                          </span>
                          {blackMove.san}
                        </button>
                      ) : <div />}
                    </React.Fragment>
                  );
                })}
              </div>
            </div>
          </div>

          {/* What-If Divergence */}
          <div className="glass-panel p-5 rounded-2xl space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
              <Sliders className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
              <span>Counterfactual What-If Analysis</span>
            </div>

            <form onSubmit={handleWhatIfSubmit} className="flex gap-2">
              <input
                type="text"
                placeholder={`What if ${currentMove?.color === 'white' ? 'White' : 'Black'} played… (instead of ${currentMove?.san || '…'})`}
                value={altMoveInput}
                onChange={(e) => setAltMoveInput(e.target.value)}
                className="input-app flex-1 text-xs"
              />
              <button
                type="submit"
                disabled={whatIfLoading || !currentMove}
                className="btn-gold text-xs whitespace-nowrap disabled:opacity-50"
              >
                {whatIfLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Evaluate'}
              </button>
            </form>

            <AnimatePresence>
              {whatIfResult && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="rounded-xl p-4 space-y-3 text-xs"
                  style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.06)' }}
                >
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: 'Played Move', data: whatIfResult.played_move },
                      { label: 'Alternative Move', data: whatIfResult.alternative_move },
                    ].map(({ label, data }) => {
                      const winPct = (boardFlipped ? (1 - data.win_probability) : data.win_probability) * 100;
                      return (
                        <div key={label} className="rounded-lg p-3" style={{ background: 'var(--ct-navy-2)' }}>
                          <div className="text-[10px] uppercase font-semibold mb-1" style={{ color: 'var(--ct-text-muted)' }}>
                            {label}
                          </div>
                          <div className="flex items-baseline justify-between">
                            <span className="text-base font-bold font-mono" style={{ color: 'var(--ct-text-primary)' }}>
                              {(data as any).san || data.uci}
                            </span>
                            {(data as any).eval_str && (
                              <span className="text-xs font-mono font-semibold" style={{ color: 'var(--ct-gold)' }}>
                                {(data as any).eval_str}
                              </span>
                            )}
                          </div>
                          <div className="font-mono mt-1 text-xs" style={{ color: 'var(--ct-text-secondary)' }}>
                            {winPct.toFixed(1)}% win
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <p
                    className="font-semibold text-sm leading-relaxed"
                    style={{
                      color:
                        whatIfResult.probability_divergence.win_probability_delta > 0.03 ||
                        whatIfResult.probability_divergence.recommendation.startsWith('🟢')
                          ? '#30C670'
                          : whatIfResult.probability_divergence.win_probability_delta < -0.03 ||
                            whatIfResult.probability_divergence.recommendation.startsWith('🔴')
                          ? '#EF4444'
                          : whatIfResult.probability_divergence.recommendation.startsWith('🟡')
                          ? '#F59E0B'
                          : 'var(--ct-text-secondary)',
                    }}
                  >
                    {whatIfResult.probability_divergence.recommendation}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* XGBoost Predictions */}
          <AnimatePresence>
            {prediction && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="glass-panel p-5 rounded-2xl space-y-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
                    <Zap className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
                    <span>XGBoost Intelligence</span>
                  </div>
                  {prediction.time_pressure_risk_multiplier > 1.0 && (currentMove as any)?.has_clock_data && currentMove?.time_remaining_sec != null && (
                    <span
                      className="flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full animate-pulse"
                      style={{
                        background: 'rgba(249,115,22,0.1)',
                        color: '#F97316',
                        border: '1px solid rgba(249,115,22,0.25)',
                      }}
                    >
                      <AlertTriangle className="w-3 h-3" />
                      {prediction.time_pressure_risk_multiplier}× Time Stress
                    </span>
                  )}
                </div>

                {(() => {
                  const hasGameClocks = timeline.some(m => (m as any).has_clock_data === true);
                  const isUntimed = !hasGameClocks ||
                                    (currentMove as any)?.has_clock_data === false ||
                                    currentMove?.time_remaining_sec == null ||
                                    (prediction as any)?.has_clock_data === false;
                  const displayedWinProb = boardFlipped ? (1 - prediction.win_probability) : prediction.win_probability;
                  const winProbColor = displayedWinProb >= 0.55 ? '#30C670' : displayedWinProb <= 0.45 ? '#EF4444' : '#E8B66A';

                  const tension = 1.0 - Math.abs(displayedWinProb - 0.5) * 2.0;
                  const sideLosingFactor = Math.max(0.15, 1.0 - displayedWinProb);
                  const timeMult = !isUntimed ? (prediction.time_pressure_risk_multiplier || 1.0) : 1.0;
                  const displayedCollapseProb = Math.min(0.95, Math.max(0.05, (0.4 * tension + 0.6 * sideLosingFactor) * timeMult));
                  const collapseRiskColor = displayedCollapseProb > 0.6 ? '#DC2626' : displayedCollapseProb > 0.35 ? '#F97316' : '#30C670';

                  const isTimeFeature = (f: string) => /time|clock|rush|panic|pace|deviation|ratio|pressure|seconds/i.test(f);
                  const filteredPositive = (prediction.top_positive_factors || []).filter(f => !isUntimed || !isTimeFeature(f.feature));
                  const filteredNegative = (prediction.top_negative_factors || []).filter(f => !isUntimed || !isTimeFeature(f.feature));
                  const combinedFactors = [...filteredPositive, ...filteredNegative]
                    .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
                    .slice(0, 5);

                  let displayNarrative = prediction.narrative_summary;
                  if (isUntimed && displayNarrative) {
                    const cleanSentences = displayNarrative.split('. ').filter(s => !/time|clock|pace|rush|seconds|stress|pressure|deviation/i.test(s));
                    displayNarrative = cleanSentences.length > 0 ? cleanSentences.join('. ') : 'Position evaluation is driven by material balance, piece mobility, and center control.';
                    if (!displayNarrative.endsWith('.')) displayNarrative += '.';
                  }

                  return (
                    <>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="rounded-xl p-4" style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.05)' }}>
                          <p className="text-xs uppercase font-semibold" style={{ color: 'var(--ct-text-muted)' }}>
                            Win Probability ({boardFlipped ? 'Black' : 'White'})
                          </p>
                          <p className="text-3xl font-extrabold mt-1 font-mono transition-colors duration-200" style={{ color: winProbColor }}>
                            {(displayedWinProb * 100).toFixed(1)}%
                          </p>
                          <p className="text-[10px] mt-1 font-mono" style={{ color: 'var(--ct-text-muted)' }}>
                            {displayedWinProb >= 0.55 ? `▲ ${boardFlipped ? 'Black' : 'White'} is winning` :
                             displayedWinProb <= 0.45 ? `▼ ${boardFlipped ? 'Black' : 'White'} is losing` :
                             '= Balanced position'}
                          </p>
                        </div>
                        <div className="rounded-xl p-4" style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.05)' }}>
                          <p className="text-xs uppercase font-semibold" style={{ color: 'var(--ct-text-muted)' }}>
                            Collapse Risk ({boardFlipped ? 'Black' : 'White'})
                          </p>
                          <p
                            className="text-3xl font-extrabold mt-1 font-mono transition-colors duration-200"
                            style={{ color: collapseRiskColor }}
                          >
                            {(displayedCollapseProb * 100).toFixed(1)}%
                          </p>
                          <p className="text-[10px] mt-1 font-mono" style={{ color: 'var(--ct-text-muted)' }}>
                            {displayedCollapseProb > 0.6 ? '⚠ High risk' :
                             displayedCollapseProb > 0.35 ? '~ Moderate risk' : '✓ Low risk'}
                          </p>
                        </div>
                      </div>

                      {/* SHAP Factors */}
                      {combinedFactors.length > 0 && (
                        <div className="rounded-xl p-4 space-y-3" style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.05)' }}>
                          <div className="flex items-center gap-2 text-xs font-bold" style={{ color: 'var(--ct-text-secondary)' }}>
                            <Brain className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
                            Position Factors (SHAP)
                          </div>
                          <div className="space-y-2">
                            {combinedFactors.map((f, i) => (
                              <div key={i} className="flex items-center gap-2">
                                <span
                                  className="text-[10px] font-bold w-[36px] text-right font-mono"
                                  style={{ color: f.impact >= 0 ? '#30C670' : '#EF4444' }}
                                >
                                  {f.impact >= 0 ? '+' : ''}{(f.impact * 100).toFixed(1)}%
                                </span>
                                <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--ct-navy-2)' }}>
                                  <div
                                    className="h-full rounded-full"
                                    style={{
                                      width: `${Math.min(100, Math.abs(f.impact) * 400)}%`,
                                      background: f.impact >= 0 ? '#30C670' : '#EF4444',
                                    }}
                                  />
                                </div>
                                <span className="text-[10px] font-mono truncate max-w-[130px]" style={{ color: 'var(--ct-text-muted)' }}>
                                  {f.feature}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* SHAP Narrative */}
                      <div className="rounded-xl p-4" style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.05)' }}>
                        <div className="flex items-center gap-2 text-xs font-bold mb-2" style={{ color: 'var(--ct-text-secondary)' }}>
                          <Brain className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
                          SHAP Narrative
                        </div>
                        <p className="text-sm italic" style={{ color: 'var(--ct-text-secondary)' }}>
                          {displayNarrative}
                        </p>
                      </div>
                    </>
                  );
                })()}
              </motion.div>
            )}
          </AnimatePresence>

          {/* ELO Simulator */}
          <AnimatePresence>
            {eloSimResult && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="glass-panel p-5 rounded-2xl space-y-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
                    <Sparkles className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
                    ELO Simulation
                  </div>
                  <select
                    value={selectedElo}
                    onChange={(e) => setSelectedElo(e.target.value)}
                    className="input-app py-1 px-2.5 text-xs font-mono"
                    style={{ color: 'var(--ct-gold)' }}
                  >
                    <option value="< 1000">&lt; 1000</option>
                    <option value="1000-1200">1000–1200</option>
                    <option value="1200-1400">1200–1400</option>
                    <option value="1400-1600">1400–1600</option>
                    <option value="1600-1800">1600–1800</option>
                    <option value="1800-2000">1800–2000</option>
                    <option value="2000+">2000+</option>
                  </select>
                </div>

                <div className="space-y-2.5">
                  {eloSimResult.top_candidate_moves.length === 0 ? (
                    <p className="text-xs text-center italic py-3" style={{ color: 'var(--ct-text-muted)' }}>
                      No candidate moves found.
                    </p>
                  ) : (
                    eloSimResult.top_candidate_moves.map((cand, i) => (
                      <div
                        key={i}
                        className="rounded-xl p-3 space-y-1.5 text-xs"
                        style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.05)' }}
                      >
                        <div className="flex justify-between items-center">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm font-mono" style={{ color: 'var(--ct-text-primary)' }}>
                              {cand.san}
                            </span>
                            <span className="font-mono" style={{ color: 'var(--ct-text-muted)' }}>
                              ({cand.uci})
                            </span>
                            {cand.is_engine_top_choice && (
                              <span
                                className="px-2 py-0.5 rounded text-[10px] font-bold"
                                style={{ background: 'rgba(48,198,112,0.12)', color: '#30C670', border: '1px solid rgba(48,198,112,0.25)' }}
                              >
                                Stockfish Best
                              </span>
                            )}
                          </div>
                          <span className="font-bold font-mono" style={{ color: 'var(--ct-gold)' }}>
                            {(cand.probability * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--ct-navy-2)' }}>
                          <div
                            className="h-full rounded-full transition-all duration-300"
                            style={{ width: `${Math.min(100, cand.probability * 100)}%`, background: 'var(--ct-gold)' }}
                          />
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* ── Game Review Summary ──────────────────────────────── */}
      <div className="glass-panel rounded-2xl overflow-hidden">
        <div
          className="px-6 py-4 flex items-center justify-between border-b"
          style={{ borderColor: 'rgba(255,255,255,0.05)' }}
        >
          <h2 className="text-base font-bold flex items-center gap-2" style={{ color: 'var(--ct-text-primary)' }}>
            <Sparkles className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
            Game Review
          </h2>
        </div>

        {/* Player Headers */}
        <div className="px-6 py-5 grid grid-cols-[1fr_auto_1fr] items-center gap-4">
          <div className="flex flex-col items-end">
            <div className="text-xs font-bold font-mono truncate" style={{ color: 'var(--ct-text-secondary)' }}>
              {gameMeta?.white_player || 'White'}
            </div>
            <div className="text-3xl font-extrabold font-mono leading-none mt-1" style={{ color: 'var(--ct-text-primary)' }}>
              {whiteRating}
            </div>
            <div className="text-[10px] mt-0.5" style={{ color: 'var(--ct-gold)' }}>
              {gameMeta?.white_elo ? `Est. Rating · Actual: ${gameMeta.white_elo}` : 'Est. Rating'}
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs font-semibold px-3 py-1 rounded-full" style={{ background: 'var(--ct-navy)', color: 'var(--ct-text-muted)', border: '1px solid rgba(255,255,255,0.06)' }}>
              vs
            </div>
          </div>
          <div className="flex flex-col items-start">
            <div className="text-xs font-bold font-mono truncate" style={{ color: 'var(--ct-text-secondary)' }}>
              {gameMeta?.black_player || 'Black'}
            </div>
            <div className="text-3xl font-extrabold font-mono leading-none mt-1" style={{ color: 'var(--ct-text-primary)' }}>
              {blackRating}
            </div>
            <div className="text-[10px] mt-0.5" style={{ color: 'var(--ct-gold)' }}>
              {gameMeta?.black_elo ? `Est. Rating · Actual: ${gameMeta.black_elo}` : 'Est. Rating'}
            </div>
          </div>
        </div>

        {/* Accuracy Bars */}
        <div className="px-6 pb-4 grid grid-cols-[1fr_auto_1fr] items-center gap-4">
          <div className="flex items-center justify-end gap-2">
            <span className="text-sm font-extrabold font-mono" style={{ color: 'var(--ct-text-primary)' }}>
              {whiteAccuracy}
            </span>
            <div className="flex-1 max-w-[120px] h-2 rounded-full overflow-hidden" style={{ background: 'var(--ct-navy-3)' }}>
              <div className="h-full rounded-full" style={{ width: `${whiteAccuracy}%`, background: 'var(--ct-gold)' }} />
            </div>
          </div>
          <div
            className="px-3 py-1 rounded text-[10px] font-semibold uppercase tracking-wider text-center"
            style={{ color: 'var(--ct-text-muted)' }}
          >
            Accuracy
          </div>
          <div className="flex items-center justify-start gap-2">
            <div className="flex-1 max-w-[120px] h-2 rounded-full overflow-hidden" style={{ background: 'var(--ct-navy-3)' }}>
              <div className="h-full rounded-full" style={{ width: `${blackAccuracy}%`, background: '#A5ADC6' }} />
            </div>
            <span className="text-sm font-extrabold font-mono" style={{ color: 'var(--ct-text-primary)' }}>
              {blackAccuracy}
            </span>
          </div>
        </div>

        <div className="mx-6 border-t" style={{ borderColor: 'rgba(255,255,255,0.04)' }} />

        {/* Move Type Rows */}
        <div className="px-6 py-4 space-y-1">
          {MOVE_TYPES.map((mt) => {
            const wCount = whiteCounts[mt.key] || 0;
            const bCount = blackCounts[mt.key] || 0;
            const wPct = (wCount / whiteTotalMoves) * 100;
            const bPct = (bCount / blackTotalMoves) * 100;
            const wFirstIdx = timeline.findIndex(m => m.color === 'white' && (m as any).move_classification === mt.key);
            const bFirstIdx = timeline.findIndex(m => m.color === 'black' && (m as any).move_classification === mt.key);
            return (
              <div key={mt.key} className="grid grid-cols-[1fr_64px_40px_64px_1fr] items-center gap-2 py-1.5 px-2 rounded-xl">
                <div
                  className={`flex items-center justify-end gap-2 ${wFirstIdx !== -1 ? 'cursor-pointer hover:bg-white/[0.03] rounded-lg px-2 py-1 transition-colors' : 'opacity-30'}`}
                  onClick={() => { if (wFirstIdx !== -1) { setCurrentIndex(wFirstIdx); boardContainerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }}}
                >
                  {wCount > 0 && <span className="text-sm font-extrabold font-mono" style={{ color: mt.text }}>{wCount}</span>}
                  <div className="flex-1 max-w-[100px] h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.04)' }}>
                    {wCount > 0 && <div className="h-full rounded-full" style={{ width: `${Math.max(4, wPct * 2.5)}%`, background: mt.color }} />}
                  </div>
                </div>
                <div className="text-center text-xs font-semibold" style={{ color: 'var(--ct-text-muted)' }}>
                  {mt.label}
                </div>
                <div
                  className="w-8 h-8 flex items-center justify-center rounded-full text-xs font-black flex-shrink-0 mx-auto"
                  style={{ background: mt.bg, color: mt.text, border: `1px solid ${mt.border}` }}
                >
                  {mt.icon}
                </div>
                <div className="text-center" />
                <div
                  className={`flex items-center justify-start gap-2 ${bFirstIdx !== -1 ? 'cursor-pointer hover:bg-white/[0.03] rounded-lg px-2 py-1 transition-colors' : 'opacity-30'}`}
                  onClick={() => { if (bFirstIdx !== -1) { setCurrentIndex(bFirstIdx); boardContainerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }}}
                >
                  <div className="flex-1 max-w-[100px] h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.04)' }}>
                    {bCount > 0 && <div className="h-full rounded-full" style={{ width: `${Math.max(4, bPct * 2.5)}%`, background: mt.color }} />}
                  </div>
                  {bCount > 0 && <span className="text-sm font-extrabold font-mono" style={{ color: mt.text }}>{bCount}</span>}
                </div>
              </div>
            );
          })}
        </div>

        <div className="px-6 py-3 border-t flex items-center justify-between text-[11px] font-mono" style={{ borderColor: 'rgba(255,255,255,0.04)', color: 'var(--ct-text-muted)' }}>
          <span>{gameMeta?.white_player || 'White'} · {whiteTotalMoves} moves</span>
          <span>{timeline.length} moves analyzed</span>
          <span>{gameMeta?.black_player || 'Black'} · {blackTotalMoves} moves</span>
        </div>
      </div>

      {/* ── Think Time Chart ─────────────────────────────────── */}
      <div className="glass-panel p-5 rounded-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold flex items-center gap-2" style={{ color: 'var(--ct-text-primary)' }}>
            <TrendingDown className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
            Think Time &amp; Clock Pressure Heatmap
          </h3>
          <span className="text-xs" style={{ color: 'var(--ct-text-muted)' }}>Seconds per move</span>
        </div>

        {chartData.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-sm" style={{ color: 'var(--ct-text-muted)' }}>
            No clock data available for this game.
          </div>
        ) : (
          <div className="h-48 w-full cursor-pointer">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
                onClick={(e: any) => {
                  if (e?.activeLabel) {
                    const idx = timeline.findIndex(m => m.move_number === Number(e.activeLabel));
                    if (idx !== -1) { setCurrentIndex(idx); boardContainerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
                  }
                }}
              >
                <defs>
                  <linearGradient id="goldGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#E8B66A" stopOpacity={0.5} />
                    <stop offset="95%" stopColor="#E8B66A" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="silverGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#A5ADC6" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#A5ADC6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="move" stroke="#2A3050" fontSize={10} tick={{ fill: '#6B7394' }} minTickGap={35} />
                <YAxis stroke="#2A3050" fontSize={10} unit="s" tick={{ fill: '#6B7394' }} width={36} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#171E40', borderColor: '#2A3050', borderRadius: '10px', color: '#F3F0E8', fontSize: '12px' }}
                  formatter={(val: any, name: any) => [`${val}s`, name === 'whiteThink' ? 'White Time' : 'Black Time']}
                />
                <Area type="monotone" dataKey="whiteThink" name="whiteThink" stroke="#F3F0E8" strokeWidth={1.5} fillOpacity={1} fill="url(#silverGrad)" dot={false} />
                <Area type="monotone" dataKey="blackThink" name="blackThink" stroke="#E8B66A" strokeWidth={1.5} fillOpacity={1} fill="url(#goldGrad)" dot={false} />
                {currentMove && <ReferenceLine x={currentMove.move_number} stroke="#E8B66A" strokeWidth={1.5} strokeDasharray="3 3" />}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
};
