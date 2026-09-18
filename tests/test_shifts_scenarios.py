import copy
import pytest
from backend.domain import Settings, MODELS, validate_data, slot_stride
from backend.scenarios import SCENARIOS, scenario_data, two_shift_bells
from backend.scheduling import events, validate_schedule, capacity_issues, diagnose
from backend.solver import solve
from backend.exports import rows_for
from tests.test_api import client, seed
from tests.test_solver import small

def two_shifts():
    d=small(7);d['settings']['bells']=two_shift_bells();d['classes'][1]['shift']=2
    d['rooms']=d['rooms'][:1]
    return d

def test_two_shifts_accept_ten_bells_and_solve_share_resources():
    d=two_shifts();assert len(Settings(**d['settings']).bells)==10
    assert not validate_data(d)
    r=solve(d,seconds=1);assert r['status']=='complete',r
    assert not validate_schedule(d,r['lessons'])
    ev={e['id']:e for e in events(d)}
    for l in r['lessons']:
        shift=d['settings']['bells'][l['slot']%10]['shift']
        assert shift==(1 if ev[l['id']]['class_ids']==['c0'] else 2)
    rows=rows_for({'snapshot':d,'lessons':r['lessons'],'week':''},{})
    assert any('2 смена' in row[1] for row in rows)

def test_wrong_shift_and_total_teacher_load_are_rejected():
    d=two_shifts();r=solve(d,seconds=1)
    bad=copy.deepcopy(r['lessons']);l=next(l for l in bad if l['id'].startswith('p1'))
    l['slot']=(l['slot']//10)*10
    assert any('время недоступно' in e for e in validate_schedule(d,bad))
    d['teachers'][0].update(daily_hard=1,daily_soft=1)
    lessons=[{'id':'p0:0','slot':0,'parts':[{'teacher_id':'t0','room_id':'r0'}]}, {'id':'p1:0','slot':5,'parts':[{'teacher_id':'t0','room_id':'r0'}]}]
    assert any('дневная нагрузка' in e for e in validate_schedule(d,lessons,complete=False))

def test_breaks_checked_in_each_shift_and_legacy_stride():
    d=two_shifts()
    # Second shift has no long break even though the first one does.
    minute=810
    for b in d['settings']['bells'][5:]:
        b.update(start=f'{minute//60:02}:{minute%60:02}',end=f'{(minute+45)//60:02}:{(minute+45)%60:02}');minute+=50
    assert any('Смена 2: нужна большая перемена' in e for e in validate_data(d))
    assert slot_stride(small())==8

@pytest.mark.parametrize('key',[s[0] for s in SCENARIOS])
def test_scenario_has_valid_populated_reference_data_and_no_solution(key):
    d=scenario_data(key)
    assert not validate_data(d)
    for kind,model in MODELS.items():
        assert d[kind],kind
        for row in d[kind]:model(**row)
    assert 'lessons' not in d

def test_scenario_seed_changes_inputs():
    assert scenario_data('balanced',1)['plans']!=scenario_data('balanced',2)['plans']

def test_capacity_impossibility_is_not_reported_as_timeout():
    d=scenario_data('many_students');r=solve(d,seconds=2)
    assert r['status']=='infeasible'
    assert r['diagnostics'] and all('кабинета' in x['reason'] for x in r['diagnostics'])

def test_workspace_restore_preserves_school_and_versions(client):
    vid,_,_=seed(client)
    original=client.get('/api/data').json()
    r=client.post('/api/demo/workspace',json={'revision':original['revision'],'scenario':'two_shifts'});assert r.status_code==200,r.text
    current=client.get('/api/data').json();assert len(current['data']['settings']['bells'])==10
    assert client.get('/api/versions').json()==[]
    assert client.get('/api/versions/'+vid).status_code==404
    assert client.post('/api/demo/workspace',json={'revision':original['revision'],'scenario':'small'}).status_code==409
    # Save ten bells through the real settings route.
    settings=current['data']['settings']
    assert client.put('/api/settings',json={'revision':current['revision'],'settings':settings}).status_code==200
    r=client.post('/api/demo/workspace',json={'revision':current['revision']+1,'scenario':'few_rooms'});assert r.status_code==200
    revision=r.json()['revision']
    assert client.post('/api/demo/workspace',json={'revision':revision}).status_code==200
    assert client.get('/api/data').json()['data']==original['data']
    assert client.get('/api/versions').json()[0]['id']==vid
    assert client.post('/api/versions/'+vid+'/status',json={'status':'review'}).status_code==200

def test_settings_validation_is_russian_and_does_not_save(client):
    before=client.get('/api/data').json();settings=copy.deepcopy(before['data']['settings'])
    settings['bells']*=3
    r=client.put('/api/settings',json={'revision':before['revision'],'settings':settings})
    assert r.status_code==422
    message=r.json()['errors'][0]['message']
    assert 'Звонки' in message and 'не более 16' in message
    assert 'List should' not in message
    assert client.get('/api/data').json()==before

def test_teacher_shortage_has_proven_numeric_bound():
    issues=capacity_issues(scenario_data('few_teachers',50))
    teacher=next(x for x in issues if x['resource']=='teachers')
    assert (teacher['required'],teacher['capacity'],teacher['deficit'])==(104,60,44)

def test_no_capacity_deficit_does_not_claim_impossibility():
    d=small();assert capacity_issues(d)==[]
    result=diagnose(d,events(d))
    assert all('не доказывает невозможность' in r['reason'] for r in result)

def test_resource_capacity_counts_groups_and_calendar():
    d=small();d['teachers'][0]['maximum']=3
    assert next(x for x in capacity_issues(d) if x['resource']=='teachers')['capacity']==3
    d['teachers'][0]['availability']=[{'day':day,'slot':s,'value':'unavailable'} for day in range(5) for s in range(8)]
    assert next(x for x in capacity_issues(d) if x['resource']=='teachers')['capacity']==0
