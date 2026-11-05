"""Quick-add parser: due date read from anywhere in the text; ISO dates removed from the title."""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from profiles import parse_quick  # noqa: E402

T = date(2026, 10, 23)  # Friday


@pytest.mark.parametrize('text,name,due,course', [
    ('due fri #MAT104 light', 'light', date(2026, 10, 30), 'MAT104'),
    ('light due fri #MAT104', 'light', date(2026, 10, 30), 'MAT104'),
    ('Read ch 4 due fri #CSC4710', 'Read ch 4', date(2026, 10, 30), 'CSC4710'),
    ('lab by 10/30 writeup', 'lab writeup', date(2026, 10, 30), None),
    ('essay on tomorrow draft', 'essay draft', date(2026, 10, 24), None),
    ('due in 3 days problem set', 'problem set', date(2026, 10, 26), None),
    ('essay 2026-11-02 #ENG1', 'essay', date(2026, 11, 2), 'ENG1'),
    ('2026-11-02 essay', 'essay', date(2026, 11, 2), None),
    ('essay due 2026-11-02 final', 'essay final', date(2026, 11, 2), None),
    ('quiz tomorrow', 'quiz', date(2026, 10, 24), None),              # 709dd26: bare date at the end
    ('Read ch 4', 'Read ch 4', None, None),                            # no date -> nudge path
])
def test_due_anywhere(text, name, due, course):
    assert parse_quick(text, T) == (name, due, course)


@pytest.mark.parametrize('text', ['Monday notes', '1/2 chapter review', 'fridge cleanup', 'stand by me'])
def test_bare_words_mid_text_not_dates(text):
    assert parse_quick(text, T) == (text, None, None)


def test_invalid_iso_left_in_title():
    assert parse_quick('hw due 2026-13-40', T) == ('hw due 2026-13-40', None, None)


def test_iso_beats_word_date_and_word_date_stripped():
    assert parse_quick('due mon review 2026-11-09', T) == ('review', date(2026, 11, 9), None)


def test_iso_wins_and_losing_keyword_date_is_stripped():
    from datetime import date
    from profiles import parse_quick
    name, due, _ = parse_quick('due fri 2026-11-02 x', today=date(2026, 10, 23))
    assert due == date(2026, 11, 2) and name == 'x'
    name, due, _ = parse_quick('Essay 2026-11-02 by tomorrow', today=date(2026, 10, 23))
    assert due == date(2026, 11, 2) and name == 'Essay'
