from django.test import TestCase
from .report_engine import (
    _normalize_item_name,
    _default_segments,
    _parse_range_from_label,
    _extract_score_segments_by_item,
    _extract_score_weights,
    _match_score_weights,
    _normalize_scores_to_hundred,
    _match_score_column,
    _analyze_grades,
    SCORE_BUCKETS,
)


class NormalizeItemNameTests(TestCase):
    def test_strips_parentheses(self):
        self.assertEqual(_normalize_item_name('课堂表现（30%）'), '课堂表现')
        self.assertEqual(_normalize_item_name('作业(50%)'), '作业')

    def test_strips_suffixes(self):
        self.assertEqual(_normalize_item_name('课堂表现成绩'), '课堂表现')
        self.assertEqual(_normalize_item_name('作业得分'), '作业')
        self.assertEqual(_normalize_item_name('实验评分'), '实验')

    def test_strips_whitespace(self):
        self.assertEqual(_normalize_item_name('  课堂表现  '), '课堂表现')


class ParseRangeFromLabelTests(TestCase):
    def test_nn_nn_pattern(self):
        self.assertEqual(_parse_range_from_label('优秀（90-100分）'), (90.0, 101.0))
        self.assertEqual(_parse_range_from_label('良好（80-89分）'), (80.0, 90.0))

    def test_less_than_pattern(self):
        self.assertEqual(_parse_range_from_label('<60（不及格）'), (0.0, 60.0))

    def test_greater_than_pattern(self):
        self.assertEqual(_parse_range_from_label('>90'), (90.0, 101.0))

    def test_no_range(self):
        self.assertIsNone(_parse_range_from_label('考核项目'))


