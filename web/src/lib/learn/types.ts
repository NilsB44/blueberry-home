export type Verdict = 'correct' | 'accent' | 'typo' | 'wrong';
export type CheckResult = { verdict: Verdict; correct: boolean; expected: string };

export type Exercise =
	| { type: 'choice'; prompt: string; options: string[]; speak: string | null }
	| { type: 'translate'; prompt: string; source: 'target' | 'en'; prompt_reading: string | null }
	| { type: 'word_bank'; prompt: string; tiles: string[] }
	| { type: 'match'; pairs: [string, string][] }
	| { type: 'listen'; text: string }
	| { type: 'gap'; prompt: string; hint: string | null; options: string[] }
	| { type: 'write'; char: string; reading: string; en: string };

export type Vocab = { word: string; en: string; reading: string | null; note: string | null };
export type Lesson = { id: string; title: string; intro: string | null; vocab: Vocab[]; exercises: Exercise[] };

export type Stats = { xp_today: number; daily_goal: number; streak: number; total_xp: number; due: number; words: number };

export type LessonSummary = { id: string; title: string; exercises: number; completed: boolean; best_mistakes: number | null };
export type Unit = { id: string; title: string; description: string; cefr: string; lessons: LessonSummary[] };
export type CourseMeta = { name: string; flag: string; lang: string; answer_hint: string | null };
export type CourseOverview = {
	id: string;
	meta: CourseMeta;
	units: Unit[];
	next_lesson: string | null;
	pinyin: Record<string, string>;
};

export type ReviewItem = { id: number; mode: 'to_en' | 'from_en' | 'listen'; prompt: string; reading: string | null };
