import { useState, useEffect } from 'react';
import type { WingmanEmotion } from '../emotion-map';
import { emotionEngine } from '../engine';

export function useEmotionEngine() {
  const [emotion, setEmotion] = useState<WingmanEmotion>(emotionEngine.getCurrent());

  useEffect(() => {
    return emotionEngine.subscribe((newEmotion) => {
      setEmotion(newEmotion);
    });
  }, []);

  return {
    emotion,
    setEmotion: (e: WingmanEmotion) => emotionEngine.transition(e, true)
  };
}
