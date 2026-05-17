import { useState, useEffect, useMemo } from 'react';
import { generateBalancedPattern } from './patternUtils';
import type { PatternItem } from './patternUtils';

/**
 * Custom hook to generate and manage non-clustered, visually balanced background pattern positions.
 * Updates on mount and window resize (debounced) to maintain premium spacing characteristics.
 */
export function usePatternPositions(
  count: number,
  imageList: string[],
  isDarkMode: boolean
): PatternItem[] {
  // Use unique key depending on mode to trigger clean recalculation of assets when theme switches
  const [positions, setPositions] = useState<PatternItem[]>([]);

  // Function to trigger regeneration
  const regenerate = () => {
    const items = generateBalancedPattern(imageList, isDarkMode);
    
    // Slice or adjust to match the count requirements if needed
    setPositions(items.slice(0, count));
  };

  // Run on mount and theme change
  useEffect(() => {
    regenerate();
  }, [isDarkMode]);

  // Debounced resize handler to preserve performance
  useEffect(() => {
    let timeoutId: any;

    const handleResize = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        regenerate();
      }, 300); // 300ms debounce
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      clearTimeout(timeoutId);
    };
  }, [imageList, isDarkMode, count]);

  return useMemo(() => positions, [positions]);
}
