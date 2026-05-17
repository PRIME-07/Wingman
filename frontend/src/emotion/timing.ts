/**
 * Timing constants for emotional transitions to prevent flickering
 * and ensure human-like persistence.
 */
export const EMOTION_TIMING = {
  /**
   * Minimum time an emotion must stay visible before it can transition (ms).
   * Prevents rapid "stuttering" during dense telemetry bursts.
   */
  MIN_PERSISTENCE: 1200,

  /**
   * Transition animation duration (ms).
   */
  TRANSITION_DURATION: 600,

  /**
   * Idle animation loop timings.
   */
  IDLE: {
    BREATH_CYCLE: 4000,
    BLINK_INTERVAL_MIN: 3000,
    BLINK_INTERVAL_MAX: 7000,
    FLOAT_CYCLE: 6000
  }
};
