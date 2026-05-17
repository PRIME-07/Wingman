import React from 'react';
import { useEmotionEngine } from '../hooks/useEmotionEngine';
import { useTelemetryEmotion } from '../hooks/useTelemetryEmotion';
import { EmotionTransition } from './EmotionTransition';

interface MascotProps {
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'hero';
  className?: string;
  enableTelemetry?: boolean;
}

export const Mascot: React.FC<MascotProps> = ({ 
  size = 'md', 
  className = '',
  enableTelemetry = true
}) => {
  const { emotion } = useEmotionEngine();
  
  // Drive emotional shifts from telemetry stream
  useTelemetryEmotion(enableTelemetry);

  return (
    <EmotionTransition 
      emotion={emotion} 
      size={size} 
      className={className} 
    />
  );
};
