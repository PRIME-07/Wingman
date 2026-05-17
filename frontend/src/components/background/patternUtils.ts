export interface PatternItem {
  id: string;
  src: string;
  top: string;      // percentage
  left: string;     // percentage
  size: number;     // px
  rotate: number;   // deg
  opacity: number;
}

// Available expression filenames under /public/wingman/dark and /public/wingman/light
export const EXPRESSION_IMAGES = [
  'neutral.png',
  'happy.png',
  'excited.png',
  'glad.png',
  'proud.png',
  'laughing.png',
  'shy.png',
  'thankful.png',
  'inLove.png',
  'thinking.png'
];

/**
 * Generates a randomized, non-clustering distribution of wingman expression items.
 * Uses a grid-based jitter layout to ensure clean scattering without overlaps.
 */
export function generateBalancedPattern(
  imageList: string[],
  isDarkMode: boolean
): PatternItem[] {
  const items: PatternItem[] = [];
  
  // Define columns and rows for a virtual 7x3 grid (21 total cells) for a perfect spread
  const cols = 7;
  const rows = 3;
  const colWidth = 100 / cols;

  const TOP_OFFSET_PERCENT = 4;
  const HEIGHT_SPAN_PERCENT = 25; // 29% - 4% = 25% height span
  const rowHeight = HEIGHT_SPAN_PERCENT / rows;

  let idCounter = 0;

  // Track the chosen expression names in a grid to easily check neighbors
  const gridExpr: string[][] = Array(rows).fill(null).map(() => Array(cols).fill(''));

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      // Small 10% chance to organically skip a cell to keep it natural and prevent perfect rigidity
      if (Math.random() < 0.1) continue;

      const id = `pattern-${idCounter++}-${r}-${c}`;
      
      // Determine forbidden expression names by checking adjacent/diagonal grid cells
      const forbidden = new Set<string>();
      if (c > 0) {
        const leftExpr = gridExpr[r][c - 1];
        if (leftExpr) forbidden.add(leftExpr);
      }
      if (r > 0) {
        const topExpr = gridExpr[r - 1][c];
        if (topExpr) forbidden.add(topExpr);
        if (c > 0) {
          const topLeftExpr = gridExpr[r - 1][c - 1];
          if (topLeftExpr) forbidden.add(topLeftExpr);
        }
        if (c < cols - 1) {
          const topRightExpr = gridExpr[r - 1][c + 1];
          if (topRightExpr) forbidden.add(topRightExpr);
        }
      }

      // Filter image pool to exclude forbidden expressions
      const available = imageList.filter(name => !forbidden.has(name));
      const pool = available.length > 0 ? available : imageList;
      
      // Select expression image
      const srcName = pool[Math.floor(Math.random() * pool.length)];
      gridExpr[r][c] = srcName;

      const folder = isDarkMode ? 'dark' : 'light';
      const src = `/wingman/${folder}/${srcName}`;

      // Calculate base positions in percentages
      const baseLeft = c * colWidth;
      const baseTop = TOP_OFFSET_PERCENT + r * rowHeight;

      // Add controlled jitter to avoid grid look while preventing collisions
      const leftJitter = (Math.random() * 0.45 - 0.225) * colWidth; // Jitter within 45% of cell width
      const topJitter = (Math.random() * 0.4 - 0.2) * rowHeight; // Jitter within 40% of cell height

      const left = `${Math.max(2, Math.min(95, baseLeft + colWidth / 2 + leftJitter))}%`;
      const top = `${Math.max(TOP_OFFSET_PERCENT + 1, Math.min(TOP_OFFSET_PERCENT + HEIGHT_SPAN_PERCENT - 1, baseTop + rowHeight / 2 + topJitter))}%`;

      // Premium sizing: alternate through small, medium, and large classes with a small size jitter
      const sizeClasses = [40, 56, 78]; // small, medium, large in px
      const sizeClassIndex = (r + c) % 3;
      const sizeBase = sizeClasses[sizeClassIndex];
      const sizeJitter = Math.floor(Math.random() * 7) - 3; // +/- 3px
      const size = Math.max(34, sizeBase + sizeJitter);

      // Premium alternating rotations for beautiful floating visual rhythm
      const rotationDirection = (r + c) % 2 === 0 ? 1 : -1;
      const rotate = rotationDirection * (Math.floor(Math.random() * 7) + 6); // tilted between 6deg and 12deg

      // Increased opacity for luxury cinematic pop
      const opacity = isDarkMode
        ? parseFloat((Math.random() * (0.24 - 0.18) + 0.18).toFixed(3))
        : parseFloat((Math.random() * (0.34 - 0.24) + 0.24).toFixed(3));

      items.push({
        id,
        src,
        top,
        left,
        size,
        rotate,
        opacity
      });
    }
  }

  return items;
}
