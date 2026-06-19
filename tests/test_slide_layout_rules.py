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

    def test_source_phrase_lines_are_not_merged_past_slide_line_limit(self) -> None:
        words = [
            LyricWord("Aaa", 0.0, 0.4, line_index=0),
            LyricWord("bbb", 0.4, 0.8, line_index=0),
            LyricWord("Ccc", 0.8, 1.2, line_index=1),
            LyricWord("ddd", 1.2, 1.6, line_index=1),
            LyricWord("Eee", 1.6, 2.0, line_index=2),
            LyricWord("fff", 2.0, 2.4, line_index=2),
        ]

        slides = plan_lyric_slides(words)

        self.assertEqual(
            [slide.lines for slide in slides],
            [("Aaa bbb", "Ccc ddd"), ("Eee fff",)],
        )

    def test_long_single_source_phrase_can_wrap_inside_slide(self) -> None:
        words = [
            LyricWord("E", 0.0, 0.2, line_index=0),
            LyricWord("ao", 0.2, 0.4, line_index=0),
            LyricWord("olhar", 0.4, 0.8, line_index=0),
            LyricWord("pra", 0.8, 1.0, line_index=0),
            LyricWord("cruz", 1.0, 1.3, line_index=0),
            LyricWord("eu", 1.3, 1.5, line_index=0),
            LyricWord("entendo", 1.5, 2.0, line_index=0),
            LyricWord("amor", 2.0, 2.4, line_index=0),
        ]

        slides = plan_lyric_slides(words)

        self.assertEqual(slides[0].lines, ("E ao olhar pra cruz", "eu entendo amor"))

    def test_long_timestamp_run_without_pauses_uses_bounded_layout_search(self) -> None:
        words = words_from_text(" ".join(f"palavra{i}" for i in range(120)), step=0.2)

        slides = plan_lyric_slides(words)

        self.assertGreater(len(slides), 1)
        self.assertTrue(all(slide.lines for slide in slides))

    def test_line_break_does_not_end_on_weak_word(self) -> None:
        words = words_from_text("Toma Teu lugar de honra Queremos Tua Presenca aqui")

        slides = plan_lyric_slides(words)

        first_line = slides[0].lines[0]
        self.assertNotRegex(first_line.lower(), r"\b(de|do|da|em|que|e|nao)$")
        self.assertEqual(first_line, "Toma Teu lugar de honra")

    def test_duration_fallback_does_not_end_slide_on_weak_word(self) -> None:
        words = words_from_text(
            "Nossa missão é levantar o Santo nome do Senhor O Santo nome do Senhor Eu sou Calebe",
            step=0.8,
        )

        slides = plan_lyric_slides(words)

        for slide in slides[:-1]:
            last_line = slide.lines[-1]
            self.assertNotRegex(last_line.lower(), r"\b(o|a|de|do|da|em|que|e|nao)$")

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

        self.assertEqual(
            [slide.lines for slide in slides],
            [("E tudo vai ficar bem",), ("tudo acaba bem", "No final no final")],
        )

    def test_strong_boundary_region_with_many_source_lines_is_split(self) -> None:
        line_texts = [
            "alfa beta gama delta",
            "bravo canto claro dia",
            "eco firme gloria hoje",
            "justo lume monte novo",
            "povo quieto rumo santo",
            "terra unica vida zelo",
        ]
        words: list[LyricWord] = []
        cursor = 0.0
        for line_index, line_text in enumerate(line_texts):
            for token in line_text.split():
                start = cursor
                end = start + 0.3
                words.append(
                    LyricWord(token, start, end, line_index=line_index)
                )
                cursor = end + 0.1
        cursor += 4.0
        words.append(LyricWord("final", cursor, cursor + 0.3, line_index=len(line_texts)))

        slides = plan_lyric_slides(words)

        self.assertGreater(len(slides), 2)
        self.assertEqual(slides[-1].lines, ("final",))
        self.assertTrue(
            all(
                len(line) <= LayoutConfig().hard_max_chars_per_line
                for slide in slides
                for line in slide.lines
            )
        )

    def test_pause_delimited_phrase_is_not_split_between_slides(self) -> None:
        words = words_from_text(
            (
                "Santo es Senhor da minha vida agora e para sempre tua luz me guia "
                "Tudo entrego no altar do meu coracao"
            ),
            gap_after={1: 0.8, 13: 0.8},
        )

        slides = plan_lyric_slides(words)

        self.assertEqual(
            [slide.lines for slide in slides],
            [
                ("Santo es",),
                ("Senhor da minha vida agora", "e para sempre tua luz me guia"),
                ("Tudo entrego no altar", "do meu coracao"),
            ],
        )

    def test_auxiliary_text_starts_at_phrase_boundary(self) -> None:
        words = words_from_text(
            "Santo es Senhor da minha vida agora e para sempre tua luz me guia Tudo entrego",
            gap_after={1: 0.8, 13: 0.8},
        )

        slides = plan_lyric_slides(words)

        self.assertEqual(
            slides,
            [
                SlidePlan(lines=("Santo es",), start_seconds=0.0, end_seconds=1.0),
                SlidePlan(
                    lines=("Senhor da minha vida agora", "e para sempre tua luz me guia"),
                    start_seconds=1.8,
                    end_seconds=9.6,
                    aux_text="Tudo entrego",
                ),
            ],
        )

    def test_overlong_pause_delimited_phrase_splits_before_hard_limit(self) -> None:
        long_phrase = (
            "Senhor da minha vida agora e para sempre tua luz me guia "
            "pelos vales e montanhas ate o fim"
        )
        words = words_from_text(
            f"Gloria a ti {long_phrase} Tudo entrego",
            gap_after={2: 0.8, 21: 0.8},
        )

        slides = plan_lyric_slides(words)

        self.assertEqual(slides[0].lines, ("Gloria a ti",))
        self.assertGreater(len(slides), 2)
        self.assertTrue(
            all(
                len(line) <= LayoutConfig().hard_max_chars_per_line
                for slide in slides
                for line in slide.lines
            )
        )
        self.assertIn("Tudo entrego", " ".join(" ".join(slide.lines) for slide in slides))

    def test_does_not_create_fast_one_line_slide_transition(self) -> None:
        words = words_from_text(
            "Nao devemos parar nao devemos temer",
            gap_after={2: 0.2},
        )

        slides = plan_lyric_slides(words)

        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0].lines, ("Nao devemos parar", "nao devemos temer"))

    def test_short_auxiliary_text_can_remain_overflow_fallback(self) -> None:
        words = words_from_text(
            "Nao devemos parar nao devemos temer pela tua misericordia",
            gap_after={2: 0.8, 5: 0.8},
        )

        slides = plan_lyric_slides(words)

        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0].lines, ("Nao devemos parar", "nao devemos temer"))
        self.assertEqual(slides[0].aux_text, "pela tua misericordia")

    def test_long_auxiliary_text_becomes_own_slide(self) -> None:
        words = words_from_text(
            "Nao devemos parar nao devemos temer porque o noivo vai chegar",
            gap_after={2: 0.8, 5: 0.8},
        )

        slides = plan_lyric_slides(words)

        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0].aux_text, "")
        self.assertEqual(slides[0].lines, ("Nao devemos parar nao devemos", "temer porque o noivo vai chegar"))

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

    def test_repeated_slides_collapse_with_case_difference(self) -> None:
        slides = collapse_repeated_slides(
            [
                SlidePlan(
                    lines=("voce vai se", "sentir feliz."),
                    start_seconds=1.0,
                    end_seconds=4.0,
                ),
                SlidePlan(
                    lines=("Voce vai se", "sentir feliz."),
                    start_seconds=4.0,
                    end_seconds=7.0,
                ),
            ]
        )

        self.assertEqual(
            slides,
            [
                SlidePlan(
                    lines=("voce vai se", "sentir feliz."),
                    start_seconds=1.0,
                    end_seconds=7.0,
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