class ExtractScoreSegmentsByItemTests(TestCase):
    def test_single_table_single_item(self):
        blocks = [
            {
                'type': 'table',
                'num_cols': 6,
                'grid': [
                    [
                        {'text': '考核项目', 'colspan': 1, 'rowspan': 1},
                        {'text': '优秀（90-100分）', 'colspan': 1, 'rowspan': 1},
                        {'text': '良好（80-89分）', 'colspan': 1, 'rowspan': 1},
                        {'text': '中等（70-79分）', 'colspan': 1, 'rowspan': 1},
                        {'text': '合格（60-69分）', 'colspan': 1, 'rowspan': 1},
                        {'text': '不合格（0-59分）', 'colspan': 1, 'rowspan': 1},
                    ],
                    [
                        {'text': '课堂表现', 'colspan': 1, 'rowspan': 1},
                        None, None, None, None, None,
                    ],
                ],
            },
        ]
        result = _extract_score_segments_by_item(blocks)
        self.assertIsNotNone(result)
        self.assertIn('课堂表现', result)
        self.assertEqual(len(result['课堂表现']), 5)
        labels = [s['label'] for s in result['课堂表现']]
        self.assertIn('优秀（90-100分）', labels)

    def test_multiple_items_in_one_table(self):
        blocks = [
            {
                'type': 'table',
                'num_cols': 6,
                'grid': [
                    [
                        {'text': '考核项目', 'colspan': 1, 'rowspan': 1},
                        {'text': 'A（90-100分）', 'colspan': 1, 'rowspan': 1},
                        {'text': 'B（80-89分）', 'colspan': 1, 'rowspan': 1},
                        {'text': 'C（70-79分）', 'colspan': 1, 'rowspan': 1},
                        {'text': 'D（60-69分）', 'colspan': 1, 'rowspan': 1},
                        {'text': 'F（0-59分）', 'colspan': 1, 'rowspan': 1},
                    ],
                    [
                        {'text': '课堂表现', 'colspan': 1, 'rowspan': 1},
                        None, None, None, None, None,
                    ],
                    [
                        {'text': '作业', 'colspan': 1, 'rowspan': 1},
                        None, None, None, None, None,
                    ],
                ],
            },
        ]
        result = _extract_score_segments_by_item(blocks)
        self.assertIsNotNone(result)
        self.assertIn('课堂表现', result)
        self.assertIn('作业', result)
        self.assertEqual(result['课堂表现'][0]['label'], 'A（90-100分）')
        self.assertEqual(result['作业'][0]['label'], 'A（90-100分）')

    def test_multiple_tables_different_labels(self):
        blocks = [
            {
                'type': 'table',
                'num_cols': 3,
                'grid': [
                    [
                        {'text': '考核项目', 'colspan': 1, 'rowspan': 1},
                        {'text': '优秀（90-100分）', 'colspan': 1, 'rowspan': 1},
                        {'text': '<60（不及格）', 'colspan': 1, 'rowspan': 1},
                    ],
                    [
                        {'text': '课堂表现', 'colspan': 1, 'rowspan': 1},
                        None, None,
                    ],
                ],
            },
            {
                'type': 'table',
                'num_cols': 3,
                'grid': [
                    [
                        {'text': '考核项目', 'colspan': 1, 'rowspan': 1},
                        {'text': 'A（90-100分）', 'colspan': 1, 'rowspan': 1},
                        {'text': 'F（0-59分）', 'colspan': 1, 'rowspan': 1},
                    ],
                    [
                        {'text': '作业', 'colspan': 1, 'rowspan': 1},
                        None, None,
                    ],
                ],
            },
        ]
        result = _extract_score_segments_by_item(blocks)
        self.assertIsNotNone(result)
        self.assertEqual(result['课堂表现'][0]['label'], '优秀（90-100分）')
        self.assertEqual(result['作业'][0]['label'], 'A（90-100分）')

    def test_no_table_blocks(self):
        blocks = [{'type': 'paragraph', 'text': 'no tables here'}]
        self.assertIsNone(_extract_score_segments_by_item(blocks))

    def test_empty_list(self):
        self.assertIsNone(_extract_score_segments_by_item([]))

    def test_none_input(self):
        self.assertIsNone(_extract_score_segments_by_item(None))

    def test_table_without_enough_segments(self):
        blocks = [
            {
                'type': 'table',
                'num_cols': 2,
                'grid': [
                    [
                        {'text': '考核项目', 'colspan': 1, 'rowspan': 1},
                        {'text': '描述', 'colspan': 1, 'rowspan': 1},
                    ],
                ],
            },
        ]
        result = _extract_score_segments_by_item(blocks)
        self.assertIsNone(result)

    def test_header_without_item_column_label(self):
        """Header row has no '考核项目' etc. — all columns treated as segments."""
        blocks = [
            {
                'type': 'table',
                'num_cols': 5,
                'grid': [
                    [
                        {'text': '优秀（90-100分）', 'colspan': 1, 'rowspan': 1},
                        {'text': '良好（80-89分）', 'colspan': 1, 'rowspan': 1},
                        {'text': '中等（70-79分）', 'colspan': 1, 'rowspan': 1},
                        {'text': '合格（60-69分）', 'colspan': 1, 'rowspan': 1},
                        {'text': '不合格（0-59分）', 'colspan': 1, 'rowspan': 1},
                    ],
                    [
                        {'text': '课堂表现', 'colspan': 1, 'rowspan': 1},
                        None, None, None, None,
                    ],
                ],
            },
        ]
        result = _extract_score_segments_by_item(blocks)
        self.assertIsNotNone(result)
        self.assertIn('课堂表现', result)
        # All 5 columns should be recognized as segments
        self.assertEqual(len(result['课堂表现']), 5)
        labels = [s['label'] for s in result['课堂表现']]
        self.assertIn('优秀（90-100分）', labels)


class MatchScoreColumnTests(TestCase):
    def setUp(self):
        self.item_map = {
            '课堂表现': [
                {'label': '优秀（90-100分）', 'lo': 90, 'hi': 101},
                {'label': '合格（60-69分）', 'lo': 60, 'hi': 70},
            ],
            '作业': [
                {'label': 'A（90-100分）', 'lo': 90, 'hi': 101},
                {'label': 'F（0-59分）', 'lo': 0, 'hi': 60},
            ],
        }

    def test_exact_match(self):
        result = _match_score_column('课堂表现', self.item_map)
        self.assertEqual(result[0]['label'], '优秀（90-100分）')

    def test_normalized_match(self):
        result = _match_score_column('课堂表现成绩', self.item_map)
        self.assertEqual(result[0]['label'], '优秀（90-100分）')

    def test_parentheses_stripped_match(self):
        result = _match_score_column('课堂表现（30%）', self.item_map)
        self.assertEqual(result[0]['label'], '优秀（90-100分）')

    def test_substring_match(self):
        result = _match_score_column('平时作业', self.item_map)
        self.assertEqual(result[0]['label'], 'A（90-100分）')

    def test_no_match(self):
        result = _match_score_column('总评', self.item_map)
        self.assertIsNone(result)


