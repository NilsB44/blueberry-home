export type Instrument = { name: string; epic: string; point_value: number };

export type TradingSettings = {
  enabled: boolean;
  price_check_seconds: number;
  near_points: number;
  cooldown_minutes: number;
  equity: number;
  risk_pct: number;
  ntfy_url: string;
  feed_enabled: boolean;
  feed_check_minutes: number;
  feed_url: string;
  instruments: Instrument[];
};

export type Price = {
  name: string;
  epic: string;
  bid: number | null;
  offer: number | null;
  mid: number | null;
  status: string;
  at: string;
};

export type TradingStatus = {
  ig_configured: boolean;
  ig_demo: boolean;
  enabled: boolean;
  price_checked_at: string | null;
  price_error: string;
  feed_checked_at: string | null;
  feed_error: string;
  prices: Price[];
};

export type Level = {
  id: number;
  created_at: string;
  instrument: string;
  bias: "long" | "short";
  entry_low: number;
  entry_high: number;
  stop: number;
  targets: string;
  note: string;
  valid_until: string | null;
  active: boolean;
  last_alert_at: string | null;
  price: number | null;
  distance: number | null;
  contracts: number | null;
};

export type Alert = {
  id: number;
  at: string;
  kind: "level" | "post" | "test";
  level_id: number | null;
  instrument: string;
  price: number | null;
  title: string;
  message: string;
  link: string;
  delivered: boolean;
  error: string;
};

export type Market = {
  epic: string;
  name: string;
  type: string;
  expiry: string;
  bid: number | null;
  offer: number | null;
};

export function num(x: number | null | undefined): string {
  return x == null
    ? "–"
    : x.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
