import type { Signal } from './contracts';
import { feedLabel } from './tokens';

/** Presentation only: probabilities must come from the Python signal-time model. */
export function signalConfidence(signal: Pick<Signal, 'confidence' | 'confidence_reason' | 'horizon_bars' | 'feed'>) {
  const value = signal.confidence;
  const available = typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1;
  return {
    available,
    label: available ? `${(value * 100).toFixed(1)}%` : 'Unavailable',
    detail: available
      ? `Calibrated model estimate at signal time: analytical target reached before stop within ${signal.horizon_bars} bars · ${feedLabel(signal.feed)}. Training excludes ambiguous and incomplete outcomes. This is not a probability of profit.`
      : signal.confidence_reason || 'No calibrated prediction was recorded for this signal.',
  };
}
