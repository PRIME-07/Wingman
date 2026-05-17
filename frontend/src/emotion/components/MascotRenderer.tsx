import React from 'react';
import type { WingmanEmotion } from '../emotion-map';
import { useChatStore } from '../../stores/useChatStore';

interface MascotRendererProps {
  emotion: WingmanEmotion;
  className?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'hero';
}

const SIZE_MAP = {
  sm: 'w-7 h-7',
  md: 'w-9 h-9',
  lg: 'w-12 h-12',
  xl: 'w-24 h-24',
  hero: 'w-36 h-36 sm:w-48 sm:h-48'
};

export const MascotRenderer: React.FC<MascotRendererProps> = ({ 
  emotion, 
  className = '',
  size = 'md'
}) => {
  const { theme } = useChatStore();
  
  // Construct canonical asset path: /assets/{emotion}_{l|d}.png
  const suffix = theme === 'dark' ? 'd' : 'l';
  const src = new URL(`../../../assets/${emotion}_${suffix}.png`, import.meta.url).href;

  return (
    <div className={`relative flex items-center justify-center overflow-hidden ${SIZE_MAP[size]} ${className}`}>
      <img 
        src={src} 
        alt={`Wingman - ${emotion}`}
        className="w-full h-full object-contain select-none transition-transform duration-500 hover:scale-105"
        draggable={false}
        onError={(e) => {
          // Fallback to happy if asset is missing
          (e.target as HTMLImageElement).src = new URL(`../../../assets/happy_${suffix}.png`, import.meta.url).href;
        }}
      />
    </div>
  );
};
