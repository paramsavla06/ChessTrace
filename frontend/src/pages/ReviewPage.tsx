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
  ReferenceLine,
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
  FlipVertical2,
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
  const [boardFlipped, setBoardFlipped] = useState<boolean>(false);
  // -1 = starting position (before any moves), 0..n-1 = timeline moves
  const [currentIndex, setCurrentIndex] = useState<number>(-1);
  const [loading, setLoading] = useState<boolean>(true);
  const [whatIfLoading, setWhatIfLoading] = useState<boolean>(false);
  const [gameMeta, setGameMeta] = useState<any>(null);

  // Advanced Analysis State
  const [prediction, setPrediction] = useState<PredictResponse | null>(null);
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResponse | null>(null);
  const [eloSimResult, setEloSimResult] = useState<EloSimResponse | null>(null);
  const [altMoveInput, setAltMoveInput] = useState<string>('');
  const [selectedElo, setSelectedElo] = useState<string>('1600-1800');
  const boardContainerRef = React.useRef<HTMLDivElement>(null);

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
        setCurrentIndex(-1);
      } catch (err) {
        console.error('Failed loading game review data', err);
      } finally {
        setLoading(false);
      }
    };
    loadGameData();
  }, [activeGameId, gameId]);

  // Keyboard Arrow Navigation (ignore when typing in input/select fields)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (document.activeElement as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      if (e.key === 'ArrowLeft') {
        setCurrentIndex((prev) => Math.max(-1, prev - 1));
      } else if (e.key === 'ArrowRight') {
        setCurrentIndex((prev) => Math.min(timeline.length - 1, prev + 1));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [timeline.length]);

  const currentMove = timeline[currentIndex] ?? null;  // null at index -1 (start)

  // Run ML Prediction on move change (skip at starting position)
  useEffect(() => {
    if (!currentMove) { setPrediction(null); return; }
    
    setPrediction(null); // Clear old prediction while waiting

    const timer = setTimeout(async () => {
      try {
        const res = await api.post<PredictResponse>('/analysis/predict', {
          fen: currentMove.fen,
          think_time_sec: currentMove.think_time_sec,
          time_remaining_sec: currentMove.time_remaining_sec,
          eval_cp: (currentMove as any).eval_cp,
        });
        setPrediction(res.data);
      } catch (err) {
        console.error('Prediction failed', err);
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [currentIndex, currentMove]);

  // Run ELO Simulator on target ELO change (skip at starting position)
  useEffect(() => {
    if (!currentMove) { setEloSimResult(null); return; }
    
    setEloSimResult(null); // Clear old simulation while waiting

    const timer = setTimeout(async () => {
      try {
        const res = await api.post<EloSimResponse>('/analysis/elo-sim', {
          fen: currentMove.fen,
          target_elo_bucket: selectedElo,
          time_remaining_sec: currentMove.time_remaining_sec,
          best_move_uci: (currentMove as any).best_move_uci,
        });
        setEloSimResult(res.data);
      } catch (err) {
        console.error('ELO Sim failed', err);
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [currentIndex, selectedElo, currentMove]);

  const runWhatIf = async (
    baseFen: string,
    actualMove: TimelineMove,
    altMoveStr: string
  ) => {
    setWhatIfLoading(true);
    try {
      const res = await api.post<WhatIfResponse>('/analysis/what-if', {
        fen: baseFen,
        played_move_uci: actualMove.uci,
        alternative_move_uci: altMoveStr.trim(),
        think_time_sec: actualMove.think_time_sec,
        time_remaining_sec: actualMove.time_remaining_sec,
        eval_cp: (actualMove as any).eval_cp,
        perspective: boardFlipped ? 'black' : 'white',
      });
      setWhatIfResult(res.data);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'An unknown error occurred on the server.';
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
      const moveObj = chess.move({
        from: sourceSquare,
        to: targetSquare,
        promotion: 'q',
      });
      
      if (!moveObj) return false;

      const nextIndex = currentIndex + 1;
      const actualNextMove = nextIndex < timeline.length ? timeline[nextIndex] : null;

      if (actualNextMove) {
        if (moveObj.lan !== actualNextMove.uci && moveObj.san !== actualNextMove.san) {
          // They played an alternative move. Step forward and run what-if.
          setCurrentIndex(nextIndex);
          setAltMoveInput(moveObj.san);
          runWhatIf(fen, actualNextMove, moveObj.san);
        } else {
          // They played the exact move from the game.
          setCurrentIndex(nextIndex);
          setAltMoveInput('');
          setWhatIfResult(null);
        }
      }
      return true;
    } catch (e) {
      // Illegal move or wrong turn
      return false;
    }
  };

  if (loading) {
    return (
      <div className="py-24 text-center text-slate-400">
        Loading game #{activeGameId || gameId} timeline and neural feature metrics...
      </div>
    );
  }

  const chartData: any[] = [];
  const movesByNumber = new Map<number, any>();

  timeline.forEach((m) => {
    if (!movesByNumber.has(m.move_number)) {
      movesByNumber.set(m.move_number, { move: m.move_number });
    }
    const d = movesByNumber.get(m.move_number);
    if (m.color === 'white') {
      d.whiteThink = parseFloat((m.think_time_sec ?? 0).toFixed(1));
    } else {
      d.blackThink = parseFloat((m.think_time_sec ?? 0).toFixed(1));
    }
  });
  movesByNumber.forEach((v) => chartData.push(v));
  chartData.sort((a, b) => a.move - b.move);

  // Chess.com move classification metadata (order matches Chess.com Game Review)
  const MOVE_TYPES = [
    { key: 'brilliant', label: 'Brilliant', icon: '!!', color: '#00b5c8', bgColor: 'bg-cyan-500/20', borderColor: 'border-cyan-500/30', textColor: 'text-cyan-400' },
    { key: 'great',     label: 'Great',     icon: '!',  color: '#32a8a8', bgColor: 'bg-teal-500/20', borderColor: 'border-teal-500/30', textColor: 'text-teal-400' },
    { key: 'book',      label: 'Book',      icon: '📖', color: '#8b5cf6', bgColor: 'bg-violet-500/20', borderColor: 'border-violet-500/30', textColor: 'text-violet-400' },
    { key: 'best',      label: 'Best',      icon: '★',  color: '#30c670', bgColor: 'bg-emerald-500/20', borderColor: 'border-emerald-500/30', textColor: 'text-emerald-400' },
    { key: 'excellent', label: 'Excellent', icon: '✓+', color: '#7fc97f', bgColor: 'bg-green-500/20', borderColor: 'border-green-500/30', textColor: 'text-green-400' },
    { key: 'good',      label: 'Good',      icon: '✓',  color: '#4ade80', bgColor: 'bg-lime-500/20', borderColor: 'border-lime-500/30', textColor: 'text-lime-400' },
    { key: 'inaccuracy',label: 'Inaccuracy',icon: '?!', color: '#f59e0b', bgColor: 'bg-amber-500/20', borderColor: 'border-amber-500/30', textColor: 'text-amber-400' },
    { key: 'mistake',   label: 'Mistake',   icon: '?',  color: '#f97316', bgColor: 'bg-orange-500/20', borderColor: 'border-orange-500/30', textColor: 'text-orange-400' },
    { key: 'miss',      label: 'Miss',      icon: '✗',  color: '#ef4444', bgColor: 'bg-rose-500/20', borderColor: 'border-rose-500/30', textColor: 'text-rose-400' },
    { key: 'blunder',   label: 'Blunder',   icon: '??', color: '#dc2626', bgColor: 'bg-red-600/20', borderColor: 'border-red-600/30', textColor: 'text-red-400' },
  ];

  // Count move types per player for Game Review summary
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

  // Compute accuracy % — Book moves excluded from denominator (not evaluated by engine)
  // Brilliant/Great/Best/Excellent/Good = accurate; Inaccuracy/Mistake/Miss/Blunder = inaccurate
  const computeAccuracy = (counts: Record<string, number>): number => {
    const bookCount = counts['book'] || 0;
    const total = (Object.values(counts).reduce((a, b) => a + b, 0) - bookCount) || 1;
    const goodMoves = (counts['brilliant'] || 0) + (counts['great'] || 0) + (counts['best'] || 0) + (counts['excellent'] || 0) + (counts['good'] || 0);
    return parseFloat(((goodMoves / total) * 100).toFixed(1));
  };

  // Estimate ChessTrace rating from move quality distribution (book moves neutral weight)
  const estimateRating = (counts: Record<string, number>): number => {
    const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
    const weights = { brilliant: 2500, great: 2200, book: 1800, best: 2000, excellent: 1800, good: 1600, inaccuracy: 1300, mistake: 1100, miss: 900, blunder: 700 };
    const weightedSum = Object.entries(counts).reduce((sum, [k, v]) => sum + (weights[k as keyof typeof weights] || 1200) * v, 0);
    return Math.round(weightedSum / total);
  };

  const whiteCounts = getMoveTypeCounts('white');
  const blackCounts = getMoveTypeCounts('black');
  const whiteRating = estimateRating(whiteCounts);
  const blackRating = estimateRating(blackCounts);
  const whiteAccuracy = computeAccuracy(whiteCounts);
  const blackAccuracy = computeAccuracy(blackCounts);
  const whiteTotalMoves = timeline.filter(m => m.color === 'white').length || 1;
  const blackTotalMoves = timeline.filter(m => m.color === 'black').length || 1;

  // Current move classification metadata helper
  const getMoveTypeMeta = (cls: string) => MOVE_TYPES.find(t => t.key === cls) || MOVE_TYPES[4];

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
          {/* Move Quality Banner (Chess.com Style) */}
          {currentMove && (() => {
            const cls = (currentMove as any).move_classification || 'good';
            const meta = getMoveTypeMeta(cls);
            return (
              <div className={`glass-panel p-3.5 rounded-2xl flex items-center justify-between gap-3 border ${meta.borderColor} shadow-lg`}>
                <div className="flex items-center gap-2.5">
                  <span className={`w-8 h-8 flex items-center justify-center rounded-full text-sm font-black ${meta.bgColor} ${meta.textColor} border ${meta.borderColor}`}>
                    {meta.icon}
                  </span>
                  <div>
                    <div className={`text-xs font-black font-mono ${meta.textColor}`}>{meta.label}</div>
                    <div className="text-[11px] text-slate-400 font-mono">{currentMove.san} played</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-extrabold font-mono ${meta.textColor}`}>{(currentMove as any).eval_score || '+0.25'}</span>
                  {!['best', 'brilliant', 'great', 'book'].includes(cls) && (
                    <div className="text-[11px] font-bold font-mono text-emerald-300 bg-emerald-500/10 px-2 py-1 rounded-lg border border-emerald-500/20">
                      {(currentMove as any).best_move_label || `${(currentMove as any).best_move_san || 'best'} is best`}
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          <div className="flex items-center justify-center gap-2">
            {/* Vertical Evaluation Bar + visible score */}
            {(() => {
              const rawEval = prediction ? (prediction.win_probability * 2 - 1) * 3.5 : 0.25;
              const evalCp = (currentMove as any)?.eval_cp;
              const evalScore = evalCp !== undefined && evalCp !== null
                ? (evalCp / 100.0)
                : rawEval;
              
              let whitePct;
              if (evalCp !== undefined && evalCp !== null && Math.abs(evalCp) > 100000) {
                whitePct = evalCp > 0 ? 100 : 0;
              } else {
                whitePct = Math.max(8, Math.min(92, 50 + (evalScore * 10)));
              }

              const evalDisplay = (currentMove as any)?.eval_score || `${evalScore >= 0 ? '+' : ''}${evalScore.toFixed(2)}`;

              return (
                <div className="flex flex-col items-center gap-1">
                  {/* Score above bar */}
                  <span className={`text-[11px] font-extrabold font-mono px-2 py-0.5 rounded-lg shadow-md ${
                    evalScore >= 0
                      ? 'bg-slate-800 text-white border border-slate-600'
                      : 'bg-slate-100 text-slate-900 border border-slate-300'
                  }`}>
                    {evalDisplay}
                  </span>
                  {/* Bar — orientation flips with board */}
                  <div className="w-5 h-[400px] bg-slate-950 rounded-xl overflow-hidden border border-slate-800 flex flex-col relative shadow-2xl">
                    {boardFlipped ? (
                      <>
                        {/* Flipped: White advantage at top */}
                        <div className="bg-slate-100 w-full transition-all duration-300 ease-out" style={{ height: `${whitePct}%` }} />
                        <div className="bg-slate-800 w-full transition-all duration-300 ease-out" style={{ height: `${100 - whitePct}%` }} />
                      </>
                    ) : (
                      <>
                        {/* Normal: Black advantage at top */}
                        <div className="bg-slate-800 w-full transition-all duration-300 ease-out" style={{ height: `${100 - whitePct}%` }} />
                        <div className="bg-slate-100 w-full transition-all duration-300 ease-out" style={{ height: `${whitePct}%` }} />
                      </>
                    )}
                  </div>
                </div>
              );
            })()}

            {/* Interactive Chessboard */}
            <div ref={boardContainerRef} className="bg-slate-900/40 border border-slate-800 shadow-xl p-4 rounded-2xl w-full max-w-[440px] aspect-square flex items-center justify-center glow-indigo">
              <Chessboard
                position={fenToPositionObj(currentMove ? currentMove.fen : 'start')}
                boardOrientation={boardFlipped ? 'black' : 'white'}
                onPieceDrop={onPieceDrop}
                customSquareStyles={currentMove?.uci ? {
                  [currentMove.uci.substring(0, 2)]: { backgroundColor: 'rgba(255, 255, 0, 0.4)' },
                  [currentMove.uci.substring(2, 4)]: { backgroundColor: 'rgba(255, 255, 0, 0.4)' },
                } : {}}
                customBoardStyle={{
                  borderRadius: '12px',
                  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
                }}
              />
            </div>
          </div>

          {/* Stepper Controls */}
          <div className="glass-panel p-4 rounded-2xl flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentIndex(-1)}
                className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                title="Reset to start"
              >
                <RotateCcw className="w-5 h-5" />
              </button>
              <button
                onClick={() => setBoardFlipped(f => !f)}
                className={`p-2 rounded-lg transition-colors ${
                  boardFlipped
                    ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
                    : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                }`}
                title="Flip board"
              >
                <FlipVertical2 className="w-5 h-5" />
              </button>
            </div>

            <div className="flex items-center gap-3">
              <button
                disabled={currentIndex <= -1}
                onClick={() => setCurrentIndex((prev) => Math.max(-1, prev - 1))}
                className="p-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 text-white transition-all"
              >
                <ChevronLeft className="w-6 h-6" />
              </button>

              <span className="text-sm font-semibold text-slate-300 font-mono min-w-[80px] text-center">
                {currentIndex === -1 ? 'Start' : `${currentIndex + 1} / ${timeline.length}`}
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
          {/* Clickable Move List */}
          <div className="glass-panel p-4 rounded-2xl max-h-[200px] overflow-y-auto">
            <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm mb-3">
              <Zap className="w-4 h-4" />
              <span>Game Moves</span>
            </div>
            <div className="grid grid-cols-[40px_1fr_1fr] gap-x-2 gap-y-1 text-sm font-mono">
              {Array.from({ length: Math.ceil(timeline.length / 2) }).map((_, i) => {
                const whiteMove = timeline[i * 2];
                const blackMove = timeline[i * 2 + 1];
                return (
                  <React.Fragment key={i}>
                    <div className="text-slate-500 text-right pr-2 py-0.5">{whiteMove?.move_number}.</div>
                    {whiteMove && (
                      <button 
                        onClick={() => setCurrentIndex(i * 2)}
                        className={`text-left px-2 py-0.5 rounded transition-colors ${
                          currentIndex === i * 2 ? 'bg-indigo-600 text-white font-bold shadow-md' : 'hover:bg-slate-800 text-slate-300'
                        }`}
                      >
                        {whiteMove.san}
                      </button>
                    )}
                    {blackMove ? (
                      <button 
                        onClick={() => setCurrentIndex(i * 2 + 1)}
                        className={`text-left px-2 py-0.5 rounded transition-colors ${
                          currentIndex === i * 2 + 1 ? 'bg-indigo-600 text-white font-bold shadow-md' : 'hover:bg-slate-800 text-slate-300'
                        }`}
                      >
                        {blackMove.san}
                      </button>
                    ) : (
                      <div />
                    )}
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* Counterfactual What-If Brancher */}
          <div className="glass-panel p-6 rounded-2xl space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <Sliders className="w-4 h-4 text-pink-400" />
              <span>Counterfactual What-If Divergence Analysis</span>
            </div>

            <form onSubmit={handleWhatIfSubmit} className="flex gap-3">
              <input
                type="text"
                placeholder={`What if ${currentMove?.color === 'white' ? 'White' : 'Black'} played... (instead of ${currentMove?.san})`}
                value={altMoveInput}
                onChange={(e) => setAltMoveInput(e.target.value)}
                className="flex-1 bg-slate-900 border border-slate-800 rounded-xl px-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
              />
              <button
                type="submit"
                disabled={whatIfLoading}
                className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                  whatIfLoading 
                    ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                    : 'bg-indigo-600 hover:bg-indigo-500 text-white'
                }`}
              >
                {whatIfLoading ? 'Evaluating...' : 'Evaluate Divergence'}
              </button>
            </form>

            {whatIfResult && (
              <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-3 text-xs">
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-slate-800/50 p-3 rounded-lg">
                    <div className="text-[10px] text-slate-500 uppercase font-semibold">Played Move</div>
                    <div className="text-sm font-bold text-white mt-1">{(whatIfResult.played_move as any).san || whatIfResult.played_move.uci}</div>
                    <div className="text-slate-300 font-mono mt-0.5">
                      {(whatIfResult.played_move as any).eval_str != null
                        ? `${(whatIfResult.played_move as any).eval_str} eval`
                        : ''} · {(
                          (boardFlipped ? 1 - whatIfResult.played_move.win_probability : whatIfResult.played_move.win_probability) * 100
                        ).toFixed(1)}% win
                    </div>
                  </div>
                  <div className="bg-slate-800/50 p-3 rounded-lg">
                    <div className="text-[10px] text-slate-500 uppercase font-semibold">Alternative Move</div>
                    <div className="text-sm font-bold text-white mt-1">{(whatIfResult.alternative_move as any).san || whatIfResult.alternative_move.uci}</div>
                    <div className="text-slate-300 font-mono mt-0.5">
                      {(whatIfResult.alternative_move as any).eval_str != null
                        ? `${(whatIfResult.alternative_move as any).eval_str} eval`
                        : ''} · {(
                          (boardFlipped ? 1 - whatIfResult.alternative_move.win_probability : whatIfResult.alternative_move.win_probability) * 100
                        ).toFixed(1)}% win
                    </div>
                  </div>
                </div>
                <p className={`font-semibold text-sm mt-1 ${
                  whatIfResult.probability_divergence.win_probability_delta > 0.03 ? 'text-emerald-400' :
                  whatIfResult.probability_divergence.win_probability_delta < -0.03 ? 'text-rose-400' :
                  'text-slate-300'
                }`}>
                  {whatIfResult.probability_divergence.recommendation}
                </p>
              </div>
            )}
          </div>

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
                  <p className="text-[10px] text-slate-500 mt-1 font-mono">
                    {prediction.win_probability > 0.6 ? '▲ White is winning' :
                     prediction.win_probability < 0.4 ? '▼ Black is winning' :
                     '= Position is balanced'}
                  </p>
                </div>

                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                  <p className="text-xs text-slate-400 uppercase font-semibold">Collapse Risk</p>
                  <p className={`text-3xl font-extrabold mt-1 ${
                    prediction.collapse_probability > 0.6 ? 'text-red-400' :
                    prediction.collapse_probability > 0.35 ? 'text-orange-400' : 'text-green-400'
                  }`}>
                    {(prediction.collapse_probability * 100).toFixed(1)}%
                  </p>
                  <p className="text-[10px] text-slate-500 mt-1 font-mono">
                    {prediction.collapse_probability > 0.6 ? '⚠ High time-pressure risk' :
                     prediction.collapse_probability > 0.35 ? '~ Moderate risk' :
                     '✓ Low risk'}
                  </p>
                </div>
              </div>

              {/* SHAP Factor Breakdown */}
              {(prediction.top_positive_factors?.length > 0 || prediction.top_negative_factors?.length > 0) && (
                <div className="bg-slate-900/40 p-4 rounded-xl border border-slate-800 space-y-3">
                  <div className="flex items-center gap-2 text-xs font-bold text-slate-300">
                    <Brain className="w-4 h-4 text-indigo-400" />
                    <span>Position Factor Breakdown (SHAP)</span>
                  </div>
                  <div className="space-y-1.5">
                    {[...(prediction.top_positive_factors || []), ...(prediction.top_negative_factors || [])]
                      .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
                      .slice(0, 5)
                      .map((f, i) => (
                        <div key={i} className="flex items-center gap-2">
                          <span className={`text-[10px] font-bold w-[30px] text-right mr-2 ${
                            f.impact >= 0 ? 'text-emerald-400' : 'text-rose-400'
                          }`}>{f.impact >= 0 ? '+' : ''}{(f.impact * 100).toFixed(1)}%</span>
                          <div className="flex-1 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                f.impact >= 0 ? 'bg-emerald-500' : 'bg-rose-500'
                              }`}
                              style={{ width: `${Math.min(100, Math.abs(f.impact) * 400)}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-slate-400 font-mono truncate max-w-[120px]">{f.feature}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}

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
                  <option value="< 1000">&lt; 1000 ELO</option>
                  <option value="1000-1200">1000-1200 ELO</option>
                  <option value="1200-1400">1200-1400 ELO</option>
                  <option value="1400-1600">1400-1600 ELO</option>
                  <option value="1600-1800">1600-1800 ELO</option>
                  <option value="1800-2000">1800-2000 ELO</option>
                  <option value="2000+">2000+ ELO</option>
                </select>
              </div>

              <div className="space-y-3">
                {eloSimResult.top_candidate_moves.length === 0 ? (
                  <div className="text-slate-400 text-xs italic text-center py-2">
                    No candidate moves found. (Game over?)
                  </div>
                ) : (
                  eloSimResult.top_candidate_moves.map((cand, i) => (
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
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Game Review Summary Panel — Chess.com Layout */}
      <div className="glass-panel rounded-2xl overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-slate-800 flex items-center justify-between">
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <span>Game Review</span>
          </h3>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 font-mono">ChessTrace estimated rating</span>
          </div>
        </div>

        {/* Column Headers: White | — | Black */}
        <div className="px-6 pt-4 pb-2 grid grid-cols-[1fr_auto_1fr] items-center gap-2">
          {/* White player header */}
          <div className="text-right flex flex-col items-end">
            <div className="text-xs font-bold text-slate-300 font-mono truncate">{gameMeta?.white_player || 'White'}</div>
            <div className="text-2xl font-extrabold text-white font-mono leading-none mt-1">{whiteRating}</div>
            <div className="text-[10px] text-indigo-400 font-mono">Est.</div>
          </div>

          <div className="w-16" /> {/* Center spacer */}

          {/* Black player header */}
          <div className="text-left flex flex-col items-start">
            <div className="text-xs font-bold text-slate-300 font-mono truncate">{gameMeta?.black_player || 'Black'}</div>
            <div className="text-2xl font-extrabold text-white font-mono leading-none mt-1">{blackRating}</div>
            <div className="text-[10px] text-indigo-400 font-mono">Est.</div>
          </div>
        </div>

        {/* Accuracy Row */}
        <div className="px-6 py-2 grid grid-cols-[1fr_auto_1fr] items-center gap-2">
          {/* White accuracy bar + number */}
          <div className="flex items-center justify-end gap-3">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-extrabold text-white font-mono">{whiteAccuracy}</span>
              <span className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider">Accuracy</span>
            </div>
            <div className="flex-1 max-w-[120px] bg-slate-800 h-2 rounded-full overflow-hidden">
              <div className="bg-blue-400 h-full rounded-full transition-all" style={{ width: `${whiteAccuracy}%` }} />
            </div>
          </div>

          <div className="w-16" />

          {/* Black accuracy bar + number */}
          <div className="flex items-center justify-start gap-3">
            <div className="flex-1 max-w-[120px] bg-slate-800 h-2 rounded-full overflow-hidden">
              <div className="bg-emerald-400 h-full rounded-full transition-all" style={{ width: `${blackAccuracy}%` }} />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-slate-500 uppercase font-semibold tracking-wider">Accuracy</span>
              <span className="text-sm font-extrabold text-white font-mono">{blackAccuracy}</span>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div className="mx-6 border-t border-slate-800/60" />

        {/* Move Type Rows — clickable to jump to first move of that type */}
        <div className="px-6 py-3 space-y-1">
          {MOVE_TYPES.map((mt) => {
            const wCount = whiteCounts[mt.key] || 0;
            const bCount = blackCounts[mt.key] || 0;
            const wPct = (wCount / whiteTotalMoves) * 100;
            const bPct = (bCount / blackTotalMoves) * 100;

            const wFirstIdx = timeline.findIndex((m) => m.color === 'white' && (m as any).move_classification === mt.key);
            const bFirstIdx = timeline.findIndex((m) => m.color === 'black' && (m as any).move_classification === mt.key);

            const handleWhiteClick = () => {
              if (wFirstIdx !== -1) {
                setCurrentIndex(wFirstIdx);
                boardContainerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }
            };

            const handleBlackClick = () => {
              if (bFirstIdx !== -1) {
                setCurrentIndex(bFirstIdx);
                boardContainerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
              }
            };

            return (
              <div
                key={mt.key}
                className="grid grid-cols-[1fr_auto_auto_auto_1fr] items-center gap-2 py-1.5 px-2 rounded-xl"
              >
                {/* White side */}
                <div 
                  className={`flex items-center justify-end gap-2 group ${wFirstIdx !== -1 ? 'cursor-pointer hover:bg-slate-800/80 rounded-lg py-1 px-2 transition-colors' : 'opacity-40'}`}
                  onClick={handleWhiteClick}
                  title={wFirstIdx !== -1 ? `Jump to White's first ${mt.label}` : ''}
                >
                  {wCount > 0 && (
                    <span className={`text-sm font-extrabold font-mono ${mt.textColor}`}>{wCount}</span>
                  )}
                  <div className="flex-1 max-w-[140px] h-2 rounded-full overflow-hidden bg-slate-800/40">
                    {wCount > 0 && (
                      <div
                        className="h-full rounded-full transition-all"
                        style={{ width: `${Math.max(4, wPct * 2.5)}%`, backgroundColor: mt.color }}
                      />
                    )}
                  </div>
                </div>

                {/* Label */}
                <div className="w-[72px] text-center flex items-center justify-center gap-1">
                  <span className="text-xs font-semibold text-slate-400">{mt.label}</span>
                </div>

                {/* Icon — center */}
                <div className={`w-8 h-8 flex items-center justify-center rounded-full text-xs font-black flex-shrink-0 ${mt.bgColor} ${mt.textColor} border ${mt.borderColor}`}>
                  {mt.icon}
                </div>

                {/* Spacer */}
                <div className="w-[72px] text-center" />

                {/* Black side */}
                <div 
                  className={`flex items-center justify-start gap-2 group ${bFirstIdx !== -1 ? 'cursor-pointer hover:bg-slate-800/80 rounded-lg py-1 px-2 transition-colors' : 'opacity-40'}`}
                  onClick={handleBlackClick}
                  title={bFirstIdx !== -1 ? `Jump to Black's first ${mt.label}` : ''}
                >
                  <div className="flex-1 max-w-[140px] h-2 rounded-full overflow-hidden bg-slate-800/40">
                    {bCount > 0 && (
                      <div
                        className="h-full rounded-full transition-all"
                        style={{ width: `${Math.max(4, bPct * 2.5)}%`, backgroundColor: mt.color }}
                      />
                    )}
                  </div>
                  {bCount > 0 && (
                    <span className={`text-sm font-extrabold font-mono ${mt.textColor}`}>{bCount}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-500 font-mono">
          <span>{gameMeta?.white_player || 'White'} (White) · {whiteTotalMoves} moves</span>
          <span>{timeline.length} total moves analyzed</span>
          <span>{gameMeta?.black_player || 'Black'} (Black) · {blackTotalMoves} moves</span>
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

        {chartData.length === 0 ? (
          <div className="h-48 flex items-center justify-center text-slate-500 text-sm">
            No think time data available for this game (clock times may not have been recorded)
          </div>
        ) : (
          <div className="h-48 w-full cursor-pointer">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart 
                data={chartData} 
                margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
                onClick={(e: any) => {
                  if (e && e.activeLabel) {
                    const moveNumber = Number(e.activeLabel);
                    const idx = timeline.findIndex(m => m.move_number === moveNumber);
                    if (idx !== -1) {
                      setCurrentIndex(idx);
                      boardContainerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    }
                  }
                }}
                style={{ cursor: 'pointer' }}
              >
                <defs>
                  <linearGradient id="thinkColor" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366F1" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#6366F1" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="pressureColor" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.7} />
                    <stop offset="95%" stopColor="#f43f5e" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="move"
                  stroke="#64748B"
                  fontSize={10}
                  tick={{ fill: '#94a3b8' }}
                  minTickGap={35}
                />
                <YAxis stroke="#64748B" fontSize={10} unit="s" tick={{ fill: '#94a3b8' }} width={36} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0F172A',
                    borderColor: '#334155',
                    borderRadius: '12px',
                    color: '#fff',
                    fontSize: '12px',
                  }}
                  formatter={(val: any, name: any) => [`${val}s`, name === 'whiteThink' ? 'White Time' : 'Black Time']}
                />
                <Area type="monotone" dataKey="whiteThink" name="whiteThink" stroke="#f1f5f9" strokeWidth={2} fillOpacity={0.2} fill="#f1f5f9" dot={false} />
                <Area type="monotone" dataKey="blackThink" name="blackThink" stroke="#6366F1" strokeWidth={2} fillOpacity={0.5} fill="#6366F1" dot={false} />
                {currentMove && <ReferenceLine x={currentMove.move_number} stroke="#ec4899" strokeWidth={2} strokeDasharray="3 3" />}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
};