class AnalyzeGradesTests(TestCase):
    def setUp(self):
        self.headers = ['学号', '姓名', '课堂表现', '作业']
        self.rows = [
            {'学号': '001', '姓名': '张三', '课堂表现': 85, '作业': 92},
            {'学号': '002', '姓名': '李四', '课堂表现': 72, '作业': 88},
            {'学号': '003', '姓名': '王五', '课堂表现': 95, '作业': 65},
        ]

    def test_per_column_segments(self):
        segments_by_column = {
            '课堂表现': [
                {'label': '优秀（90-100）', 'lo': 90, 'hi': 101},
                {'label': '良好（80-89）', 'lo': 80, 'hi': 90},
                {'label': '其他（0-80）', 'lo': 0, 'hi': 80},
            ],
            '作业': [
                {'label': 'A（90-100）', 'lo': 90, 'hi': 101},
                {'label': 'B（80-89）', 'lo': 80, 'hi': 90},
                {'label': 'C（0-80）', 'lo': 0, 'hi': 80},
            ],
        }
        result = _analyze_grades(self.headers, self.rows, segments_by_column=segments_by_column)
        self.assertIn('课堂表现', result)
        self.assertIn('作业', result)
        # 课堂表现 uses its own labels
        dist_labels = list(result['课堂表现']['distribution'].keys())
        self.assertIn('优秀（90-100）', dist_labels)
        self.assertIn('良好（80-89）', dist_labels)
        # 作业 uses its own labels
        dist_labels = list(result['作业']['distribution'].keys())
        self.assertIn('A（90-100）', dist_labels)
        self.assertIn('B（80-89）', dist_labels)

    def test_fallback_segments_for_unmatched(self):
        fallback = [
            {'label': '优秀（90-100）', 'lo': 90, 'hi': 101},
            {'label': '不及格（0-60）', 'lo': 0, 'hi': 60},
        ]
        result = _analyze_grades(
            self.headers, self.rows,
            segments_by_column={'课堂表现': fallback},
            fallback_segments=None,
        )
        # 作业 not in segments_by_column → uses SCORE_BUCKETS default
        self.assertIn('作业', result)

    def test_full_default_fallback(self):
        result = _analyze_grades(self.headers, self.rows)
        self.assertIn('课堂表现', result)
        self.assertIn('作业', result)
        # Should use SCORE_BUCKETS labels
        dist = result['课堂表现']['distribution']
        for _, label, _, _ in SCORE_BUCKETS:
            self.assertIn(label, dist, f'Expected "{label}" in distribution')


class ExtractScoreWeightsTests(TestCase):
    def test_single_weight_table(self):
        blocks = [
            {
                'type': 'table',
                'num_cols': 7,
                'grid': [
                    [
                        {'text': '序号', 'colspan': 1, 'rowspan': 2},
                        {'text': '课程目标', 'colspan': 1, 'rowspan': 2},
                        {'text': '评价依据及成绩比例(%)', 'colspan': 4, 'rowspan': 1},
                        None, None, None,
                        {'text': '成绩比例(%)', 'colspan': 1, 'rowspan': 1},
                    ],
                    [
                        None, None,
                        {'text': '课堂表现 10%', 'colspan': 1, 'rowspan': 1},
                        {'text': '课后作业 20%', 'colspan': 1, 'rowspan': 1},
                        {'text': '上机实验30%', 'colspan': 1, 'rowspan': 1},
                        {'text': '期末考试 40%', 'colspan': 1, 'rowspan': 1},
                        {'text': '', 'colspan': 1, 'rowspan': 1},
                    ],
                ],
            },
        ]
        result = _extract_score_weights(blocks)
        self.assertIsNotNone(result)
        self.assertEqual(result['课堂表现'], 10.0)
        self.assertEqual(result['课后作业'], 20.0)
        self.assertEqual(result['上机实验'], 30.0)
        self.assertEqual(result['期末考试'], 40.0)

    def test_no_weight_table(self):
        blocks = [{'type': 'paragraph', 'text': 'no tables'}]
        self.assertIsNone(_extract_score_weights(blocks))

    def test_none_input(self):
        self.assertIsNone(_extract_score_weights(None))


