import axios from 'axios';

export const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface GameSummary {
  id: number;
  site: string | null;
  event: string | null;
  date: string | null;
  white_player: string | null;
  black_player: string | null;
  white_elo: number | null;
  black_elo: number | null;
  result: string;
  eco: string | null;
  time_control: string | null;
  move_count: number;
}

export interface TimelineMove {
  move_number: number;
  ply: number;
  color: string;
  san: string;
  uci: string;
  fen: string;
  material_balance: number;
  game_phase: string;
  white_mobility: number;
  black_mobility: number;
  white_pawn_shield: number;
  black_pawn_shield: number;
  think_time_sec: float;
  time_remaining_sec: float;
  is_time_pressure_120s: boolean;
  is_time_pressure_60s: boolean;
  is_time_pressure_30s: boolean;
  time_usage_ratio: number;
  time_control: string;
}

export interface PredictResponse {
  win_probability: number;
  collapse_probability: number;
  time_pressure_risk_multiplier: number;
  narrative_summary: string;
  top_positive_factors: Array<{ feature: string; impact: number }>;
  top_negative_factors: Array<{ feature: string; impact: number }>;
}

export interface WhatIfResponse {
  played_move: { uci: string; win_probability: number; collapse_probability: number };
  alternative_move: { uci: string; win_probability: number; collapse_probability: number };
  probability_divergence: {
    win_probability_delta: number;
    collapse_probability_delta: number;
    recommendation: string;
  };
}

export interface EloSimResponse {
  elo_bucket: string;
  fen: string;
  engine_recommendation: string;
  top_candidate_moves: Array<{
    san: string;
    uci: string;
    probability: number;
    expected_think_time_sec: number;
    is_engine_top_choice: boolean;
  }>;
}

export interface PlayerProfileResponse {
  player_name: string;
  total_games_analyzed: number;
  accuracy_vs_clock: Array<{ clock_bucket: string; move_count: number; avg_think_time_sec: number; accuracy_pct: number }>;
  tilt_signature: {
    normal_avg_think_time_sec: number;
    post_material_loss_think_time_sec: number;
    tilt_speedup_percentage: number;
    is_panic_tilted: boolean;
  };
  time_distribution: {
    opening_time_pct: number;
    middlegame_time_pct: number;
    endgame_time_pct: number;
  };
  phase_accuracy: {
    opening_accuracy_pct: number;
    middlegame_accuracy_pct: number;
    endgame_accuracy_pct: number;
  };
  panic_move_count: number;
  overthink_move_count: number;
}

export interface ArchetypeResponse {
  username: string;
  primary_archetype: string;
  secondary_archetype: string;
  archetype_scores: Record<string, number>;
  description: string;
}

export interface SimilarityResponse {
  username: string;
  similar_players: Array<{
    username: string;
    similarity_score_pct: number;
    shared_traits: string[];
  }>;
}

export interface PatternsResponse {
  username: string;
  total_games_scanned: number;
  recurring_patterns: Array<{
    pattern_name: string;
    category: string;
    frequency_count: number;
    impact_severity: string;
    recommendation: string;
  }>;
}

export interface OpeningReportResponse {
  username: string;
  total_games_analyzed: number;
  openings: Array<{
    eco: string;
    opening_name: string;
    total_played: number;
    win_rate_pct: number;
    wins: number;
    losses: number;
    draws: number;
    recommendation: string;
  }>;
}

export interface BrilliancyResponse {
  username: string;
  total_brilliances_found: number;
  top_brilliances: Array<{
    game_id: number;
    white_player: string;
    black_player: string;
    move_number: number;
    san: string;
    anomaly_score: number;
    description: string;
  }>;
}

export interface CompareResponse {
  player1: {
    username: string;
    archetype: string;
    normal_think_pace_sec: number;
    post_blunder_pace_sec: number;
    tilt_speedup_pct: number;
    panic_move_count: number;
    overthink_move_count: number;
  };
  player2: {
    username: string;
    archetype: string;
    normal_think_pace_sec: number;
    post_blunder_pace_sec: number;
    tilt_speedup_pct: number;
    panic_move_count: number;
    overthink_move_count: number;
  };
  head_to_head_summary: {
    tilt_vulnerability_winner: string;
    comparison_verdict: string;
  };
}

type float = number;
