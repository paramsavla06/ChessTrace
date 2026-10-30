import React, {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Chessboard } from 'react-chessboard';
import {
  motion,
  useInView,
  useScroll,
  useTransform,
  AnimatePresence,
} from 'framer-motion';

/* ================================================================
   DESIGN TOKENS
   ================================================================ */
const C = {
  bg: '#F0EEE9',
  surface: '#FAF9F6',
  border: '#E2DED7',
  borderLight: '#EDEBE6',
  text: '#1A1916',
  textMuted: '#7A776E',
  textFaint: '#B0ACA5',
  accent: '#4A4540',
  mono: "'JetBrains Mono', 'Fira Code', monospace",
} as const;

const EASE_EXPO: [number, number, number, number] = [0.16, 1, 0.3, 1];

/* ================================================================
   CHESS POSITIONS — verified FEN strings for each step/feature
   ================================================================ */

// Sicilian Najdorf, move 11 — illustrative middlegame for features
const FEATURE_POSITIONS: Record<
  string,
  { fen: string; move?: string; from?: string; to?: string; label: string; eval: string; caption: string }
> = {
  analysis: {
    fen: 'r1bqkb1r/pp2pppp/2np1n2/6B1/3NP3/2N5/PPP2PPP/R2QKB1R w KQkq - 0 7',
    from: 'd4',
    to: 'f5',
    label: '★ Best move',
    eval: '+0.4',
    caption: 'Move 7: Nd4–f5 — engine-best continuation in the Sicilian Four Knights.',
  },
  engine: {
    fen: 'r1bqkb1r/pp2pppp/2np1n2/8/3NP3/2N5/PPP2PPP/R2QKB1R b KQkq - 2 6',
    from: 'f8',
    to: 'b4',
    label: '?! Inaccuracy',
    eval: '−0.8',
    caption: 'Evaluation: –0.8. Bb4 creates early pressure but surrenders the bishop pair.',
  },
  whatif: {
    fen: 'r1bqkb1r/pp2pppp/2np1n2/6B1/3NP3/2N5/PPP2PPP/R2QKB1R w KQkq - 0 7',
    from: 'g5',
    to: 'e7',
    label: '→ Alternative',
    eval: '+0.2',
    caption: 'What if Bxe7 instead? Exchange the dark-squared bishop for a slight initiative.',
  },
  openings: {
    fen: 'rnbqkb1r/pp2pppp/3p1n2/8/3NP3/8/PPP2PPP/RNBQKB1R w KQkq - 0 6',
    from: 'f1',
    to: 'c4',
    label: '📖 Book move',
    eval: '+0.3',
    caption: 'Bc4 — the main line of the Two Knights Defense. Studied by 89% of classical games.',
  },
  patterns: {
    fen: 'r2qkb1r/pp2pppp/2npbn2/6B1/3NP3/2N5/PPP2PPP/R2QKB1R w KQkq - 2 8',
    from: 'd1',
    to: 'd2',
    label: '↺ Pattern',
    eval: '+0.6',
    caption: 'Recurring pattern detected: early queen centralization leads to 76% win rate in your games.',
  },
};

const FEATURES = [
  { key: 'analysis', label: 'Move-by-move analysis' },
  { key: 'engine', label: 'Engine evaluation' },
  { key: 'whatif', label: 'What-if branching' },
  { key: 'openings', label: 'Opening repertoire' },
  { key: 'patterns', label: 'Cognitive patterns' },
] as const;

// Four process steps — a real game sequence (Scholar's mate attempt refuted)
const PROCESS_STEPS = [
  {
    number: '01',
    title: 'Import a game',
    description:
      'Upload a PGN file or fetch directly from Lichess with full clock timestamps.',
    fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    move: null,
    caption: 'Starting position — 32 pieces, infinite possibility.',
  },
  {
    number: '02',
    title: 'Analyze positions',
    description:
      'Stockfish 18 evaluates every move. XGBoost predicts collapse risk and win probability.',
    fen: 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
    move: 'Bc4',
    from: 'f1',
    to: 'c4',
    caption: 'Move 4: Bc4 — Italian Game. Evaluation: +0.3. Engine marks this as book.',
  },
  {
    number: '03',
    title: 'Explore critical moments',
    description:
      'Navigate move-by-move. Drag pieces to evaluate alternatives. Examine every decision.',
    fen: 'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 6',
    move: 'Nc3',
    from: 'b1',
    to: 'c3',
    caption: 'Move 6: Nc3 — both sides developed. Alternative arrow: d2–d4 central break.',
  },
  {
    number: '04',
    title: 'Understand the patterns',
    description:
      'Cognitive fingerprints, tilt signatures, time-pressure curves, and opening health reports.',
    fen: 'r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R b KQkq d3 0 7',
    move: 'd3',
    from: 'd2',
    to: 'd3',
    caption: 'Move 7: d3 — strategic consolidation. Your accuracy: 91.4%. Best move rate: 72%.',
  },
];


