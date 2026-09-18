from backend.recommendations import proposals, coverage
from backend.solver import solve
from backend.scheduling import validate_schedule
from .test_solver import small

def test_alternative_teacher_proposal_is_verified_and_does_not_mutate_data():
    d=small();d['teachers'][0]['availability']=[{'day':day,'slot':slot,'value':'unavailable'} for day in range(5) for slot in range(8)]
    candidate=next(proposals(d));r=solve(candidate['data'],seconds=1)
    assert r['status']=='complete'
    assert coverage(candidate['data'],r['lessons'])==4
    assert not validate_schedule(candidate['data'],r['lessons'])
    assert all(p['teacher_ids']==['t0'] for p in d['plans'])

def test_merge_proposal_requires_matching_topics():
    d=small();assert any('Объединить' in p['title'] for p in proposals(d))
    d['plans'][1]['topic']=9
    assert not any('Объединить' in p['title'] for p in proposals(d))
