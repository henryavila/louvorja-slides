from __future__ import annotations

import unittest

from louvorja_slides.layout import (
    LayoutConfig,
    LyricWord,
    SlidePlan,
    collapse_repeated_slides,
    plan_lyric_slides,
)


def words_from_text(
    text: str,
    *,
    start: float = 0.0,
    step: float = 0.5,
    gap_after: dict[int, float] | None = None,
) -> list[LyricWord]:
    gap_after = gap_after or {}
    result: list[LyricWord] = []
    cursor = start
    for index, token in enumerate(text.split()):
        end = cursor + step
        result.append(LyricWord(text=token, start=cursor, end=end))
        cursor = end + gap_after.get(index, 0.0)
    return result


class SlideLayoutRulesTest(unittest.TestCase):
    def test_short_complete_phrase_uses_one_line(self) -> None:
        slides = plan_lyric_slides(words_from_text("Fala comigo"))

        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0].lines, ("Fala comigo",))
        self.assertEqual(slides[0].aux_text, "")

    def test_two_short_sequential_phrases_stay_in_one_slide(self) -> None:
        words = words_from_text(
            "Toma Teu lugar de honra Queremos Tua Presenca aqui",
            gap_after={4: 0.2},
        )

        slides = plan_lyric_slides(words)

        self.assertEqual(len(slides), 1)
        self.assertEqual(
            slides[0].lines,
            ("Toma Teu lugar de honra", "Queremos Tua Presenca aqui"),
        )

    def test_one_line_config_never_creates_two_line_slides(self) -> None:
        config = LayoutConfig(max_lines_per_slide=1)
        words = words_from_text("Nao devemos parar nao devemos temer")

        slides = plan_lyric_slides(words, config=config)

        self.assertTrue(slides)
        self.assertTrue(all(len(slide.lines) == 1 for slide in slides))

    def test_line_break_does_not_end_on_weak_word(self) -> None:
        words = words_from_text("Toma Teu lugar de honra Queremos Tua Presenca aqui")

        slides = plan_lyric_slides(words)

        first_line = slides[0].lines[0]
        self.assertNotRegex(first_line.lower(), r"\b(de|do|da|em|que|e|nao)$")
        self.assertEqual(first_line, "Toma Teu lugar de honra")

    def test_allows_hard_limit_to_avoid_fast_slide_change(self) -> None:
        config = LayoutConfig(target_max_chars_per_line=20, hard_max_chars_per_line=34)
        words = words_from_text(
            "E tudo vai ficar bem tudo acaba bem No final no final",
            gap_after={4: 0.8},
        )

        slides = plan_lyric_slides(words, config=config)

        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0].lines, ("E tudo vai ficar bem", "tudo acaba bem No final no final"))

    def test_creates_new_slide_when_pause_is_long_enough(self) -> None:
        words = words_from_text(
            "E tudo vai ficar bem tudo acaba bem No final no final",
            gap_after={4: 4.0},
        )

        slides = plan_lyric_slides(words)

        self.assertEqual([slide.lines for slide in slides], [("E tudo vai ficar bem",), ("tudo acaba bem No final no final",)])

    def test_does_not_create_fast_one_line_slide_transition(self) -> None:
        words = words_from_text(
            "Nao devemos parar nao devemos temer",
            gap_after={2: 0.2},
        )

        slides = plan_lyric_slides(words)

        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0].lines, ("Nao devemos parar", "nao devemos temer"))

    def test_uses_auxiliary_text_only_as_overflow_fallback(self) -> None:
        words = words_from_text(
            "Nao devemos parar nao devemos temer porque o noivo vai chegar",
            gap_after={2: 0.8, 5: 0.8},
        )

        slides = plan_lyric_slides(words)

        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0].lines, ("Nao devemos parar", "nao devemos temer"))
        self.assertEqual(slides[0].aux_text, "porque o noivo vai chegar")

    def test_invalid_natural_split_falls_back_to_readable_two_line_break(self) -> None:
        config = LayoutConfig()
        words = words_from_text(
            "Eu quero ver tua gloria brilhando aqui Senhor amado",
            gap_after={6: 0.8},
        )

        slides = plan_lyric_slides(words, config=config)

        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0].aux_text, "")
        self.assertEqual(len(slides[0].lines), 2)
        self.assertTrue(
            all(len(line) <= config.hard_max_chars_per_line for line in slides[0].lines)
        )

    def test_repetition_does_not_generate_two_times_auxiliary_marker(self) -> None:
        words = words_from_text(
            "Fala comigo fala comigo Fala comigo fala comigo",
            gap_after={3: 0.2},
        )

        slides = plan_lyric_slides(words)

        self.assertNotIn("(2x)", [slide.aux_text for slide in slides])

    def test_consecutive_repeated_slides_are_collapsed_with_two_times_marker(self) -> None:
        slides = collapse_repeated_slides(
            [
                SlidePlan(lines=("Fala comigo",), start_seconds=1.0, end_seconds=2.0),
                SlidePlan(lines=("Fala comigo",), start_seconds=3.0, end_seconds=4.0),
            ]
        )

        self.assertEqual(
            slides,
            [
                SlidePlan(
                    lines=("Fala comigo",),
                    start_seconds=1.0,
                    end_seconds=4.0,
                    aux_text="(2x)",
                )
            ],
        )

    def test_consecutive_repeated_slides_are_collapsed_with_three_times_marker(self) -> None:
        slides = collapse_repeated_slides(
            [
                SlidePlan(lines=("Fala comigo",), start_seconds=1.0, end_seconds=2.0),
                SlidePlan(lines=("Fala comigo",), start_seconds=3.0, end_seconds=4.0),
                SlidePlan(lines=("Fala comigo",), start_seconds=5.0, end_seconds=6.0),
            ]
        )

        self.assertEqual(slides[0].aux_text, "(3x)")
        self.assertEqual(slides[0].start_seconds, 1.0)
        self.assertEqual(slides[0].end_seconds, 6.0)

    def test_consecutive_repeated_slides_are_collapsed_with_five_times_marker(self) -> None:
        slides = collapse_repeated_slides(
            [
                SlidePlan(lines=("Santo",), start_seconds=1.0, end_seconds=2.0),
                SlidePlan(lines=("Santo",), start_seconds=3.0, end_seconds=4.0),
                SlidePlan(lines=("Santo",), start_seconds=5.0, end_seconds=6.0),
                SlidePlan(lines=("Santo",), start_seconds=7.0, end_seconds=8.0),
                SlidePlan(lines=("Santo",), start_seconds=9.0, end_seconds=10.0),
            ]
        )

        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0].aux_text, "(5x)")

    def test_non_consecutive_repeated_slides_are_not_collapsed(self) -> None:
        slides = collapse_repeated_slides(
            [
                SlidePlan(lines=("Fala comigo",), start_seconds=1.0, end_seconds=2.0),
                SlidePlan(lines=("Outra frase",), start_seconds=3.0, end_seconds=4.0),
                SlidePlan(lines=("Fala comigo",), start_seconds=5.0, end_seconds=6.0),
            ]
        )

        self.assertEqual([slide.aux_text for slide in slides], ["", "", ""])
        self.assertEqual(len(slides), 3)

    def test_slide_with_existing_auxiliary_text_is_not_collapsed(self) -> None:
        slides = collapse_repeated_slides(
            [
                SlidePlan(
                    lines=("Nao devemos parar",),
                    start_seconds=1.0,
                    end_seconds=2.0,
                    aux_text="continua",
                ),
                SlidePlan(lines=("Nao devemos parar",), start_seconds=3.0, end_seconds=4.0),
            ]
        )

        self.assertEqual([slide.aux_text for slide in slides], ["continua", ""])

    def test_plan_lyric_slides_counts_repeated_phrases_split_by_real_pauses(self) -> None:
        words = words_from_text(
            "Fala comigo Fala comigo Fala comigo",
            gap_after={1: 4.0, 3: 4.0},
        )

        slides = plan_lyric_slides(words)

        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0].lines, ("Fala comigo",))
        self.assertEqual(slides[0].aux_text, "(3x)")

    def test_prefers_punctuation_for_line_break(self) -> None:
        words = words_from_text("E tudo vai ficar bem, tudo acaba bem, No final no final")

        slides = plan_lyric_slides(words)

        self.assertEqual(slides[0].lines[0], "E tudo vai ficar bem,")

    def test_empty_words_raise_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "no lyric words"):
            plan_lyric_slides([])

    def test_single_word_longer_than_hard_limit_does_not_crash(self) -> None:
        long_word = "Misericordiosissimamente"

        slides = plan_lyric_slides([LyricWord(text=long_word, start=0.0, end=1.0)])

        self.assertEqual(slides[0].lines, (long_word,))

    def test_rejects_missing_timestamps(self) -> None:
        with self.assertRaisesRegex(ValueError, "timestamp"):
            plan_lyric_slides([object()])


if __name__ == "__main__":
    unittest.main()