interface CursorBoardProps {
  fen: string;
  fromSquare?: string;
  toSquare?: string;
  showArrow?: boolean;
  size?: number;
}

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];

function squareToXY(sq: string, size: number, flipped = false): { x: number; y: number } {
  const file = FILES.indexOf(sq[0]);
  const rank = parseInt(sq[1]) - 1;
  const sqSize = size / 8;
  const col = flipped ? 7 - file : file;
  const row = flipped ? rank : 7 - rank;
  return {
    x: col * sqSize + sqSize / 2,
    y: row * sqSize + sqSize / 2,
  };
}

const CursorBoard: React.FC<CursorBoardProps> = ({
  fen,
  fromSquare,
  toSquare,
  showArrow = true,
  size = 340,
}) => {
  // Arrow path from fromSquare to toSquare
  const arrowPath = useMemo(() => {
    if (!showArrow || !fromSquare || !toSquare) return null;
    const from = squareToXY(fromSquare, size);
    const to = squareToXY(toSquare, size);
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const len = Math.sqrt(dx * dx + dy * dy);
    if (len < 1) return null;
    const ux = dx / len;
    const uy = dy / len;
    return {
      sx: from.x + ux * 12,
      sy: from.y + uy * 12,
      ex: to.x - ux * 14,
      ey: to.y - uy * 14,
    };
  }, [fromSquare, toSquare, size, showArrow]);

  // Square highlights
  const highlightSquares: Record<string, React.CSSProperties> = {};
  if (fromSquare) highlightSquares[fromSquare] = { background: 'rgba(26,25,22,0.15)', borderRadius: '2px' };
  if (toSquare)   highlightSquares[toSquare]   = { background: 'rgba(26,25,22,0.25)', borderRadius: '2px' };

  return (
    <div style={{ position: 'relative', width: size, height: size, userSelect: 'none' }}>
      <Chessboard
        position={fen}
        boardWidth={size}
        arePiecesDraggable={false}
        customSquareStyles={highlightSquares}
        customBoardStyle={{ borderRadius: '4px', boxShadow: 'none' }}
        customDarkSquareStyle={{ backgroundColor: '#C9C4BB' }}
        customLightSquareStyle={{ backgroundColor: '#F0EEE9' }}
        showBoardNotation={false}
      />

      {/* SVG overlay — analytical arrow only, pointer-events none */}
      {arrowPath && showArrow && (
        <svg
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: size,
            height: size,
            pointerEvents: 'none',
            overflow: 'hidden',
          }}
          viewBox={`0 0 ${size} ${size}`}
        >
          <defs>
            <marker id="ct-arrowhead" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto">
              <path d="M0,0.5 L0,6.5 L6,3.5 z" fill="rgba(26,25,22,0.6)" />
            </marker>
          </defs>
          <motion.line
            key={`arrow-${fromSquare}-${toSquare}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.35, delay: 0.1 }}
            x1={arrowPath.sx}
            y1={arrowPath.sy}
            x2={arrowPath.ex}
            y2={arrowPath.ey}
            stroke="rgba(26,25,22,0.55)"
            strokeWidth="3"
            strokeLinecap="round"
            markerEnd="url(#ct-arrowhead)"
          />
        </svg>
      )}
    </div>
  );
};

/* ================================================================
   PROCESS STEP BOARD — shows chess position per step, driven by
   scroll position in the process section.
   ================================================================ */
interface ProcessBoardProps {
  stepIndex: number;
  reduced?: boolean;
  size?: number;
}

const ProcessBoard: React.FC<ProcessBoardProps> = ({ stepIndex, reduced, size = 260 }) => {
  const step = PROCESS_STEPS[stepIndex];

  const highlightSquares: Record<string, React.CSSProperties> = {};
  if (step.from) {
    highlightSquares[step.from] = { background: 'rgba(26,25,22,0.14)' };
  }
  if (step.move && step.to) {
    highlightSquares[step.to] = { background: 'rgba(26,25,22,0.22)' };
  }

  const arrowPath = useMemo(() => {
    if (!step.from || !step.to) return null;
    const from = squareToXY(step.from, size);
    const to = squareToXY(step.to, size);
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const len = Math.sqrt(dx * dx + dy * dy);
    if (len < 1) return null;
    const ux = dx / len;
    const uy = dy / len;
    return {
      sx: from.x + ux * 12,
      sy: from.y + uy * 12,
      ex: to.x - ux * 14,
      ey: to.y - uy * 14,
    };
  }, [step.from, step.to, size]);

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <Chessboard
        position={step.fen}
        boardWidth={size}
        arePiecesDraggable={false}
        customSquareStyles={highlightSquares}
        customBoardStyle={{ borderRadius: '4px', boxShadow: 'none' }}
        customDarkSquareStyle={{ backgroundColor: '#C9C4BB' }}
        customLightSquareStyle={{ backgroundColor: '#F0EEE9' }}
        showBoardNotation={false}
      />
      {!reduced && arrowPath && (
        <svg
          style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
          width={size}
          height={size}
        >
          <defs>
            <marker
              id={`ph-${stepIndex}`}
              markerWidth="6"
              markerHeight="6"
              refX="3"
              refY="3"
              orient="auto"
            >
              <path d="M0,0 L0,6 L6,3 z" fill="rgba(26,25,22,0.5)" />
            </marker>
          </defs>
          <motion.line
            key={stepIndex}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3, delay: 0.1 }}
            x1={arrowPath.sx}
            y1={arrowPath.sy}
            x2={arrowPath.ex}
            y2={arrowPath.ey}
            stroke="rgba(26,25,22,0.5)"
            strokeWidth="2"
            strokeLinecap="round"
            markerEnd={`url(#ph-${stepIndex})`}
          />
        </svg>
      )}
    </div>
  );
};

