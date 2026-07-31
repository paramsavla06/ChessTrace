import React, { useState, useEffect } from 'react';
import { AlertTriangle, Users, Award, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import type { PlayerProfileResponse, ArchetypeResponse, SimilarityResponse, PatternsResponse } from '../api/client';

interface ProfilePageProps {
  username: string;
}

export const ProfilePage: React.FC<ProfilePageProps> = ({ username }) => {
  const [profile, setProfile] = useState<PlayerProfileResponse | null>(null);
  const [archetype, setArchetype] = useState<ArchetypeResponse | null>(null);
  const [similarity, setSimilarity] = useState<SimilarityResponse | null>(null);
  const [patterns, setPatterns] = useState<PatternsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchProfileData = async () => {
    setLoading(true);
    try {
      const [profRes, archRes, simRes, patRes] = await Promise.all([
        api.get<PlayerProfileResponse>(`/analysis/profile/${username}`),
        api.get<ArchetypeResponse>(`/analysis/archetype/${username}`),
        api.get<SimilarityResponse>(`/analysis/similarity/${username}`),
        api.get<PatternsResponse>(`/analysis/patterns/${username}`),
      ]);

      setProfile(profRes.data);
      setArchetype(archRes.data);
      setSimilarity(simRes.data);
      setPatterns(patRes.data);
    } catch (err) {
      console.error('Failed loading profile intelligence data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfileData();
  }, [username]);

  if (loading) {
    return (
      <div className="py-24 text-center text-slate-400">
        Computing K-Means cluster archetypes & cognitive tilt signatures for '{username}'...
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">
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
              <span className="text-xs uppercase font-bold text-slate-400">Playing Style Archetype</span>
              <p className="text-lg font-bold text-white">{archetype.primary_archetype}</p>
            </div>
          </div>
        )}
      </div>

      {/* Grid: Tilt Signature & Archetype Cluster */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Tilt Signature Card */}
        {profile && (
          <div className="glass-panel p-6 rounded-2xl space-y-4">
            <div className="flex items-center gap-2 text-rose-400 font-semibold text-sm">
              <AlertTriangle className="w-5 h-5" />
              <span>Cognitive Tilt & Pressure Signature</span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                <span className="text-xs text-slate-400 uppercase">Normal Think Pace</span>
                <p className="text-2xl font-bold text-white mt-1">
                  {profile.tilt_signature.normal_avg_think_time_sec}s
                </p>
              </div>

              <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                <span className="text-xs text-slate-400 uppercase">Post-Material Loss Pace</span>
                <p className="text-2xl font-bold text-rose-400 mt-1">
                  {profile.tilt_signature.post_material_loss_think_time_sec}s
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-900/50 flex justify-between items-center text-xs">
              <span className="text-rose-300 font-medium">Tilt Speedup Factor</span>
              <span className="text-rose-400 font-bold text-sm">
                -{profile.tilt_signature.tilt_speedup_percentage}% think time after blunder
              </span>
            </div>
          </div>
        )}

        {/* Similar Player Neighbors */}
        {similarity && (
          <div className="glass-panel p-6 rounded-2xl space-y-4">
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
                  <span className="text-indigo-400 font-extrabold text-sm">
                    {sim.similarity_score_pct}% Match
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Cross-Game Recurring Patterns */}
      {patterns && patterns.recurring_patterns.length > 0 && (
        <div className="glass-panel p-6 rounded-2xl space-y-4">
          <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
            <RefreshCw className="w-5 h-5" />
            <span>Cross-Game Recurring Blunder Patterns</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {patterns.recurring_patterns.map((pat, i) => (
              <div key={i} className="bg-slate-900/60 p-4 rounded-xl border border-slate-800 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-white text-sm">{pat.pattern_name}</span>
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] uppercase font-bold bg-amber-950/60 text-amber-400 border border-amber-800">
                    {pat.impact_severity} Severity
                  </span>
                </div>
                <p className="text-xs text-slate-300 italic">{pat.recommendation}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