class MatchScoreWeightsTests(TestCase):
    def setUp(self):
        self.weights = {'课堂表现': 10.0, '课后作业': 20.0, '上机实验': 30.0}

    def test_exact_match(self):
        result = _match_score_weights(['课堂表现', '课后作业', '总评'], self.weights)
        self.assertEqual(result['课堂表现'], 10.0)
        self.assertEqual(result['课后作业'], 20.0)

    def test_normalized_match(self):
        result = _match_score_weights(['课堂表现成绩', '平时课后作业'], self.weights)
        self.assertEqual(result['课堂表现成绩'], 10.0)
        self.assertEqual(result['平时课后作业'], 20.0)

    def test_excludes_total_score(self):
        result = _match_score_weights(['课堂表现', '总评', '总分'], self.weights)
        self.assertIn('课堂表现', result)
        self.assertNotIn('总评', result)
        self.assertNotIn('总分', result)

    def test_no_match(self):
        result = _match_score_weights(['未知列', '总评'], self.weights)
        self.assertEqual(result, {})


class NormalizeScoresToHundredTests(TestCase):
    def test_already_hundred_scale(self):
        scores = [85.0, 92.0, 78.0, 65.0, 90.0]
        normalized, is_weighted = _normalize_scores_to_hundred(scores, 10.0)
        self.assertFalse(is_weighted)
        self.assertEqual(normalized, scores)

    def test_weighted_scores_converted(self):
        scores = [8.5, 9.2, 7.8, 6.5, 9.0]
        normalized, is_weighted = _normalize_scores_to_hundred(scores, 10.0)
        self.assertTrue(is_weighted)
        self.assertAlmostEqual(normalized[0], 85.0)
        self.assertAlmostEqual(normalized[1], 92.0)
        self.assertAlmostEqual(normalized[2], 78.0)

    def test_boundary_detection(self):
        scores = [10.0, 9.0, 8.0]
        normalized, is_weighted = _normalize_scores_to_hundred(scores, 10.0)
        self.assertTrue(is_weighted)

    def test_empty_scores(self):
        normalized, is_weighted = _normalize_scores_to_hundred([], 10.0)
        self.assertEqual(normalized, [])
        self.assertFalse(is_weighted)


class AnalyzeGradesWithWeightsTests(TestCase):
    def setUp(self):
        self.headers = ['学号', '姓名', '课堂表现', '课后作业', '总评']
        self.rows = [
            {'学号': '001', '姓名': '张三', '课堂表现': 8.5, '课后作业': 85, '总评': 88},
            {'学号': '002', '姓名': '李四', '课堂表现': 9.2, '课后作业': 90, '总评': 92},
            {'学号': '003', '姓名': '王五', '课堂表现': 7.0, '课后作业': 78, '总评': 76},
        ]
        self.column_weights = {'课堂表现': 10.0, '课后作业': 20.0}

    def test_weighted_column_normalized(self):
        result = _analyze_grades(
            self.headers, self.rows,
            column_weights=self.column_weights,
        )
        self.assertIn('课堂表现', result)
        self.assertTrue(result['课堂表现']['is_weighted'])
        self.assertAlmostEqual(result['课堂表现']['avg'], 82.33, places=1)

    def test_hundred_scale_column_not_normalized(self):
        result = _analyze_grades(
            self.headers, self.rows,
            column_weights=self.column_weights,
        )
        self.assertIn('课后作业', result)
        self.assertFalse(result['课后作业']['is_weighted'])

    def test_total_score_excluded_from_weights(self):
        result = _analyze_grades(
            self.headers, self.rows,
            column_weights=self.column_weights,
        )
        self.assertIn('总评', result)
        self.assertIsNone(result['总评']['weight_pct'])


class DefaultSegmentsTests(TestCase):
    def test_returns_dict_format(self):
        segs = _default_segments()
        self.assertEqual(len(segs), len(SCORE_BUCKETS))
        for seg in segs:
            self.assertIn('label', seg)
            self.assertIn('lo', seg)
            self.assertIn('hi', seg)
