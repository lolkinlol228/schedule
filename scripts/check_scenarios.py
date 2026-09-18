"""Exercise every demo dataset through the actual solver and independent validator."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.scenarios import SCENARIOS, scenario_data
from backend.solver import solve
from backend.scheduling import validate_schedule, events

results=[]
for key,title,*_ in SCENARIOS:
    data=scenario_data(key)
    week='2026-09-14' if key=='calendar' else ''
    result=solve(data,week=week,seconds=10)
    violations=validate_schedule(data,result['lessons'],week,complete=False)
    row={'scenario':key,'status':result['status'],'placed':len(result['lessons']),'total':len(events(data,week)),
         'seconds':result['elapsed'],'hard_violations':violations,'errors':result['errors']}
    results.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
    assert not violations and not result['errors'],row
Path('reports/scenarios.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
