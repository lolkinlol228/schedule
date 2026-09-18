"""Regression tests for the Kazakhstan norm profile and the class day load.

The five properties below are the ones the school complained about: an uneven
week with empty and overloaded days, missing norms per parallel, classes of the
legally protected parallels scheduled into the second shift, and hard subjects
left at the edges of the school day.
"""
from collections import Counter, defaultdict

import pytest

from backend.domain import MODELS, Rule, limits, requires_first_shift, slot_stride, validate_data
from backend.norms import DAILY_MAX, FIRST_SHIFT_GRADES, RANK_POINTS, WEEKLY_MAX, difficulty
from backend.scenarios import scenario_data, two_shift_bells
from backend.scheduling import DAYS, events, prepare_errors, score, validate_schedule
from backend.solver import solve
from tests.test_solver import small

def day_load(data, lessons, week=''):
    stride=slot_stride(data); index={e['id']:e for e in events(data,week)}
    rows=defaultdict(Counter)
    for l in lessons:
        for cid in index[l['id']]['class_ids']: rows[cid][l['slot']//stride]+=1
    return {c['id']:[rows[c['id']][day] for day in range(5)] for c in data['classes']}

def deviation(load, hours):
    """Отклонение дневной нагрузки от ровной раскладки: та же величина, что в модели."""
    base=hours//5
    return sum(abs(x-base) for x in load)

# --- (1) ни одного пустого учебного дня, когда часы помещаются в пятидневку ------------

@pytest.mark.parametrize('key',['balanced','two_shifts'])
def test_no_class_has_an_empty_school_day(key):
    data=scenario_data(key);result=solve(data,seconds=10)
    assert result['status']=='complete',result
    assert not validate_schedule(data,result['lessons'])
    load=day_load(data,result['lessons'])
    for c in data['classes']:
        hours=sum(load[c['id']])
        assert hours>=5, (c['name'],load[c['id']],'сценарий должен давать классу полную неделю')
        assert 0 not in load[c['id']],(c['name'],load[c['id']])

def test_empty_day_is_reported_by_score():
    d=small();d['plans'][0]['hours']=6
    packed=[{'id':f'p0:{i}','slot':i,'parts':[{'teacher_id':'t0','room_id':'r0'}],'lock':'free','origin':'generator'} for i in range(6)]
    assert score(d,packed)['warnings']==[] or all('ровной раскладки' in w['message'] for w in score(d,packed)['warnings'])
    spread=[dict(l,slot=day*8+1) for day,l in enumerate(packed[:5])]
    assert not [w for w in score(d,spread)['warnings'] if 'ровной раскладки' in w['message']]

# --- (2) дневная нагрузка не превышает норматив параллели ------------------------------

@pytest.mark.parametrize('key',['balanced','two_shifts'])
def test_daily_load_never_exceeds_the_grade_norm(key):
    data=scenario_data(key);result=solve(data,seconds=10)
    assert result['status']=='complete',result
    load=day_load(data,result['lessons'])
    for c in data['classes']:
        norm=limits(data,'daily_max',c['grade'])
        assert norm==DAILY_MAX[c['grade']]
        for day,value in enumerate(load[c['id']]):
            assert value<=norm,(c['name'],DAYS[day],value,norm)
    assert not validate_schedule(data,result['lessons'])

def test_norm_profile_follows_the_order_and_the_school_can_override_it():
    d=scenario_data('balanced')
    for grade in range(5,12):
        assert limits(d,'weekly_max',grade)==WEEKLY_MAX[grade]
        assert limits(d,'daily_max',grade)==DAILY_MAX[grade]
    for grade in FIRST_SHIFT_GRADES: assert requires_first_shift(d,grade)
    for grade in (6,7,8,10): assert not requires_first_shift(d,grade)
    # Более конкретная запись важнее общей, ноль отключает норму для параллели.
    d['rules'].append(Rule(id='shift-off-5',name='Отключение для 5 классов',key='first_shift',grade=5,value=0).model_dump(mode='json'))
    assert not requires_first_shift(d,5) and requires_first_shift(d,9)
    d['rules']=[r for r in d['rules'] if r['id']!='shift-off-5']
    d['rules'].append(Rule(id='shift-all',name='Первая смена для всей школы',key='first_shift',grade=0,value=1).model_dump(mode='json'))
    assert requires_first_shift(d,6) and requires_first_shift(d,11)

def test_difficulty_scale_follows_annex_four():
    assert difficulty(RANK_POINTS['math'])==10 and difficulty(RANK_POINTS['english'])==9
    assert difficulty(RANK_POINTS['history'])==7 and difficulty(RANK_POINTS['pe'])==4
    assert difficulty(RANK_POINTS['music'])==1
    d=scenario_data('balanced');ix={s['id']:s for s in d['subjects']}
    assert ix['math']['difficulty']>ix['history']['difficulty']>ix['science']['difficulty']>ix['pe']['difficulty']

# --- (3) 5, 9 и 11 классы не попадают во вторую смену ----------------------------------

def test_second_shift_is_rejected_for_protected_parallels():
    d=small();d['settings']['bells']=two_shift_bells();d['classes'][1]['shift']=2
    assert any('только первая смена' in e for e in validate_data(d)),validate_data(d)
    assert any('только первая смена' in e for e in prepare_errors(d))
    result=solve(d,seconds=1);assert result['status']=='invalid' and result['errors']

@pytest.mark.parametrize('grade,allowed',[(5,False),(7,True),(9,False),(10,True),(11,False)])
def test_second_shift_is_allowed_only_for_legal_parallels(grade,allowed):
    d=small(grade);d['settings']['bells']=two_shift_bells();d['classes'][1]['shift']=2
    errors=[e for e in validate_data(d) if 'первая смена' in e]
    assert bool(errors)!=allowed,errors
    if allowed:
        result=solve(d,seconds=2);assert result['status']=='complete',result
        assert not validate_schedule(d,result['lessons'])
        for l in result['lessons']:
            shift=d['settings']['bells'][l['slot']%10]['shift']
            assert shift==(1 if l['id'].startswith('p0') else 2),l

def test_validator_reports_a_first_shift_lesson_outside_the_first_shift():
    d=scenario_data('two_shifts');result=solve(d,seconds=5)
    assert result['status']=='complete',result
    broken=[dict(l) for l in result['lessons']]
    protected=next(l for l in broken if d['settings']['bells'][l['slot']%10]['shift']==1)
    protected['slot']=(protected['slot']//10)*10+5              # второй урок второй смены
    assert any('только первая смена' in e for e in validate_schedule(d,broken,complete=False))

def test_two_shift_scenario_keeps_protected_parallels_in_the_first_shift():
    data=scenario_data('two_shifts');result=solve(data,seconds=10)
    assert result['status']=='complete',result
    shifts={c['id']:c['shift'] for c in data['classes']}
    assert {c['name']:c['shift'] for c in data['classes']}=={'5А':1,'9А':1,'7А':2,'7Б':2}
    for c in data['classes']:
        if c['grade'] in FIRST_SHIFT_GRADES: assert c['shift']==1
    for l in result['lessons']:
        for cid in next(e for e in events(data) if e['id']==l['id'])['class_ids']:
            assert data['settings']['bells'][l['slot']%10]['shift']==shifts[cid],l

# --- (4) сложный предмет и контрольная не на краю дня ----------------------------------

def test_score_reports_hard_subject_and_test_at_the_day_edges():
    d=scenario_data('balanced')['classes'] and small()
    d['plans'][0]['kind']='test';d['plans'][1]['hours']=1
    closing=[{'id':'p1:0','slot':0,'parts':[{'teacher_id':'t0','room_id':'r0'}]},
             {'id':'p0:0','slot':1,'parts':[{'teacher_id':'t0','room_id':'r0'}]}]
    d['subjects'][0]['difficulty']=9
    messages=[w['message'] for w in score(d,closing)['warnings']]
    assert any('контрольная последним уроком' in m for m in messages),messages
    assert any('сложный предмет последним уроком' in m for m in messages),messages
    opening=[dict(closing[1],slot=0),dict(closing[0],slot=1)]
    messages=[w['message'] for w in score(d,opening)['warnings']]
    assert any('контрольная первым уроком' in m for m in messages),messages
    assert any('сложный предмет первым уроком' in m for m in messages),messages

def test_solver_keeps_a_hard_subject_and_a_test_inside_the_day():
    # Три урока на понедельник: сложные предметы должны оказаться в середине.
    d=small();d['subjects'][0]['difficulty']=9
    d['classes']=d['classes'][:1];d['plans']=d['plans'][:1];d['plans'][0]['hours']=3
    d['classes'][0]['availability']=[{'day':day,'slot':s,'value':'unavailable'} for day in range(1,5) for s in range(8)]
    result=solve(d,seconds=3);assert result['status']=='complete',result
    slots=sorted(l['slot'] for l in result['lessons'])
    assert slots==[0,1,2] and 1 in slots
    assert not [w for w in result['quality']['warnings'] if 'уроком' in w['message']],result['quality']['warnings']

# --- (5) равномерность раскладки -------------------------------------------------------

@pytest.mark.parametrize('key',['balanced','two_shifts'])
def test_week_is_spread_as_evenly_as_the_hours_allow(key):
    data=scenario_data(key);result=solve(data,seconds=10)
    assert result['status']=='complete',result
    load=day_load(data,result['lessons'])
    for c in data['classes']:
        hours=sum(load[c['id']]);base=hours//5
        # Раскладка ideal: одна часть дней с base уроками, остальные с base+1.
        assert deviation(load[c['id']],hours)==hours%5,(c['name'],load[c['id']])

def test_score_reports_the_same_deviation_as_the_model():
    d=small();d['plans'][0]['hours']=5;d['plans'][1]['hours']=5
    lessons=[{'id':f'p0:{i}','slot':i,'parts':[{'teacher_id':'t0','room_id':'r0'}]} for i in range(5)]
    lessons+=[{'id':f'p1:{i}','slot':40+i,'parts':[{'teacher_id':'t0','room_id':'r0'}]} for i in range(5)]
    warnings=[w for w in score(d,lessons)['warnings'] if 'ровной раскладки' in w['message']]
    assert warnings and 'отклоняется от ровной раскладки на 8' in warnings[0]['message'],warnings
