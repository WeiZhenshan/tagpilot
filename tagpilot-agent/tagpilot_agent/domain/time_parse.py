"""保守的时间词法解析：只规范化明确给出的滚动日窗口。"""
import re

def parse_time(text):
    match=re.search(r'(?:近|最近|过去)\s*(\d+)\s*天',text or '')
    if match:return {'calendar_mode':'ROLLING','time_anchor_type':'WINDOW','time_window_unit':'DAY','time_window_value':int(match.group(1))}
    return {}
