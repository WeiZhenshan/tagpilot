from tagpilot_eval.l2 import _merge_multiturn

def test_invalid_final_turn_cannot_become_pass_from_empty_checks():
 final={'status':'RUN_INVALID','checks':{},'failures':['RUN_NOT_TERMINAL:FAILED']}
 first={'status':'PASS','checks':{'slots_asked':True}}
 result=_merge_multiturn(final,first,{})
 assert result['status']=='RUN_INVALID'
 assert result['checks']['final_turn_expectation'] is False

def test_failed_first_or_final_turn_is_not_pass():
 good={'status':'PASS','checks':{'tree_equal':True},'failures':[]}
 bad={'status':'FAIL','checks':{},'failures':['AGENT_TIMEOUT_OR_FAILED']}
 assert _merge_multiturn(good,bad,{})['status']=='FAIL'
 assert _merge_multiturn(bad,good,{})['status']=='FAIL'
 assert _merge_multiturn(good,good,{})['status']=='PASS'
