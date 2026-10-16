import { api } from '../api.ts';
import { setSpeechLang } from './speech.ts';
import type { CourseMeta, CourseOverview } from './types.ts';

/** The course that's open, shared by the course, lesson and review pages. */
export const course = $state<{
	id: string;
	meta: CourseMeta | null;
	chinese: boolean;
	pinyin: Record<string, string>;
}>({
	id: '',
	meta: null,
	chinese: false,
	pinyin: {}
});

/** Per-course choices, remembered in this browser only. */
export const prefs = $state({ pinyin: true, writing: true });

function prefsKey(id: string) {
	return `learn.${id}.prefs`;
}

function loadPrefs(id: string) {
	let saved: Partial<typeof prefs> = {};
	try {
		saved = JSON.parse(localStorage.getItem(prefsKey(id)) ?? '{}');
	} catch {
		// Storage can be blocked (private windows); the defaults are fine.
	}
	prefs.pinyin = saved.pinyin ?? true;
	prefs.writing = saved.writing ?? true;
}

export function savePrefs() {
	try {
		localStorage.setItem(prefsKey(course.id), JSON.stringify(prefs));
	} catch {
		// See loadPrefs.
	}
}

export function setCourse(overview: CourseOverview) {
	course.id = overview.id;
	course.meta = overview.meta;
	course.chinese = overview.meta.lang.startsWith('zh');
	course.pinyin = overview.pinyin;
	setSpeechLang(overview.meta.lang);
	loadPrefs(overview.id);
}

export async function loadCourse(id: string): Promise<CourseMeta> {
	if (course.id === id && course.meta) return course.meta;
	const overview = await api<CourseOverview>(`/learn/${id}/course`);
	setCourse(overview);
	return overview.meta;
}

/** Feedback shows "hanzi · pinyin" for Chinese; only the characters should be read aloud. */
export function spoken(expected: string): string {
	return expected.split(' · ')[0];
}

export type Segment = { text: string; reading?: string };

/** Split text into known words and characters with their pinyin, longest word first. */
export function annotate(text: string): Segment[] {
	const dict = course.pinyin;
	const longest = Math.max(1, ...Object.keys(dict).map((k) => k.length));
	const out: Segment[] = [];
	let i = 0;
	while (i < text.length) {
		let len = Math.min(longest, text.length - i);
		while (len > 0 && !(text.slice(i, i + len) in dict)) len--;
		if (len > 0) {
			const word = text.slice(i, i + len);
			out.push({ text: word, reading: dict[word] });
			i += len;
		} else {
			const last = out.at(-1);
			if (last && last.reading === undefined) last.text += text[i];
			else out.push({ text: text[i] });
			i++;
		}
	}
	return out;
}
