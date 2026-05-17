/**
 * Canonical list of supported emotion expressions.
 * Matches assets in public/expressions/
 */
export type WingmanEmotion = 
  | 'thinking'
  | 'recollecting'
  | 'happy'
  | 'sad'
  | 'laughing'
  | 'excited'
  | 'glad'
  | 'proud'
  | 'confused'
  | 'embarrassed'
  | 'skeptical'
  | 'shy'
  | 'thankful'
  | 'inLove'
  | 'sleepy'
  | 'worried'
  | 'angry'
  | 'bored'
  | 'shocked';

/**
 * Runtime namespace object — mirrors the WingmanEmotion type as a value.
 * Required for browser ESM module resolution when importing the type by name.
 */
export const WingmanEmotion = {
  thinking: 'thinking',
  recollecting: 'recollecting',
  happy: 'happy',
  sad: 'sad',
  laughing: 'laughing',
  excited: 'excited',
  glad: 'glad',
  proud: 'proud',
  confused: 'confused',
  embarrassed: 'embarrassed',
  skeptical: 'skeptical',
  shy: 'shy',
  thankful: 'thankful',
  inLove: 'inLove',
  sleepy: 'sleepy',
  worried: 'worried',
  angry: 'angry',
  bored: 'bored',
  shocked: 'shocked',
} as const;


export const ALL_EMOTIONS: WingmanEmotion[] = [
  'thinking', 'recollecting', 'happy', 'sad', 
  'laughing', 'excited', 'glad', 'proud', 'confused', 
  'embarrassed', 'skeptical', 'shy', 'thankful', 'inLove', 
  'sleepy', 'worried', 'angry', 'bored', 'shocked'
];

/**
 * Priority hierarchy for emotion overrides.
 * Higher values override lower ones.
 */
export const EMOTION_PRIORITY: Record<WingmanEmotion, number> = {
  shocked: 100,
  angry: 95,
  worried: 90,
  sad: 85,
  confused: 80,
  skeptical: 75,
  excited: 70,
  inLove: 65,
  thankful: 60,
  shy: 55,
  proud: 50,
  glad: 45,
  laughing: 40,
  embarrassed: 35,
  happy: 30,
  recollecting: 25,
  thinking: 20,
  sleepy: 15,
  bored: 10
};