/* ================================================================
   INLINE REVEAL wrapper
   ================================================================ */
function Reveal({
  children,
  delay = 0,
  y = 18,
  className = '',
}: {
  children: React.ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-50px' });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay, ease: EASE_EXPO }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ================================================================
   MAIN LANDING PAGE
   ================================================================ */
interface LandingPageProps {
  onEnterApp: () => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onEnterApp }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [reduced, setReduced] = useState(false);
  const [activeFeature, setActiveFeature] = useState<keyof typeof FEATURE_POSITIONS>('analysis');
  const [activeStep, setActiveStep] = useState(0);

  // Reduced motion
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const h = () => setReduced(mq.matches);
    mq.addEventListener('change', h);
    return () => mq.removeEventListener('change', h);
  }, []);

  // Hero scroll parallax
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress: heroP } = useScroll({ target: heroRef, offset: ['start start', 'end start'] });
  const heroScale = useTransform(heroP, [0, 1], [1, 1.03]);
  const heroOpacity = useTransform(heroP, [0, 0.8], [1, 0.55]);

  // Process section scroll — drive active step
  const processRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress: procP } = useScroll({
    target: processRef,
    offset: ['start center', 'end center'],
  });

  useEffect(() => {
    if (reduced) return;
    const unsub = procP.on('change', (v) => {
      const step = Math.min(3, Math.floor(v * 4));
      setActiveStep(step);
    });
    return unsub;
  }, [procP, reduced]);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
    setMenuOpen(false);
  };

  const featureData = FEATURE_POSITIONS[activeFeature];

  const nav = ['Features', 'Process', 'Analysis'];

  return (
    <div style={{ background: C.bg, fontFamily: "'Inter', -apple-system, sans-serif" }}>

      {/* ── OUTER CONTAINER ─────────────────────────────────── */}
      <motion.div
        initial={reduced ? {} : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: EASE_EXPO }}
        style={{
          maxWidth: '1280px',
          margin: '28px auto',
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: '14px',
          boxShadow: '0 2px 20px rgba(0,0,0,0.055)',
          overflow: 'hidden',
        }}
      >

        {/* ── NAV ───────────────────────────────────────────── */}
        <motion.header
          initial={reduced ? {} : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.15 }}
          style={{ borderBottom: `1px solid ${C.border}`, background: C.surface }}
        >
          <div className="flex items-center justify-between px-6 md:px-8 h-[52px]">
            <button onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} className="flex items-center gap-2.5">
              <img src="/ChessTraceLogo.png" alt="ChessTrace" className="w-6 h-6 rounded-md object-cover" />
              <span className="text-[14px] font-semibold tracking-[-0.02em]" style={{ color: C.text }}>ChessTrace</span>
            </button>

            <nav className="hidden md:flex items-center gap-7">
              {nav.map((item) => (
                <button
                  key={item}
                  onClick={() => scrollTo(item.toLowerCase())}
                  className="text-[13px] transition-colors duration-150"
                  style={{ color: C.textMuted }}
                  onMouseEnter={(e) => ((e.target as HTMLElement).style.color = C.text)}
                  onMouseLeave={(e) => ((e.target as HTMLElement).style.color = C.textMuted)}
                >
                  {item}
                </button>
              ))}
            </nav>

            <div className="flex items-center gap-3">
              <button
                onClick={onEnterApp}
                className="hidden md:flex items-center gap-1.5 text-[13px] font-medium px-4 py-1.5 rounded-full"
                style={{ background: C.text, color: C.surface }}
              >
                Open workspace <span style={{ opacity: 0.6 }}>→</span>
              </button>
              <button
                className="md:hidden w-8 h-8 flex flex-col justify-center items-center gap-1.5"
                onClick={() => setMenuOpen((o) => !o)}
              >
                {[0, 1, 2].map((i) => (
                  <span key={i} className="block w-5 h-px transition-all duration-200" style={{ background: C.text }} />
                ))}
              </button>
            </div>
          </div>

          {menuOpen && (
            <div className="md:hidden px-6 py-4 space-y-3" style={{ borderTop: `1px solid ${C.border}` }}>
              {nav.map((item) => (
                <button key={item} onClick={() => scrollTo(item.toLowerCase())} className="block text-[13px]" style={{ color: C.textMuted }}>
                  {item}
                </button>
              ))}
              <button onClick={onEnterApp} className="inline-flex items-center gap-1 text-[13px] font-medium px-4 py-1.5 rounded-full mt-2" style={{ background: C.text, color: C.surface }}>
                Open workspace →
              </button>
            </div>
          )}
        </motion.header>

        {/* ── HERO IMAGE ────────────────────────────────────── */}
        <div ref={heroRef} style={{ overflow: 'hidden' }}>
          <motion.div
            initial={reduced ? {} : { clipPath: 'inset(0 100% 0 0)' }}
            animate={{ clipPath: 'inset(0 0% 0 0)' }}
            transition={{ duration: 0.95, delay: 0.3, ease: EASE_EXPO }}
            style={{ overflow: 'hidden' }}
          >
            <motion.img
              src="/hero-chess.jpg"
              alt="Modernist chess set with geometric frosted glass and smoked crystal pieces on a cream and charcoal board, with an open art book beside it, in a clean studio environment"
              loading="eager"
              style={{
                width: '100%',
                display: 'block',
                aspectRatio: '16 / 7',
                objectFit: 'cover',
                objectPosition: 'center 30%',
                scale: heroScale,
                opacity: heroOpacity,
              }}
            />
          </motion.div>
          <div style={{ height: '1px', background: C.border }} />
        </div>

        {/* ── HERO EDITORIAL CONTENT ────────────────────────── */}
        <div
          className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-16 px-6 md:px-10 py-10 md:py-12"
          style={{ borderBottom: `1px solid ${C.border}` }}
        >
          <div>
            <motion.p
              initial={reduced ? {} : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.9, ease: EASE_EXPO }}
              className="text-[10px] font-semibold tracking-[0.14em] uppercase mb-5"
              style={{ color: '#A8A49C' }}
            >
              Chess intelligence for every move
            </motion.p>
            <motion.h1
              initial={reduced ? {} : { opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.65, delay: 1.0, ease: EASE_EXPO }}
              className="text-[28px] md:text-[34px] font-medium leading-[1.18] tracking-[-0.03em]"
              style={{ color: C.text }}
            >
              Understand the game —<br />before you play the<br />next move.
            </motion.h1>
          </div>

          <div className="flex flex-col justify-between gap-6 md:gap-0">
            <motion.div
              initial={reduced ? {} : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 1.1, ease: EASE_EXPO }}
              className="space-y-5"
            >
              <div className="flex flex-wrap gap-2">
                {['Engine-powered analysis', 'Move-by-move insights', 'Cognitive patterns'].map((tag) => (
                  <span key={tag} className="text-[11px] px-3 py-1 rounded-full" style={{ border: `1px solid ${C.border}`, color: C.textMuted, background: C.bg }}>
                    {tag}
                  </span>
                ))}
              </div>
              <p className="text-[14px] leading-[1.65]" style={{ color: C.textMuted, maxWidth: '360px' }}>
                ChessTrace analyzes chess games to reveal critical decisions, evaluate positions with Stockfish, and help players understand the moves that shape a game.
              </p>
            </motion.div>

            <motion.div
              initial={reduced ? {} : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 1.2, ease: EASE_EXPO }}
              className="flex items-center gap-4 pt-4"
            >
              <button
                onClick={onEnterApp}
                className="inline-flex items-center gap-2 text-[13px] font-medium px-5 py-2.5 rounded-full transition-all duration-150"
                style={{ background: C.text, color: C.surface }}
                onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              >
                Explore ChessTrace <span>→</span>
              </button>
              <button
                onClick={() => scrollTo('features')}
                className="text-[13px] transition-colors duration-150"
                style={{ color: '#A8A49C' }}
                onMouseEnter={(e) => ((e.target as HTMLElement).style.color = C.text)}
                onMouseLeave={(e) => ((e.target as HTMLElement).style.color = '#A8A49C')}
              >
                See capabilities
              </button>
            </motion.div>
          </div>
        </div>

        {/* ================================================================
            FEATURES SECTION — interactive board + feature selector
            ================================================================ */}
        <div id="features" style={{ borderBottom: `1px solid ${C.border}` }}>
          {/* Section header */}
          <div
            className="px-6 md:px-10 py-8 md:py-10"
            style={{ borderBottom: `1px solid ${C.borderLight}` }}
          >
            <Reveal>
              <p className="text-[10px] font-semibold tracking-[0.14em] uppercase mb-3" style={{ color: '#A8A49C' }}>
                Capabilities
              </p>
              <h2 className="text-[22px] md:text-[28px] font-medium tracking-[-0.025em] leading-[1.2]" style={{ color: C.text }}>
                Every layer of the game, made legible.
              </h2>
              <p className="text-[14px] mt-3 max-w-xl" style={{ color: C.textMuted, lineHeight: '1.65' }}>
                Move quality is only the beginning. Explore the decisions, evaluations, patterns,
                and alternatives that shape every game.
              </p>
            </Reveal>
          </div>

          {/* Main interactive composition */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-0">
            {/* Left: feature selector */}
            <div
              className="px-6 md:px-10 py-8 md:py-10 flex flex-col gap-0"
              style={{ borderRight: `1px solid ${C.borderLight}` }}
            >
              {FEATURES.map((f, i) => {
                const isActive = activeFeature === f.key;
                return (
                  <div key={f.key}>
                    <button
                      onClick={() => setActiveFeature(f.key as keyof typeof FEATURE_POSITIONS)}
                      className="w-full text-left flex items-start gap-4 transition-all duration-150"
                      style={{
                        padding: '14px 10px',
                        borderRadius: '8px',
                        background: isActive ? '#EDEAE3' : 'transparent',
                        border: 'none',
                        outline: 'none',
                        cursor: 'pointer',
                        width: '100%',
                      }}
                      onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = '#F5F3EE'; }}
                      onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
                    >
                      {/* Left accent bar — replaces the circle indicator */}
                      <div
                        style={{
                          flexShrink: 0,
                          marginTop: '3px',
                          width: '3px',
                          height: '18px',
                          borderRadius: '2px',
                          background: isActive ? C.text : '#D5D1CA',
                          transition: 'background 0.18s ease',
                        }}
                      />

                      <div style={{ flex: 1, minWidth: 0 }}>
                        {/* Label — full charcoal on all states, weight changes on active */}
                        <div
                          style={{
                            fontSize: '14px',
                            fontWeight: isActive ? 600 : 400,
                            color: isActive ? C.text : '#3A3832',
                            letterSpacing: '-0.01em',
                            lineHeight: '1.4',
                            transition: 'color 0.15s ease',
                          }}
                        >
                          {f.label}
                        </div>

                        {/* Subtitle always visible — gives content even when inactive */}
                        <div style={{ fontSize: '12px', color: isActive ? C.textMuted : '#9E9A93', marginTop: '3px', lineHeight: '1.5', transition: 'color 0.15s ease' }}>
                          {f.key === 'analysis' && 'Brilliant, best, inaccuracy, mistake, blunder'}
                          {f.key === 'engine' && 'Stockfish 18 · centipawn evaluation per position'}
                          {f.key === 'whatif' && 'Drag pieces or type moves to test alternatives'}
                          {f.key === 'openings' && 'ECO codes, win rates, opening recommendations'}
                          {f.key === 'patterns' && 'Tilt signatures, time-pressure, playing archetypes'}
                        </div>

                        {/* Expanded caption + eval pill — only when active */}
                        <AnimatePresence>
                          {isActive && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              exit={{ opacity: 0, height: 0 }}
                              transition={{ duration: 0.28, ease: EASE_EXPO }}
                              style={{ overflow: 'hidden' }}
                            >
                              <p style={{ fontSize: '13px', color: C.textMuted, lineHeight: '1.65', marginTop: '10px' }}>
                                {featureData.caption}
                              </p>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '10px' }}>
                                <span
                                  style={{
                                    fontSize: '11px',
                                    fontFamily: C.mono,
                                    fontWeight: 500,
                                    padding: '3px 10px',
                                    borderRadius: '99px',
                                    background: C.surface,
                                    border: `1px solid ${C.border}`,
                                    color: C.text,
                                  }}
                                >
                                  {featureData.label}
                                </span>
                                <span
                                  style={{
                                    fontSize: '12px',
                                    fontFamily: C.mono,
                                    fontWeight: 600,
                                    color: featureData.eval.startsWith('+') ? '#2D6A4A' : '#8B2A2A',
                                  }}
                                >
                                  {featureData.eval}
                                </span>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>

                      {/* Chevron — visible only on inactive to hint interactivity */}
                      <span
                        style={{
                          flexShrink: 0,
                          fontSize: '18px',
                          lineHeight: '1.2',
                          color: isActive ? 'transparent' : '#C5C1BA',
                          transition: 'color 0.15s ease',
                          userSelect: 'none',
                          marginTop: '1px',
                        }}
                      >
                        ›
                      </span>
                    </button>

                    {/* Hairline between items */}
                    {i < FEATURES.length - 1 && (
                      <div style={{ height: '1px', background: C.borderLight, margin: '0 10px' }} />
                    )}
                  </div>
                );
              })}
            </div>

            {/* Right: interactive board */}
            <Reveal className="flex items-start justify-center px-6 md:px-8 py-8 md:py-10 lg:sticky lg:top-4 self-start">
              <div>
                <p className="text-[10px] font-mono uppercase tracking-[0.12em] mb-4" style={{ color: '#A8A49C' }}>
                  Illustrative position — {featureData.caption.split('—')[0].trim()}
                </p>

                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeFeature}
                    initial={reduced ? {} : { opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={reduced ? {} : { opacity: 0, scale: 0.98 }}
                    transition={{ duration: 0.25, ease: EASE_EXPO }}
                  >
                    <CursorBoard
                      fen={featureData.fen}
                      fromSquare={featureData.from}
                      toSquare={featureData.to}
                      showArrow={true}
                      size={300}
                    />
                  </motion.div>
                </AnimatePresence>

                {/* File coordinate labels */}
                <div className="flex mt-2" style={{ width: '300px' }}>
                  {FILES.map((f) => (
                    <span
                      key={f}
                      style={{
                        width: `${300 / 8}px`,
                        textAlign: 'center',
                        fontSize: '9px',
                        color: '#C0BBAF',
                        fontFamily: C.mono,
                        flexShrink: 0,
                      }}
                    >
                      {f}
                    </span>
                  ))}
                </div>
              </div>
            </Reveal>
          </div>
        </div>

        {/* ================================================================
            PROCESS SECTION — scroll-driven chess position narrative
            ================================================================ */}
        <div id="process" style={{ borderBottom: `1px solid ${C.border}` }}>
          {/* Section header */}
          <div className="px-6 md:px-10 py-8 md:py-10" style={{ borderBottom: `1px solid ${C.borderLight}` }}>
            <Reveal>
              <p className="text-[10px] font-semibold tracking-[0.14em] uppercase mb-3" style={{ color: '#A8A49C' }}>
                Process
              </p>
              <h2 className="text-[22px] md:text-[28px] font-medium tracking-[-0.025em] leading-[1.2]" style={{ color: C.text }}>
                Four steps from game to insight.
              </h2>
            </Reveal>
          </div>

          {/* Process body */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-0">
            {/* Left: step text list — acts as scroll driver */}
            <div
              ref={processRef}
              className="px-6 md:px-10 py-8 md:py-10 space-y-0"
              style={{ borderRight: `1px solid ${C.borderLight}` }}
            >
              {PROCESS_STEPS.map((step, i) => {
                const isActive = activeStep === i;
                return (
                  <Reveal key={step.number} delay={i * 0.05}>
                    <button
                      className="w-full text-left py-8 flex gap-6 items-start transition-all duration-300"
                      style={{
                        borderBottom: i < PROCESS_STEPS.length - 1 ? `1px solid ${C.borderLight}` : 'none',
                        opacity: isActive ? 1 : 0.42,
                      }}
                      onClick={() => setActiveStep(i)}
                    >
                      {/* Number + progress line */}
                      <div className="flex flex-col items-center gap-2 flex-shrink-0" style={{ paddingTop: '2px' }}>
                        <span
                          className="text-[11px] font-mono font-semibold"
                          style={{ color: isActive ? C.text : C.textMuted }}
                        >
                          {step.number}
                        </span>
                        {/* Thin progress bar */}
                        {i < PROCESS_STEPS.length - 1 && (
                          <div
                            style={{
                              width: '1px',
                              height: '48px',
                              background: isActive ? C.accent : C.border,
                              transition: 'background 0.3s ease',
                            }}
                          />
                        )}
                      </div>

                      <div>
                        <h3
                          className="text-[15px] font-semibold tracking-[-0.015em] mb-2"
                          style={{ color: isActive ? C.text : C.textMuted }}
                        >
                          {step.title}
                        </h3>
                        <p className="text-[13px] leading-[1.65]" style={{ color: C.textMuted }}>
                          {step.description}
                        </p>
                        {isActive && (
                          <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ duration: 0.3 }}
                            className="text-[11px] mt-3 font-mono"
                            style={{ color: '#A8A49C' }}
                          >
                            {step.caption}
                          </motion.p>
                        )}
                      </div>
                    </button>
                  </Reveal>
                );
              })}
            </div>

            {/* Right: sticky chess board that updates with active step */}
            <div className="hidden lg:flex items-start justify-center px-8 py-10 lg:sticky lg:top-4 self-start">
              <div>
                <p className="text-[9px] font-mono uppercase tracking-[0.12em] mb-4" style={{ color: '#C0BBAF' }}>
                  Example sequence · illustrative
                </p>
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeStep}
                    initial={reduced ? {} : { opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={reduced ? {} : { opacity: 0, y: -6 }}
                    transition={{ duration: 0.3, ease: EASE_EXPO }}
                  >
                    <ProcessBoard stepIndex={activeStep} reduced={reduced} size={260} />
                  </motion.div>
                </AnimatePresence>

                {/* Step indicator dots */}
                <div className="flex gap-2 mt-5 justify-center">
                  {PROCESS_STEPS.map((_, i) => (
                    <button
                      key={i}
                      onClick={() => setActiveStep(i)}
                      style={{
                        width: activeStep === i ? '20px' : '6px',
                        height: '6px',
                        borderRadius: '3px',
                        background: activeStep === i ? C.text : C.border,
                        transition: 'all 0.25s ease',
                        border: 'none',
                        cursor: 'pointer',
                      }}
                    />
                  ))}
                </div>

                <p
                  className="text-[11px] text-center mt-3 font-mono"
                  style={{ color: '#A8A49C' }}
                >
                  {PROCESS_STEPS[activeStep].caption}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* ================================================================
            ANALYTICAL INTERLUDE — single annotated position study
            Wide board, editorial layout, SVG annotations
            ================================================================ */}
        <div
          id="analysis"
          style={{ borderBottom: `1px solid ${C.border}`, background: '#F4F2ED' }}
        >
          <div className="px-6 md:px-10 py-8 md:py-12">
            <Reveal>
              <p className="text-[10px] font-semibold tracking-[0.14em] uppercase mb-3" style={{ color: '#A8A49C' }}>
                Position study · illustrative example
              </p>
              <h2 className="text-[22px] md:text-[26px] font-medium tracking-[-0.025em] leading-[1.2] max-w-lg" style={{ color: C.text }}>
                The move that changed everything.
              </h2>
              <p className="text-[13px] mt-3 max-w-md" style={{ color: C.textMuted, lineHeight: '1.65' }}>
                A single decision separates a winning line from a drawn endgame.
                ChessTrace surfaces these moments automatically.
              </p>
            </Reveal>

            <div className="mt-10 flex flex-col lg:flex-row gap-10 lg:gap-16 items-start">
              {/* Board */}
              <Reveal delay={0.1} className="flex-shrink-0">
                <CursorBoard
                  fen="r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 6"
                  fromSquare="e1"
                  toSquare="g1"
                  showArrow={true}
                  size={280}
                />
                <p className="text-[10px] font-mono mt-3" style={{ color: '#C0BBAF' }}>
                  Italian Game — Move 6 · White to castle kingside
                </p>
              </Reveal>

              {/* Annotations */}
              <Reveal delay={0.18} className="flex-1 space-y-6">
                <div className="space-y-4">
                  {[
                    {
                      label: 'Before castling',
                      eval: '+0.3',
                      note: 'Equal game. Both sides fully developed in the Italian Four Knights.',
                      color: '#2D6A4A',
                    },
                    {
                      label: 'After O–O (castling)',
                      eval: '+0.8',
                      note: 'King safety secured. White gains a structural edge and initiative on the kingside.',
                      color: '#2D6A4A',
                    },
                    {
                      label: 'If Ke2 (alternative)',
                      eval: '−0.2',
                      note: 'King exposed in the center. Black can now launch a central pawn break with d5.',
                      color: '#8B2A2A',
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="flex gap-5 items-start"
                    >
                      <div
                        className="text-[13px] font-mono font-semibold w-[48px] flex-shrink-0 pt-0.5"
                        style={{ color: item.color }}
                      >
                        {item.eval}
                      </div>
                      <div>
                        <div className="text-[13px] font-semibold mb-1" style={{ color: C.text }}>
                          {item.label}
                        </div>
                        <div className="text-[13px]" style={{ color: C.textMuted, lineHeight: '1.6' }}>
                          {item.note}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div
                  className="text-[11px] font-mono px-4 py-3 rounded-lg"
                  style={{
                    border: `1px solid ${C.border}`,
                    color: '#A8A49C',
                    background: C.surface,
                    lineHeight: '1.7',
                  }}
                >
                  Stockfish 18 · depth 22 · illustrative position<br />
                  Move classifications: ★ Best · ?! Inaccuracy · ? Mistake · ?? Blunder
                </div>
              </Reveal>
            </div>
          </div>
        </div>

        {/* ================================================================
            FINAL CTA
            ================================================================ */}
        <div className="px-6 md:px-10 py-12 md:py-16 grid grid-cols-1 md:grid-cols-2 items-center gap-8">
          <Reveal>
            <h2
              className="text-[24px] md:text-[30px] font-medium tracking-[-0.025em] leading-[1.2]"
              style={{ color: C.text }}
            >
              Every game<br />has something<br />to teach you.
            </h2>
          </Reveal>

          <Reveal delay={0.1} className="flex flex-col gap-4 md:items-end">
            <p className="text-[13px] leading-relaxed md:text-right" style={{ color: C.textMuted, maxWidth: '300px' }}>
              Import any game. Navigate every move. Understand the decisions that shaped the result.
            </p>
            <button
              onClick={onEnterApp}
              className="inline-flex items-center gap-2 text-[13px] font-medium px-5 py-2.5 rounded-full self-start md:self-auto transition-opacity duration-150"
              style={{ background: C.text, color: C.surface }}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.82')}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
            >
              Start analyzing →
            </button>
          </Reveal>
        </div>

        {/* ── FOOTER ────────────────────────────────────────── */}
        <div
          className="px-6 md:px-10 py-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3"
          style={{ borderTop: `1px solid ${C.border}` }}
        >
          <div className="flex items-center gap-2">
            <img src="/ChessTraceLogo.png" alt="ChessTrace" className="w-5 h-5 rounded-md object-cover" />
            <span className="text-[12px]" style={{ color: '#A8A49C' }}>ChessTrace</span>
          </div>
          <nav className="flex items-center gap-5">
            {nav.map((item) => (
              <button
                key={item}
                onClick={() => scrollTo(item.toLowerCase())}
                className="text-[12px] transition-colors duration-150"
                style={{ color: '#A8A49C' }}
                onMouseEnter={(e) => ((e.target as HTMLElement).style.color = C.text)}
                onMouseLeave={(e) => ((e.target as HTMLElement).style.color = '#A8A49C')}
              >
                {item}
              </button>
            ))}
          </nav>
          <p className="text-[11px]" style={{ color: '#C4C0B9' }}>
            Powered by Stockfish 18 &amp; XGBoost ML · 2026
          </p>
        </div>

      </motion.div>

      <div style={{ height: '32px' }} />
    </div>
  );
};
