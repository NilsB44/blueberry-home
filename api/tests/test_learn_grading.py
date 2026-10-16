import pytest

from app.modules.learn.grading import grade, grade_chinese, normalize, pinyin_key


@pytest.mark.parametrize(
    ("answer", "accepted", "verdict"),
    [
        ("Je voudrais un café", ["Je voudrais un café, s'il vous plaît."], "wrong"),
        (
            "je voudrais un café s'il vous plaît",
            ["Je voudrais un café, s'il vous plaît."],
            "correct",
        ),
        (
            "  JE VOUDRAIS un café,s’il vous plaît !! ",
            ["Je voudrais un café, s'il vous plaît."],
            "correct",
        ),
        ("je voudrais un cafe", ["Je voudrais un café"], "accent"),
        ("ca va", ["Ça va"], "accent"),
        ("je voudrias un café", ["Je voudrais un café"], "typo"),
        ("dix sept", ["dix-sept"], "correct"),
        ("dixsept", ["dix-sept"], "wrong"),
        # Short words: gender and conjugation mistakes are real mistakes, not typos.
        ("je travaille dans un banque", ["Je travaille dans une banque."], "wrong"),
        ("je suit ingénieur", ["Je suis ingénieur."], "wrong"),
        ("", ["Merci"], "wrong"),
        ("Merci", ["Merci"], "correct"),
        ("j' aime le poker", ["J'aime le poker."], "correct"),
        ("coeur", ["cœur"], "accent"),
    ],
)
def test_grade_french(answer, accepted, verdict):
    assert grade(answer, accepted, "fr").verdict == verdict


@pytest.mark.parametrize(
    ("answer", "verdict"),
    [
        ("I'm from Sweden", "correct"),
        ("i am from sweden.", "correct"),
        ("I come from Sweden", "correct"),
        ("I'm from Swedn", "typo"),
        ("I am in Sweden", "wrong"),
    ],
)
def test_grade_english_contractions(answer, verdict):
    accepted = ["I come from Sweden.", "I am from Sweden."]
    assert grade(answer, accepted, "en").verdict == verdict


def test_grade_returns_matching_expected():
    result = grade(
        "ma collègue est suédoise", ["Mon collègue est suédois.", "Ma collègue est suédoise."]
    )
    assert result.verdict == "correct"
    assert result.expected == "Ma collègue est suédoise."


def test_normalize_apostrophes_and_hyphens():
    assert normalize("Qu’est-ce que c’est ?") == "qu'est ce que c'est"


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("nǐ hǎo", "ni3 hao3"),
        ("nǐ hǎo", "ni3hao3"),
        ("nǐhǎo", "NI3 HAO3"),
        ("lǜ chá", "lv4 cha2"),
        ("lǜ chá", "lu:4 cha2"),
        ("xièxie", "xie4 xie5"),
    ],
)
def test_pinyin_spellings_are_equal(a, b):
    assert pinyin_key(a) == pinyin_key(b)


@pytest.mark.parametrize(
    ("answer", "verdict"),
    [
        ("你好", "correct"),
        ("你 好！", "correct"),
        ("nǐ hǎo", "correct"),
        ("ni3 hao3", "correct"),
        ("ni hao", "accent"),
        ("ni2 hao3", "accent"),
        ("zai jian", "wrong"),
        ("再见", "wrong"),
        ("", "wrong"),
    ],
)
def test_grade_chinese(answer, verdict):
    result = grade_chinese(answer, ["你好"], ["nǐ hǎo"])
    assert result.verdict == verdict
    assert result.expected == "你好 · nǐ hǎo"
