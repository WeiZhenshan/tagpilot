"""独立SQLite交叉验证：不调用oracle解释器来计算期望；不是Java/MySQL验收。"""
from pathlib import Path
import sqlite3
import pytest
from tagpilot_eval.io import read_jsonl, digest
from tagpilot_eval.sources import load_ddl, load_fixture

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'tagpilot-eval/data/calibration-v1'


@pytest.fixture(scope='module')
def db():
    ddl=load_ddl(ROOT/'sql/indiv_cust/01_create_L_INDVCST_LABEL.sql')
    rows=load_fixture(ROOT/'sql/indiv_cust/2000_cust_generate/06_insert_L_INDVCST_LABEL_2000.sql',ddl)
    conn=sqlite3.connect(':memory:')
    columns=','.join('"'+name+'" '+('NUMERIC' if spec['data_type'].startswith(('INT','DECIMAL','TINYINT')) else 'TEXT') for name,spec in ddl.items())
    conn.execute('CREATE TABLE fixture ('+columns+')')
    conn.executemany('INSERT INTO fixture VALUES ('+','.join('?' for _ in ddl)+')',[list(r.values()) for r in rows])
    yield conn
    conn.close()


def sql_expr(expr):
    kind=expr['kind']
    if kind=='TAG':return '"'+expr['field_name']+'"'
    if kind=='CONST':return str(float(expr['value']))
    args=[sql_expr(a) for a in expr['args']]
    if kind=='COUNT_POSITIVE':
        return '(CASE WHEN '+' OR '.join(a+' IS NULL' for a in args)+' THEN NULL ELSE '+' + '.join('(CASE WHEN '+a+'>0 THEN 1 ELSE 0 END)' for a in args)+' END)'
    op={'ADD':'+','SUB':'-','MUL':'*','DIV':'/'}[kind]
    return '('+args[0]+op+('NULLIF(1.0*'+args[1]+',0)' if kind=='DIV' else args[1])+')'


def sql_tree(tree,params):
    if tree['kind']=='SCOPE_ALL':return '1=1'
    if tree['kind']=='GROUP':return '('+(' '+tree['logic']+' ').join(sql_tree(c,params) for c in tree['children'])+')'
    left=sql_expr(tree['expression']);op=tree['operator'];values=tree['values']
    # CAST数字字面量，避免SQLite派生表达式与字符串参数之间的存储类比较。
    slot='CAST(? AS NUMERIC)' if tree['data_kind']=='NUMBER' else '?'
    if op in {'is_null','is_not_null'}:return left+(' IS NULL' if op=='is_null' else ' IS NOT NULL')
    params.extend(values)
    if op=='contains':return 'instr('+left+',?)>0'
    if op in {'in','not_in'}:return left+(' IN ' if op=='in' else ' NOT IN ')+'('+','.join(slot for _ in values)+')'
    if op=='between':return left+' BETWEEN '+slot+' AND '+slot
    return left+op+slot


GOLD=read_jsonl(DATA/'oracle-results.jsonl') if DATA.exists() else []
CASES={c['case_id']:c for c in read_jsonl(DATA/'cases.jsonl')} if DATA.exists() else {}


@pytest.mark.parametrize('gold',GOLD,ids=[g['case_id']+'-turn'+str(g['stage']) for g in GOLD])
def test_every_materialized_id_set_with_sqlite(db,gold):
    case=CASES[gold['case_id']]
    expected=case['expected'] if gold['stage']==0 else case['turns'][gold['stage']-1]['expected']
    params=[]
    where=sql_tree(expected['tree'],params)
    ids=[r[0] for r in db.execute('SELECT CUST_ID FROM fixture WHERE '+where+' ORDER BY CUST_ID',params)]
    assert ids==gold['ids']
    assert digest(ids)==gold['ids_sha256']
    assert len(ids)==gold['count']
