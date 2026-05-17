import type { WingmanEmotion } from './emotion-map';
import { EMOTION_PRIORITY } from './emotion-map';
import { EMOTION_TIMING } from './timing';

/**
 * State machine to manage emotional continuity and transitions.
 */
export class EmotionEngine {
  private currentEmotion: WingmanEmotion = 'happy';
  private lastChangeTimestamp: number = 0;
  private queue: WingmanEmotion[] = [];
  private listeners: ((emotion: WingmanEmotion) => void)[] = [];

  constructor() {
    this.lastChangeTimestamp = Date.now();
  }

  public subscribe(callback: (emotion: WingmanEmotion) => void) {
    this.listeners.push(callback);
    // Defer callback invocation to subsequent task loop to prevent React synchronous state update warnings
    setTimeout(() => {
      // Check if callback is still active (unsubscribed before timeout fired)
      if (this.listeners.includes(callback)) {
        callback(this.currentEmotion);
      }
    }, 0);
    return () => {
      this.listeners = this.listeners.filter(l => l !== callback);
    };
  }

  /**
   * Attempts to transition to a new emotion.
   * Respects priority and minimum persistence time.
   */
  public transition(newEmotion: WingmanEmotion, priority: boolean = false) {
    const now = Date.now();
    const timeSinceLastChange = now - this.lastChangeTimestamp;

    // High priority overrides can bypass persistence checks if it's a critical state shift
    const canChange = priority || timeSinceLastChange >= EMOTION_TIMING.MIN_PERSISTENCE;

    if (canChange) {
      this.setEmotion(newEmotion);
    } else {
      // Queue it up if it's higher priority than the current target in queue
      this.queue.push(newEmotion);
      this.processQueue();
    }
  }

  private setEmotion(emotion: WingmanEmotion) {
    if (this.currentEmotion === emotion) return;
    
    this.currentEmotion = emotion;
    this.lastChangeTimestamp = Date.now();
    
    // Defer listener notifications to prevent React synchronous state update warnings
    setTimeout(() => {
      this.listeners.forEach(l => l(emotion));
    }, 0);
  }

  private processQueue() {
    // Basic queue logic: if we can change now, take the highest priority one from the queue
    setTimeout(() => {
      if (this.queue.length > 0) {
        const next = this.queue.sort((a, b) => EMOTION_PRIORITY[b] - EMOTION_PRIORITY[a])[0];
        this.queue = [];
        this.transition(next);
      }
    }, EMOTION_TIMING.MIN_PERSISTENCE);
  }

  public getCurrent() {
    return this.currentEmotion;
  }
}

export const emotionEngine = new EmotionEngine();
