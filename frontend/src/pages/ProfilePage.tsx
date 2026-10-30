import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  Users,
  Award,
  BookOpen,
  Sparkles,
  ExternalLink,
  Activity,
  TrendingUp,
  TrendingDown,
  User,
  Loader2,
} from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import { api } from '../api/client';
import type {
  PlayerProfileResponse,
  ArchetypeResponse,
  SimilarityResponse,
  PatternsResponse,
  OpeningReportResponse,
  BrilliancyResponse,
} from '../api/client';

interface ProfilePageProps {
  username: string;
}

function StatCard({
  label,
  value,
  sub,
  accent = '#E8B66A',
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}) {
  return (
    <div
      className="rounded-xl p-5 space-y-1"
      style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.05)' }}
    >
      <span className="text-xs uppercase font-semibold tracking-wider" style={{ color: 'var(--ct-text-muted)' }}>
        {label}
      </span>
      <p className="text-3xl font-extrabold font-mono" style={{ color: accent }}>
        {value}
      </p>
      {sub && <p className="text-xs" style={{ color: 'var(--ct-text-muted)' }}>{sub}</p>}
    </div>
  );
}

export const ProfilePage: React.FC<ProfilePageProps> = ({ username }) => {
  const [profile, setProfile] = useState<PlayerProfileResponse | null>(null);
  const [archetype, setArchetype] = useState<ArchetypeResponse | null>(null);
  const [similarity, setSimilarity] = useState<SimilarityResponse | null>(null);
  const [patterns, setPatterns] = useState<PatternsResponse | null>(null);
  const [openings, setOpenings] = useState<OpeningReportResponse | null>(null);
  const [brilliances, setBrilliances] = useState<BrilliancyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!username) return;
    const fetchProfileData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [profRes, archRes, simRes, patRes, openRes, brilRes] = await Promise.all([
          api.get<PlayerProfileResponse>(`/analysis/profile/${username}`),
          api.get<ArchetypeResponse>(`/analysis/archetype/${username}`),
          api.get<SimilarityResponse>(`/analysis/similarity/${username}`),
          api.get<PatternsResponse>(`/analysis/patterns/${username}`),
          api.get<OpeningReportResponse>(`/analysis/openings/${username}`).catch(() => null),
          api.get<BrilliancyResponse>(`/analysis/brilliances/${username}`).catch(() => null),
        ]);
        setProfile(profRes.data);
        setArchetype(archRes.data);
        setSimilarity(simRes.data);
        setPatterns(patRes.data);
        if (openRes) setOpenings(openRes.data);
        if (brilRes) setBrilliances(brilRes.data);
      } catch (err: any) {
        console.error('Failed loading profile data', err);
        setError(
          err.response?.status === 404
            ? 'No games found for this player. Import their games in the Catalog first!'
            : 'Failed loading profile intelligence data.'
        );
      } finally {
        setLoading(false);
      }
    };
    fetchProfileData();
  }, [username]);

  if (!username) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-6 text-center">
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center"
          style={{ background: 'rgba(232,182,106,0.1)', border: '1px solid rgba(232,182,106,0.2)' }}
        >
          <User className="w-10 h-10" style={{ color: 'var(--ct-gold)' }} />
        </div>
        <div>
          <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--ct-text-primary)' }}>
            Enter Your Username
          </h2>
          <p className="text-sm max-w-md" style={{ color: 'var(--ct-text-muted)' }}>
            To generate a personal cognitive fingerprint, enter your username in the top navigation bar.
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-6 text-center">
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center"
          style={{ background: 'rgba(220,38,38,0.1)', border: '1px solid rgba(220,38,38,0.2)' }}
        >
          <AlertTriangle className="w-10 h-10" style={{ color: '#EF4444' }} />
        </div>
        <div>
          <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--ct-text-primary)' }}>Profile Not Found</h2>
          <p className="text-sm max-w-md" style={{ color: 'var(--ct-text-muted)' }}>{error}</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-32 gap-6">
        <Loader2 className="w-10 h-10 animate-spin" style={{ color: 'var(--ct-gold)' }} />
        <p className="text-sm" style={{ color: 'var(--ct-text-muted)' }}>
          Generating cognitive fingerprint for {username}…
        </p>
      </div>
    );
  }

  const clockCurveData = profile?.accuracy_vs_clock.map((b) => ({
    bucket: b.clock_bucket,
    userAccuracy: b.accuracy_pct,
    eloAverage: 78.5,
    thinkTimeSec: b.avg_think_time_sec.toFixed(1),
  })) || [];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="space-y-6"
    >
      {/* ── Header Banner ────────────────────────────────────── */}
      <div
        className="glass-panel rounded-2xl px-6 py-5 flex flex-wrap items-center justify-between gap-5"
      >
        <div className="flex items-center gap-4">
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center text-[#10152F] text-xl font-black shadow-lg"
            style={{ background: 'linear-gradient(135deg, var(--ct-gold), #B8944E)' }}
          >
            {username.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'var(--ct-text-primary)' }}>{username}</h1>
            <p className="text-xs mt-0.5" style={{ color: 'var(--ct-text-muted)' }}>
              Cognitive Fingerprint &nbsp;·&nbsp; {profile?.total_games_analyzed || 0} games analyzed
            </p>
          </div>
        </div>

        {archetype && (
          <div
            className="flex items-center gap-3 px-5 py-3 rounded-2xl"
            style={{
              background: 'rgba(232,182,106,0.07)',
              border: '1px solid rgba(232,182,106,0.2)',
            }}
          >
            <Award className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--ct-gold)' }} />
            <div>
              <span className="text-[10px] uppercase font-semibold tracking-wider" style={{ color: 'var(--ct-text-muted)' }}>
                Playing Style
              </span>
              <p className="text-base font-bold" style={{ color: 'var(--ct-gold)' }}>{archetype.primary_archetype}</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Time Control Performance ──────────────────────────── */}
      {profile?.time_control_accuracy && (
        <div className="glass-panel p-5 rounded-2xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
              Time Control Performance
            </h3>
            <span className="text-xs" style={{ color: 'var(--ct-text-muted)' }}>Accuracy by format</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard
              label="Bullet (1m – 2m)"
              value={`${profile.time_control_accuracy.bullet_accuracy_pct}%`}
              sub="High speed reflex performance"
              accent="var(--ct-text-primary)"
            />
            <StatCard
              label="Blitz (3m – 5m)"
              value={`${profile.time_control_accuracy.blitz_accuracy_pct}%`}
              sub="Optimal balance of time & accuracy"
              accent="#30C670"
            />
            <StatCard
              label="Rapid (10m+)"
              value={`${profile.time_control_accuracy.rapid_accuracy_pct}%`}
              sub="Deep calculation advantage"
              accent="var(--ct-gold)"
            />
          </div>
        </div>
      )}

      {/* ── Phase Accuracy ───────────────────────────────────── */}
      {profile?.phase_accuracy && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[
            {
              label: 'Opening Phase',
              value: `${profile.phase_accuracy.opening_accuracy_pct}%`,
              time: profile.time_distribution.opening_time_pct.toFixed(0),
              desc: 'Solid book preparation across mainlines.',
              color: '#30C670',
              borderColor: '#30C670',
            },
            {
              label: 'Middlegame Tactics',
              value: `${profile.phase_accuracy.middlegame_accuracy_pct}%`,
              time: profile.time_distribution.middlegame_time_pct.toFixed(0),
              desc: 'Slight drops under tactical complexity.',
              color: 'var(--ct-gold)',
              borderColor: 'var(--ct-gold)',
            },
            {
              label: 'Endgame Technique',
              value: `${profile.phase_accuracy.endgame_accuracy_pct}%`,
              time: profile.time_distribution.endgame_time_pct.toFixed(0),
              desc: 'Technique degrades under time pressure.',
              color: '#F59E0B',
              borderColor: '#F59E0B',
            },
          ].map((p) => (
            <div
              key={p.label}
              className="glass-panel p-5 rounded-2xl"
              style={{ borderLeft: `3px solid ${p.borderColor}` }}
            >
              <span className="text-xs uppercase font-bold tracking-wider" style={{ color: p.color }}>
                {p.label}
              </span>
              <div className="flex justify-between items-baseline mt-2">
                <span className="text-3xl font-extrabold font-mono" style={{ color: 'var(--ct-text-primary)' }}>
                  {p.value}
                </span>
                <span className="text-xs font-mono" style={{ color: 'var(--ct-text-muted)' }}>
                  {p.time}% time used
                </span>
              </div>
              <p className="text-xs mt-2" style={{ color: 'var(--ct-text-muted)' }}>{p.desc}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Accuracy vs Clock Chart ───────────────────────────── */}
      <div className="glass-panel p-5 rounded-2xl space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2" style={{ color: 'var(--ct-gold)' }}>
            <Activity className="w-5 h-5" />
            <span className="text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
              Accuracy vs. Clock Remaining
            </span>
          </div>
          <span className="text-xs" style={{ color: 'var(--ct-text-muted)' }}>vs. ELO Benchmark (78.5%)</span>
        </div>
        <div className="h-64 w-full pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={clockCurveData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="bucket" stroke="#2A3050" tick={{ fontSize: 11, fill: '#6B7394' }} />
              <YAxis domain={[40, 100]} stroke="#2A3050" tick={{ fontSize: 11, fill: '#6B7394' }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#171E40',
                  borderColor: '#2A3050',
                  borderRadius: '10px',
                  color: '#F3F0E8',
                }}
                labelStyle={{ color: '#F3F0E8', fontWeight: 'bold' }}
              />
              <Legend wrapperStyle={{ color: '#A5ADC6', fontSize: '12px' }} />
              <Line
                type="monotone"
                dataKey="userAccuracy"
                name={`${username} Accuracy (%)`}
                stroke="#E8B66A"
                strokeWidth={2.5}
                dot={{ r: 4, fill: '#E8B66A' }}
              />
              <Line
                type="monotone"
                dataKey="eloAverage"
                name="ELO Benchmark Avg (%)"
                stroke="#A5ADC6"
                strokeWidth={1.5}
                strokeDasharray="5 5"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Tilt + Similarity ─────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Tilt Signature */}
        {profile && (
          <div className="glass-panel p-5 rounded-2xl space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
              <AlertTriangle className="w-4 h-4" style={{ color: '#F97316' }} />
              Cognitive Tilt Signature
            </div>
            <div className="grid grid-cols-2 gap-3">
              <StatCard
                label="Normal Think Pace"
                value={`${profile.tilt_signature.normal_avg_think_time_sec}s`}
                accent="var(--ct-text-primary)"
              />
              <StatCard
                label="Post-Material Loss"
                value={`${profile.tilt_signature.post_material_loss_think_time_sec}s`}
                accent="#EF4444"
              />
            </div>
            <div
              className="flex justify-between items-center px-4 py-3 rounded-xl"
              style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.12)' }}
            >
              <div className="flex items-center gap-2">
                {profile.tilt_signature.tilt_speedup_percentage > 0 ? (
                  <TrendingDown className="w-4 h-4" style={{ color: '#EF4444' }} />
                ) : (
                  <TrendingUp className="w-4 h-4" style={{ color: '#30C670' }} />
                )}
                <span className="text-xs font-medium" style={{ color: 'var(--ct-text-secondary)' }}>
                  Tilt Speedup Factor
                </span>
              </div>
              <span className="text-sm font-bold font-mono" style={{ color: '#EF4444' }}>
                {profile.tilt_signature.tilt_speedup_percentage > 0
                  ? `${profile.tilt_signature.tilt_speedup_percentage.toFixed(1)}% faster after blunders`
                  : profile.tilt_signature.tilt_speedup_percentage < 0
                  ? `${Math.abs(profile.tilt_signature.tilt_speedup_percentage).toFixed(1)}% slower after blunders`
                  : 'Steady pace'}
              </span>
            </div>
          </div>
        )}

        {/* Similarity Network */}
        {similarity && (
          <div className="glass-panel p-5 rounded-2xl space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
              <Users className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
              Style Similarity Network
            </div>
            <div className="space-y-2.5">
              {similarity.similar_players.map((sim, i) => (
                <div
                  key={i}
                  className="flex justify-between items-center px-4 py-3 rounded-xl"
                  style={{
                    background: 'var(--ct-navy)',
                    border: '1px solid rgba(255,255,255,0.05)',
                  }}
                >
                  <div>
                    <span className="font-semibold text-sm" style={{ color: 'var(--ct-text-primary)' }}>
                      {sim.username}
                    </span>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--ct-text-muted)' }}>
                      {sim.shared_traits.join(' · ')}
                    </p>
                  </div>
                  <span className="text-sm font-extrabold font-mono" style={{ color: 'var(--ct-gold)' }}>
                    {sim.similarity_score_pct}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Opening Health Report ─────────────────────────────── */}
      {openings && openings.openings.length > 0 && (
        <div className="glass-panel p-5 rounded-2xl space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
            <BookOpen className="w-4 h-4" style={{ color: '#00B5C8' }} />
            Opening Repertoire Report
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {openings.openings.map((op, i) => (
              <div
                key={i}
                className="rounded-xl p-4 space-y-2"
                style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.05)' }}
              >
                <div className="flex justify-between items-center">
                  <span
                    className="px-2 py-0.5 rounded text-xs font-bold font-mono"
                    style={{ background: 'rgba(232,182,106,0.1)', color: 'var(--ct-gold)', border: '1px solid rgba(232,182,106,0.2)' }}
                  >
                    {op.eco}
                  </span>
                  <span className="text-xs font-bold font-mono" style={{ color: '#30C670' }}>
                    {op.win_rate_pct}% Win
                  </span>
                </div>
                <h4 className="text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
                  {op.opening_name}
                </h4>
                <p className="text-xs" style={{ color: 'var(--ct-text-muted)' }}>{op.recommendation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Improvement Roadmap ──────────────────────────────── */}
      {patterns && patterns.recurring_patterns.length > 0 && (
        <div className="glass-panel p-5 rounded-2xl space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
            <Award className="w-4 h-4" style={{ color: '#F59E0B' }} />
            Improvement Roadmap &amp; Targeted Puzzles
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {patterns.recurring_patterns.map((pat, i) => {
              const puzzleTopic = pat.pattern_name.includes('Overthink') ? 'knightFork'
                : pat.pattern_name.includes('Rush') ? 'endgame'
                : 'backRankMate';
              const puzzleUrl = `https://lichess.org/training/${puzzleTopic}`;
              const severityColor = pat.impact_severity === 'high' ? '#EF4444' : pat.impact_severity === 'medium' ? '#F59E0B' : '#30C670';
              return (
                <div
                  key={i}
                  className="rounded-xl p-4 space-y-3"
                  style={{ background: 'var(--ct-navy)', border: '1px solid rgba(255,255,255,0.05)' }}
                >
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-sm" style={{ color: 'var(--ct-text-primary)' }}>
                      {pat.pattern_name}
                    </span>
                    <span
                      className="text-[10px] px-2 py-0.5 rounded-md uppercase font-bold"
                      style={{ background: `${severityColor}18`, color: severityColor, border: `1px solid ${severityColor}30` }}
                    >
                      {pat.impact_severity}
                    </span>
                  </div>
                  <p className="text-xs" style={{ color: 'var(--ct-text-muted)' }}>{pat.recommendation}</p>
                  <a
                    href={puzzleUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-all duration-150"
                    style={{
                      background: 'rgba(232,182,106,0.08)',
                      color: 'var(--ct-gold)',
                      border: '1px solid rgba(232,182,106,0.2)',
                    }}
                  >
                    Practice: {puzzleTopic}
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Brilliancy Hall of Fame ───────────────────────────── */}
      {brilliances && brilliances.top_brilliances.length > 0 && (
        <div className="glass-panel p-5 rounded-2xl space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--ct-text-primary)' }}>
            <Sparkles className="w-4 h-4" style={{ color: 'var(--ct-gold)' }} />
            Brilliancy Hall of Fame
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {brilliances.top_brilliances.map((b, i) => (
              <a
                key={i}
                href={`/?gameId=${b.game_id}&ply=${b.ply}#review`}
                target="_blank"
                rel="noreferrer"
                className="rounded-xl p-4 space-y-2 block transition-all duration-150"
                style={{
                  background: 'var(--ct-navy)',
                  border: '1px solid rgba(232,182,106,0.2)',
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(232,182,106,0.5)'; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = 'rgba(232,182,106,0.2)'; }}
              >
                <div className="flex justify-between items-center">
                  <span className="font-bold font-mono text-sm" style={{ color: 'var(--ct-gold)' }}>
                    Move {b.move_number}. {b.san}
                  </span>
                  <span className="text-xs font-mono" style={{ color: 'var(--ct-text-muted)' }}>
                    {b.anomaly_score.toFixed(2)}
                  </span>
                </div>
                <p className="text-xs italic" style={{ color: 'var(--ct-text-secondary)' }}>"{b.description}"</p>
                <p className="text-[10px]" style={{ color: 'var(--ct-text-muted)' }}>
                  {b.white_player} vs {b.black_player}
                </p>
              </a>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
};
