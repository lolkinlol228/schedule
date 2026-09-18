"""Acceptance benchmark. Run: python -m scripts.benchmark"""
import json
import platform
import time
from pathlib import Path
from backend.demo import demo_data
from backend.solver import solve
from backend.scheduling import validate_schedule

def main():
    data=demo_data(True);started=time.monotonic();result=solve(data,seconds=10);wall=time.monotonic()-started
    errors=validate_schedule(data,result['lessons'])
    report={'machine':platform.platform(),'processor':platform.processor(),'python':platform.python_version(),'solver':result['solver_version'],
        'classes':len(data['classes']),'students':sum(c['size'] for c in data['classes']),'teachers':len(data['teachers']),'rooms':len(data['rooms']),
        'expected_lessons':sum(p['hours'] for p in data['plans']),'placed':len(result['lessons']),'status':result['status'],'wall_seconds':round(wall,3),
        'hard_violations':errors,'seed':42,'workers':8,'optimal':result['optimal']}
    Path('reports').mkdir(exist_ok=True);Path('reports/benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    assert result['status']=='complete' and not errors
    assert wall<=10,f'Benchmark exceeded 10 seconds: {wall:.3f}'

if __name__=='__main__':main()
