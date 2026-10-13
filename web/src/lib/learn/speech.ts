// Text-to-speech through the browser. Phones and desktops ship French voices, so this works
// with nothing installed on the Pi. Server-side voices (Piper) can replace it later.

let voices: SpeechSynthesisVoice[] = [];

function loadVoices() {
	if (typeof speechSynthesis === 'undefined') return;
	voices = speechSynthesis.getVoices();
}

if (typeof speechSynthesis !== 'undefined') {
	loadVoices();
	speechSynthesis.addEventListener?.('voiceschanged', loadVoices);
}

export function canSpeak(lang = 'fr-FR'): boolean {
	if (typeof speechSynthesis === 'undefined') return false;
	if (voices.length === 0) return true; // voices load lazily on some browsers; try anyway
	return voices.some((v) => v.lang.toLowerCase().startsWith(lang.slice(0, 2)));
}

export function speak(text: string, { lang = 'fr-FR', slow = false } = {}) {
	if (typeof speechSynthesis === 'undefined') return;
	speechSynthesis.cancel();
	const u = new SpeechSynthesisUtterance(text);
	u.lang = lang;
	u.rate = slow ? 0.6 : 0.95;
	const prefix = lang.slice(0, 2);
	const voice =
		voices.find((v) => v.lang === lang && v.localService) ??
		voices.find((v) => v.lang === lang) ??
		voices.find((v) => v.lang.toLowerCase().startsWith(prefix));
	if (voice) u.voice = voice;
	speechSynthesis.speak(u);
}
