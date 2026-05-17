import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { WingmanEmotion } from '../emotion-map';
import { MascotRenderer } from './MascotRenderer';
import { EMOTION_VARIANTS, IDLE_VARIANTS } from '../transitions';

interface EmotionTransitionProps {
  emotion: WingmanEmotion;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'hero';
  className?: string;
}

export const EmotionTransition: React.FC<EmotionTransitionProps> = ({ 
  emotion,
  size = 'md',
  className = ''
}) => {
  return (
    <div className={`relative ${className}`}>
      <AnimatePresence mode="wait">
        <motion.div
          key={emotion}
          variants={EMOTION_VARIANTS}
          initial="enter"
          animate="center"
          exit="exit"
          className="relative"
        >
          {/* Apply combined idle animations */}
          <motion.div
            variants={IDLE_VARIANTS}
            animate={["breathe"]}
          >
            <MascotRenderer emotion={emotion} size={size} />
          </motion.div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
};
