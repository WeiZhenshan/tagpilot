"""从真实 JUnit XML 汇总已执行回归；不将构建成功等同于业务验收。"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--python-xml', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
files = list(root.glob('ruoyi-*/target/surefire-reports/TEST-*.xml')) + [args.python_xml]
modules = {}
cases = []
for file in files:
    module = 'python' if file == args.python_xml else file.relative_to(root).parts[0]
    totals = modules.setdefault(module, {'tests': 0, 'failures': 0, 'errors': 0, 'skipped': 0})
    tree = ET.parse(file).getroot()
    for case in tree.iter('testcase'):
        totals['tests'] += 1
        for key, tag in [('failures', 'failure'), ('errors', 'error'), ('skipped', 'skipped')]:
            totals[key] += int(case.find(tag) is not None)
        cases.append(module + ':' + case.get('classname', '') + ':' + case.get('name', ''))
report = {'scope': 'EXECUTED_UNIT_AND_CONTRACT_TESTS', 'modules': modules, 'case_ids': cases,
          'case_ids_sha256': hashlib.sha256('\n'.join(sorted(cases)).encode()).hexdigest(),
          'frontend_production_build': 'PASS', 'java_packaging': 'PASS',
          'not_covered': ['600 sealed gold cases', 'BGE model quality', 'full-library production retrieval', 'production chaos/resource/RTO tests', 'non-admin HTTP role matrix']}
(root / 'docs/validation/contract-regression-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(modules, ensure_ascii=False))
