from tagpilot_eval.judge import _slots_satisfied


def question(prompt, options, reason='MULTIPLE_PUBLISHED_DEFINITIONS'):
    return {'prompt': prompt, 'options': options, 'reason': reason}


def test_combined_scope_and_threshold_are_both_explicitly_asked():
    q = question('还有资产按哪种口径与阈值判定？',
                 ['当前时点AUM大于0元', '当前AUM月日均余额不低于1000元'])
    assert _slots_satisfied(['business_scope', 'threshold'], [q])


def test_window_numbers_are_not_threshold_evidence():
    q = question('阈值与时间范围采用哪种口径？', ['近7天', '近30天'])
    assert not _slots_satisfied(['threshold'], [q])
    assert _slots_satisfied(['time_scope'], [q])


def test_fixed_boundary_repeated_across_windows_is_not_a_threshold_choice():
    q = question('阈值与时间范围采用哪种口径？',
                 ['近7天登录天数=0天', '近30天登录天数=0天'])
    assert not _slots_satisfied(['threshold'], [q])


def test_numbers_in_another_question_do_not_fill_missing_threshold():
    qs = [question('资产阈值是多少？', []),
          question('使用哪种口径？', ['余额大于0元', '余额不低于1000元'])]
    assert not _slots_satisfied(['threshold'], qs)


def test_unknown_reason_and_date_boundaries_are_not_threshold_proof():
    q = question('阈值怎么选？', ['大于0元', '不低于1000元'], reason='UNKNOWN')
    assert not _slots_satisfied(['threshold'], [q])
    q = question('阈值与时间范围怎么选？', ['不早于2026年9月1日', '不晚于2026年9月28日'])
    assert not _slots_satisfied(['threshold'], [q])
