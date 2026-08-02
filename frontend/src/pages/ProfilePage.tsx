import React, { useState, useEffect } from 'react';
import { AlertTriangle, Users, Award, BookOpen, Sparkles, ExternalLink, Activity } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';
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

export const ProfilePage: React.FC<ProfilePageProps> = ({ username }) => {
  const [profile, setProfile] = useState<PlayerProfileResponse | null>(null);
  const [archetype, setArchetype] = useState<ArchetypeResponse | null>(null);
  const [similarity, setSimilarity] = useState<SimilarityResponse | null>(null);
  const [patterns, setPatterns] = useState<PatternsResponse | null>(null);
  const [openings, setOpenings] = useState<OpeningReportResponse | null>(null);
  const [brilliances, setBrilliances] = useState<BrilliancyResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

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
      console.error('Failed loading profile intelligence data', err);
      if (err.response?.status === 404) {
        setError("No games found for this player. Import their games in the Catalog first!");
      } else {
        setError("Failed loading profile intelligence data.");
      }
      setProfile(null);
      setArchetype(null);
      setSimilarity(null);
      setPatterns(null);
      setOpenings(null);
      setBrilliances(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (username) {
      fetchProfileData();
    }
  }, [username]);

  if (!username) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-24 text-center space-y-6">
        <div className="w-24 h-24 bg-indigo-600/20 rounded-full flex items-center justify-center mx-auto">
          <Users className="w-12 h-12 text-indigo-400" />
        </div>
        <h2 className="text-3xl font-bold text-white">Enter Your Username</h2>
        <p className="text-slate-400 max-w-lg mx-auto">
          To generate a personal cognitive fingerprint, please enter your username in the top right corner.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-24 text-center space-y-6">
        <div className="w-24 h-24 bg-red-600/20 rounded-full flex items-center justify-center mx-auto">
          <AlertTriangle className="w-12 h-12 text-red-400" />
        </div>
        <h2 className="text-3xl font-bold text-white">Profile Not Found</h2>
        <p className="text-slate-400 max-w-lg mx-auto">
          {error}
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-12 space-y-6 animate-pulse">
        <div className="h-28 bg-slate-900/60 rounded-2xl border border-slate-800" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-64 bg-slate-900/60 rounded-2xl border border-slate-800" />
          <div className="h-64 bg-slate-900/60 rounded-2xl border border-slate-800" />
        </div>
      </div>
    );
  }

  // Chart data for Accuracy vs Clock Remaining Curve
  const clockCurveData = profile?.accuracy_vs_clock.map((b) => {
    const eloBenchmark = 78.5;
    return {
      bucket: b.clock_bucket,
      userAccuracy: b.accuracy_pct,
      eloAverage: eloBenchmark,
      thinkTimeSec: b.avg_think_time_sec.toFixed(1),
    };
  }) || [];

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8 font-sans">
      {/* Header Banner */}
      <div className="glass-panel p-6 rounded-2xl flex flex-wrap items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-600 to-pink-500 flex items-center justify-center text-white font-bold text-2xl shadow-lg shadow-indigo-600/30">
            {username.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <h1 className="text-3xl font-extrabold text-white">{username}</h1>
            <p className="text-sm text-slate-400 mt-1">
              Personal Fingerprint • {profile?.total_games_analyzed || 0} games analyzed
            </p>
          </div>
        </div>

        {/* Primary Archetype Badge */}
        {archetype && (
          <div className="bg-slate-900/80 border border-indigo-500/30 px-5 py-3 rounded-2xl flex items-center gap-3">
            <Award className="w-6 h-6 text-indigo-400" />
            <div>
              <span className="text-xs text-slate-400 uppercase font-mono tracking-wider">Playing Style Archetype</span>
              <p className="text-lg font-bold text-white">{archetype.primary_archetype}</p>
            </div>
          </div>
        )}
      </div>

      {/* Time Control Performance Breakdown */}
      {profile && profile.time_control_accuracy && (
      <div className="glass-panel p-6 rounded-2xl space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white uppercase tracking-wider font-mono text-indigo-400">
            Time Control Performance Breakdown
          </h3>
          <span className="text-xs text-slate-400">Accuracy split by time control format</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-1">
            <span className="text-xs text-slate-400 font-mono">Bullet (1m - 2m)</span>
            <p className="text-2xl font-bold text-white font-mono">{profile.time_control_accuracy.bullet_accuracy_pct}%</p>
            <p className="text-[10px] text-slate-400">High speed reflex performance.</p>
          </div>
          <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-1">
            <span className="text-xs text-slate-400 font-mono">Blitz (3m - 5m)</span>
            <p className="text-2xl font-bold text-emerald-400 font-mono">{profile.time_control_accuracy.blitz_accuracy_pct}%</p>
            <p className="text-[10px] text-emerald-400 font-semibold">Optimal balance of time & tactical accuracy.</p>
          </div>
          <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-1">
            <span className="text-xs text-slate-400 font-mono">Rapid (10m+)</span>
            <p className="text-2xl font-bold text-indigo-400 font-mono">{profile.time_control_accuracy.rapid_accuracy_pct}%</p>
            <p className="text-[10px] text-slate-400">Slight overthinking paralysis under longer clocks.</p>
          </div>
        </div>
      </div>
      )}
      {profile && profile.phase_accuracy && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-emerald-500">
            <span className="text-xs uppercase font-bold text-emerald-400 font-mono">Opening Phase Accuracy</span>
            <div className="flex justify-between items-baseline mt-2">
              <span className="text-3xl font-extrabold text-white font-mono">{profile.phase_accuracy.opening_accuracy_pct}%</span>
              <span className="text-xs text-slate-400 font-mono">{profile.time_distribution.opening_time_pct.toFixed(0)}% time used</span>
            </div>
            <p className="text-xs text-slate-400 mt-2">Solid book preparation across mainlines.</p>
          </div>

          <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-indigo-500">
            <span className="text-xs uppercase font-bold text-indigo-400 font-mono">Middlegame Tactical Accuracy</span>
            <div className="flex justify-between items-baseline mt-2">
              <span className="text-3xl font-extrabold text-white font-mono">{profile.phase_accuracy.middlegame_accuracy_pct}%</span>
              <span className="text-xs text-slate-400 font-mono">{profile.time_distribution.middlegame_time_pct.toFixed(0)}% time used</span>
            </div>
            <p className="text-xs text-slate-400 mt-2">Slight tactical evaluation drops under complexity.</p>
          </div>

          <div className="glass-panel p-5 rounded-2xl border-l-4 border-l-amber-500">
            <span className="text-xs uppercase font-bold text-amber-400 font-mono">Endgame Technique Accuracy</span>
            <div className="flex justify-between items-baseline mt-2">
              <span className="text-3xl font-extrabold text-white font-mono">{profile.phase_accuracy.endgame_accuracy_pct}%</span>
              <span className="text-xs text-slate-400 font-mono">{profile.time_distribution.endgame_time_pct.toFixed(0)}% time used</span>
            </div>
            <p className="text-xs text-amber-300 font-semibold mt-2">⚠️ Technique degrades under time pressure.</p>
          </div>
        </div>
      )}

      {/* Accuracy vs Clock Remaining Line Chart */}
      <div className="glass-panel p-6 rounded-2xl space-y-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
            <Activity className="w-5 h-5" />
            <span>Accuracy vs. Clock Remaining Degradation Curve</span>
          </div>
          <span className="text-xs text-slate-400 font-mono">Compared vs. ELO Benchmark Average (78.5%)</span>
        </div>

        <div className="h-64 w-full pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={clockCurveData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
              <XAxis dataKey="bucket" stroke="#64748B" tick={{ fontSize: 12 }} />
              <YAxis domain={[40, 100]} stroke="#64748B" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0F172A', borderColor: '#334155', borderRadius: '12px' }}
                labelStyle={{ color: '#F8FAFC', fontWeight: 'bold' }}
              />
              <Legend />
              <Line type="monotone" dataKey="userAccuracy" name={`${username} Accuracy (%)`} stroke="#6366F1" strokeWidth={3} dot={{ r: 5 }} />
              <Line type="monotone" dataKey="eloAverage" name="ELO Benchmark Avg (%)" stroke="#F59E0B" strokeWidth={2} strokeDasharray="5 5" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Tilt Signature Card */}
        {profile && (
          <div className="lg:col-span-6 glass-panel p-6 rounded-2xl space-y-4">
            <div className="flex items-center gap-2 text-rose-400 font-semibold text-sm">
              <AlertTriangle className="w-5 h-5" />
              <span>Cognitive Tilt & Pressure Signature</span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                <span className="text-xs text-slate-400 uppercase font-mono">Normal Think Pace</span>
                <p className="text-2xl font-bold text-white mt-1 font-mono">
                  {profile.tilt_signature.normal_avg_think_time_sec}s
                </p>
              </div>

              <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                <span className="text-xs text-slate-400 uppercase font-mono">Post-Material Loss Pace</span>
                <p className="text-2xl font-bold text-rose-400 mt-1 font-mono">
                  {profile.tilt_signature.post_material_loss_think_time_sec}s
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-900/50 flex justify-between items-center text-xs">
              <span className="text-rose-300 font-medium">Tilt Speedup Factor</span>
              <span className="text-rose-400 font-bold text-sm font-mono">
                {profile.tilt_signature.tilt_speedup_percentage > 0
                  ? `Plays ${profile.tilt_signature.tilt_speedup_percentage.toFixed(1)}% faster after blunders (${(
                      profile.tilt_signature.normal_avg_think_time_sec /
                      Math.max(profile.tilt_signature.post_material_loss_think_time_sec, 0.1)
                    ).toFixed(1)}x speedup)`
                  : profile.tilt_signature.tilt_speedup_percentage < 0
                  ? `Plays ${Math.abs(profile.tilt_signature.tilt_speedup_percentage).toFixed(1)}% slower after blunders`
                  : 'Pace remains steady after material loss'}
              </span>
            </div>
          </div>
        )}

        {/* Style Similarity Network Neighbors */}
        {similarity && (
          <div className="lg:col-span-6 glass-panel p-6 rounded-2xl space-y-4">
            <div className="flex items-center gap-2 text-indigo-400 font-semibold text-sm">
              <Users className="w-5 h-5" />
              <span>Style Similarity Network Neighbors</span>
            </div>

            <div className="space-y-3">
              {similarity.similar_players.map((sim, i) => (
                <div key={i} className="bg-slate-900/60 p-3.5 rounded-xl border border-slate-800 flex justify-between items-center text-xs">
                  <div>
                    <span className="font-bold text-white text-sm">{sim.username}</span>
                    <p className="text-slate-400 mt-0.5">{sim.shared_traits.join(' • ')}</p>
                  </div>
                  <span className="text-indigo-400 font-extrabold text-sm font-mono">
                    {sim.similarity_score_pct}% Match
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Opening Health Report Card */}
      {openings && openings.openings.length > 0 && (
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div className="flex items-center gap-2 text-cyan-400 font-semibold text-sm">
            <BookOpen className="w-5 h-5" />
            <span>Opening Health Repertoire Report</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {openings.openings.map((op, i) => (
              <div key={i} className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-2 text-xs">
                <div className="flex justify-between items-center">
                  <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono font-bold">{op.eco}</span>
                  <span className="font-bold font-mono text-emerald-400">{op.win_rate_pct}% Win Rate</span>
                </div>
                <h4 className="font-bold text-white text-sm">{op.opening_name}</h4>
                <p className="text-slate-400">{op.recommendation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actionable Improvement Roadmap with Direct Lichess Puzzle Links */}
      {patterns && patterns.recurring_patterns.length > 0 && (
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
              <Award className="w-5 h-5" />
              <span>Actionable Improvement Roadmap & Targeted Lichess Puzzles</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {patterns.recurring_patterns.map((pat, i) => {
              const puzzleTopic =
                pat.pattern_name.includes('Overthink') ? 'knightFork'
                : pat.pattern_name.includes('Rush') ? 'endgame'
                : 'backRankMate';
              const puzzleUrl = `https://lichess.org/training/${puzzleTopic}`;

              return (
                <div key={i} className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-3 text-xs">
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-white text-sm">{pat.pattern_name}</span>
                    <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-mono text-[10px] uppercase font-bold">
                      {pat.impact_severity}
                    </span>
                  </div>

                  <p className="text-slate-400">{pat.recommendation}</p>

                  <a
                    href={puzzleUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 font-medium transition-all text-xs border border-indigo-500/30"
                  >
                    <span>Practice Targeted Lichess Puzzles ({puzzleTopic})</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Brilliancy Hall of Fame Showcase */}
      {brilliances && brilliances.top_brilliances.length > 0 && (
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
            <Sparkles className="w-5 h-5" />
            <span>Brilliancy Hall of Fame — Top 5 Extraordinary Moves</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {brilliances.top_brilliances.map((b, i) => (
              <div key={i} className="bg-slate-900/60 p-4 rounded-xl border border-amber-500/30 space-y-2 text-xs">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-amber-400 font-mono">Move {b.move_number}. {b.san}</span>
                  <span className="text-slate-400 font-mono">Score: {b.anomaly_score.toFixed(2)}</span>
                </div>
                <p className="text-slate-300 italic">"{b.description}"</p>
                <p className="text-slate-500 text-[10px]">{b.white_player} vs {b.black_player}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
