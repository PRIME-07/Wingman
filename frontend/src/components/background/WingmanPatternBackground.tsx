import React from 'react';
import { useChatStore } from '../../stores/useChatStore';
import { usePatternPositions } from './usePatternPositions';
import { EXPRESSION_IMAGES } from './patternUtils';

export const WingmanPatternBackground: React.FC = () => {
  const { theme } = useChatStore();
  const isDarkMode = theme === 'dark';

  // Target count: 20 items (will render cleanly within 18-28 range)
  const items = usePatternPositions(20, EXPRESSION_IMAGES, isDarkMode);

  return (
    <div 
      className="absolute inset-0 w-full h-full overflow-hidden pointer-events-none select-none z-0"
      style={{ zIndex: 0 }}
    >
      {/* Scattered Outline Icons Layer */}
      <div className="absolute inset-0 w-full h-full">
        {items.map((item) => (
          <img
            key={item.id}
            src={item.src}
            alt="Wingman Background Motif"
            loading="eager"
            decoding="async"
            draggable={false}
            className="absolute transition-opacity duration-500 ease-in-out object-contain"
            style={{
              top: item.top,
              left: item.left,
              width: `${item.size}px`,
              height: `${item.size}px`,
              transform: `translate3d(-50%, -50%, 0) rotate(${item.rotate}deg)`,
              opacity: item.opacity,
            }}
          />
        ))}
      </div>

      {/* Luxury Cinematic Gradient Overlay */}
      <div 
        className="absolute inset-0 w-full h-full transition-colors duration-300"
        style={{
          background: isDarkMode
            ? 'linear-gradient(to bottom, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.6) 15%, rgba(0,0,0,1) 29%, rgba(0,0,0,1) 100%)'
            : 'linear-gradient(to bottom, rgba(255,255,255,0.3) 0%, rgba(255,255,255,0.6) 15%, rgba(255,255,255,1) 29%, rgba(255,255,255,1) 100%)'
        }}
      />
    </div>
  );
};
