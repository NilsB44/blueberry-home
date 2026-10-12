export type Verdict = 'correct' | 'accent' | 'typo' | 'wrong';
export type CheckResult = { verdict: Verdict; correct: boolean; expected: string };

export type Exercise =
	| { type: 'choice'; prompt: string; options: string[]; speak: string | null }
	| { type: 'translate'; prompt: string; source: 'fr' | 'en' }
	| { type: 'word_bank'; prompt: string; tiles: string[] }
	| { type: 'match'; pairs: [string, string][] }
	| { type: 'listen'; text: string }
	| { type: 'gap'; prompt: string; hint: string | null; options: string[] };

export type Vocab = { fr: string; en: string; note: string | null };
export type Lesson = { id: string; title: string; intro: string | null; vocab: Vocab[]; exercises: Exercise[] };

export type Stats = { xp_today: number; daily_goal: number; streak: number; total_xp: number; due: number; words: number };

export type LessonSummary = { id: string; title: string; exercises: number; completed: boolean; best_mistakes: number | null };
export type Unit = { id: string; title: string; description: string; cefr: string; lessons: LessonSummary[] };
export type CourseOverview = { id: string; units: Unit[]; next_lesson: string | null };

export type ReviewItem = { id: number; mode: 'fr_en' | 'en_fr' | 'listen'; prompt: string };

export const COURSE_NAMES: Record<string, { name: string; lang: string; flag: string }> = {
	french: { name: 'French', lang: 'fr-FR', flag: '🇫🇷' }
};
