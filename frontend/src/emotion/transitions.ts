import type { Variants } from 'framer-motion';

/**
 * Shared motion variants for cinematic emotional transitions.
 */
export const EMOTION_VARIANTS: Variants = {
  enter: {
    opacity: 0,
    scale: 0.95,
    y: 10,
    filter: 'blur(4px)'
  },
  center: {
    opacity: 1,
    scale: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: {
      duration: 0.6,
      ease: [0.22, 1, 0.36, 1] // Custom quint ease-out
    }
  },
  exit: {
    opacity: 0,
    scale: 1.05,
    y: -10,
    filter: 'blur(4px)',
    transition: {
      duration: 0.4,
      ease: [0.32, 0, 0.67, 0] // Custom quint ease-in
    }
  }
};

/**
 * Ambient idle animation variants.
 */
export const IDLE_VARIANTS: Variants = {
  float: {
    y: [-4, 4, -4],
    transition: {
      duration: 6,
      repeat: Infinity,
      ease: "easeInOut"
    }
  },
  breathe: {
    scale: [1, 1.02, 1],
    transition: {
      duration: 4,
      repeat: Infinity,
      ease: "easeInOut"
    }
  }
};
