"""Soft wishes added by the audit: model term, score mirror and end result.

Each test names one rule of `score()` and checks that the CP-SAT model optimises
exactly the term the independent metric reports, so the two cannot drift apart.
"""
from backend.domain import MODELS, Merge, Subject, validate_data
from backend.domain import empty_data
from backend.scheduling import prepare_errors, room_signature, score, validate_schedule
from backend.solver import solve
from backend.scenarios import scenario_data, two_shift_bells
from tests.test_solver import small

def lesson(eid,slot,teacher='t0',room='r0',lock='free'):
    return {'id':eid,'slot':slot,'parts':[{'teacher_id':teacher,'room_id':room}],'lock':lock,'origin':'generator'}

def warnings(result,rule=None,needle=None):
    rows=result['warnings'] if isinstance(result,dict) and 'warnings' in result else result['quality']['warnings']
    return [w for w in rows if (rule is None or w['rule']==rule) and (needle is None or needle in w['message'])]

def simple(subject_hours,extra_subject_hours=0,room_count=2):
    """One class, one teacher: a hard subject 's' plus an easy subject 'f'."""
    d=empty_data(); d['settings']['confirmed']=True
    def add(k,**v):
        row=MODELS[k](**v).model_dump(mode='json'); d[k].append(row); return row
    add('rules',id='weekly',name='Предел школы',key='weekly_max',value=35)
    add('subjects',id='s',name='Математика',difficulty=8)
    add('subjects',id='f',name='История',difficulty=2)
    add('classes',id='c0',name='5А',size=10)
    add('teachers',id='t0',name='Учитель 0',qualifications=[{'subject_id':'s','level':'primary'},{'subject_id':'f','level':'primary'}],target=6,maximum=35)
    for i in range(room_count): add('rooms',id=f'r{i}',name=f'Кабинет {i}',recommended=20,absolute=23)
    add('courses',id='cs',name='Математика',subject_id='s')
    add('courses',id='cf',name='История',subject_id='f')
    add('plans',id='p0',name='План s',class_id='c0',course_id='cs',teacher_ids=['t0'],hours=subject_hours,merge_allowed=True)
    if extra_subject_hours: add('plans',id='p1',name='План f',class_id='c0',course_id='cf',teacher_ids=['t0'],hours=extra_subject_hours,merge_allowed=True)
    return d

# --- merger contract ------------------------------------------------------------------

def test_merge_without_common_teacher_is_rejected():
    d=small();d['plans'][1]['teacher_ids']=['t1']
    d['merges']=[Merge(id='m',name='Объединение',plan_ids=['p0','p1']).model_dump(mode='json')]
    assert any('общего преподавателя' in e for e in validate_data(d))
    d['plans'][1]['teacher_ids']=['t0']
    assert not validate_data(d)

def test_merge_needs_a_teacher_allowed_to_teach_the_subject():
    d=small();d['subjects'].append(Subject(id='other',name='Другой').model_dump(mode='json'))
    d['merges']=[Merge(id='m',name='Объединение',plan_ids=['p0','p1']).model_dump(mode='json')]
    d['teachers'][0]['qualifications']=[{'subject_id':'other','level':'primary'}]
    assert any('общего преподавателя' in e for e in validate_data(d))
    d['teachers'][0]['qualifications']=[{'subject_id':'s','level':'primary'}]
    assert not validate_data(d)

# --- archived reference data ----------------------------------------------------------

def test_archived_reference_is_reported_before_generation():
    d=small();d['subjects'][0]['active']=False
    assert any('в архиве' in e for e in prepare_errors(d))
    result=solve(d,seconds=1)
    assert result['status']=='invalid' and any('в архиве' in e for e in result['errors'])

def test_archived_course_and_group_are_reported():
    d=small();d['courses'][0]['active']=False
    assert any('Курс' in e and 'в архиве' in e for e in prepare_errors(d))
    d=small();d['groups']=[MODELS['groups'](id='g',name='Подгруппа',class_id='c0',size=10).model_dump(mode='json')]
    d['plans'][0]['kind']='groups';d['plans'][0]['parts']=[{'group_id':'g','teacher_ids':['t0']}]
    d['plans'][0]['hours']=2
    d['plans'][1]['kind']='groups';d['plans'][1]['parts']=[{'group_id':'g','teacher_ids':['t0']}]
    d['groups'][0]['active']=False
    assert any('Подгруппа' in e and 'в архиве' in e for e in prepare_errors(d))

# --- score mirrors the added wishes ---------------------------------------------------

def test_score_reports_subject_spread_deficit():
    d=simple(subject_hours=3)
    packed=[lesson('p0:0',0),lesson('p0:1',1),lesson('p0:2',8)]     # two plus one
    assert warnings(score(d,packed),needle='стоит в 2 днях из 3')
    spread=[lesson('p0:0',0),lesson('p0:1',8),lesson('p0:2',16)]    # one per day
    assert not warnings(score(d,spread),needle='днях из')

def test_score_reports_test_position_and_hard_subject_last():
    d=simple(subject_hours=1,extra_subject_hours=2);d['plans'][0]['kind']='test'
    closing=[lesson('p1:0',0),lesson('p1:1',1),lesson('p0:0',2)]
    assert warnings(score(d,closing),needle='контрольная последним уроком')
    assert warnings(score(d,closing),needle='сложный предмет последним уроком')
    opening=[lesson('p0:0',0),lesson('p1:0',1),lesson('p1:1',2)]
    assert warnings(score(d,opening),needle='контрольная первым уроком')
    assert not warnings(score(d,opening),needle='контрольная последним')
    middle=[lesson('p1:0',0),lesson('p0:0',1),lesson('p1:1',2)]
    assert not warnings(score(d,middle),needle='контрольная')
    assert not warnings(score(d,middle),needle='последним уроком')

def test_score_counts_identical_rooms_as_one_room():
    d=simple(subject_hours=2,extra_subject_hours=1)
    assert room_signature(d['rooms'][0])==room_signature(d['rooms'][1])
    mixed=[lesson('p0:0',0,room='r0'),lesson('p0:1',1,room='r1'),lesson('p1:0',2,room='r0')]
    assert not warnings(score(d,mixed),rule='room_changes')
    d['rooms'][1]['recommended']=15
    assert warnings(score(d,mixed),rule='room_changes',needle='нескольких кабинетах')

def test_score_binds_teacher_to_base_room():
    d=simple(subject_hours=1,extra_subject_hours=1)
    d['teachers'][0]['base_room']='r0';d['rooms'][0]['floor']=1;d['rooms'][1]['floor']=3
    outside=[lesson('p0:0',0,room='r1'),lesson('p1:0',1,room='r1')]
    assert warnings(score(d,outside),rule='room_changes',needle='вне базового кабинета')
    inside=[lesson('p0:0',0,room='r0'),lesson('p1:0',1,room='r0')]
    assert not warnings(score(d,inside),rule='room_changes')

def test_score_reports_class_availability_wish():
    d=simple(subject_hours=1,extra_subject_hours=1)
    d['classes'][0]['availability']=[{'day':0,'slot':s,'value':'undesirable'} for s in range(8)]
    assert warnings(score(d,[lesson('p0:0',0),lesson('p1:0',1)]),rule='availability',needle='5А')
    assert not warnings(score(d,[lesson('p0:0',8),lesson('p1:0',9)]),rule='availability',needle='5А')

def test_score_reports_daily_fairness_of_teacher_load():
    d=simple(subject_hours=4,extra_subject_hours=5);d['teachers'][0]['target']=9
    packed=[lesson(f'p1:{i}',i) for i in range(5)]+[lesson(f'p0:{i}',5+i) for i in range(4)]
    assert warnings(score(d,packed),rule='teacher_load',needle='неравномерная нагрузка')
    even=[lesson('p1:0',0),lesson('p0:0',1),lesson('p1:1',8),lesson('p0:1',9),
          lesson('p1:2',16),lesson('p0:2',17),lesson('p1:3',24),lesson('p0:3',25),lesson('p1:4',32)]
    assert not warnings(score(d,even),rule='teacher_load',needle='неравномерная нагрузка')

def test_score_reports_stability_with_the_weight_of_the_lock():
    d=simple(subject_hours=1,extra_subject_hours=1)
    before=[lesson('p0:0',0),lesson('p1:0',1)];after=[lesson('p0:0',8),lesson('p1:0',9)]
    moved=score(d,after,'',before)
    assert len(warnings(moved,rule='stability'))==2
    wished=score(d,after,'',[dict(before[0],lock='preferred'),before[1]])
    assert warnings(wished,rule='stability')[0]['penalty']==warnings(moved,rule='stability')[0]['penalty']*3
    assert not warnings(score(d,before,'',before),rule='stability')
    locked=score(d,after,'',[dict(before[0],lock='locked'),before[1]])
    assert len(warnings(locked,rule='stability'))==1   # only the unlocked lesson is reported

def test_score_reports_merged_lessons():
    d=small()
    d['merges']=[Merge(id='m',name='Объединение',plan_ids=['p0','p1']).model_dump(mode='json')]
    assert warnings(score(d,[lesson('p0+p1:0',0)]),rule='merge',needle='объединённое занятие')

# --- the model actually optimises them ------------------------------------------------

def test_solver_spreads_a_subject_over_separate_days():
    d=simple(subject_hours=3,extra_subject_hours=2)
    result=solve(d,seconds=2);assert result['status']=='complete',result
    assert not warnings(result,needle='днях из')
    assert len({l['slot']//8 for l in result['lessons'] if l['id'].startswith('p0:')})==3

def test_solver_places_a_test_between_two_lessons():
    # Only Monday is available, so the three lessons are forced into one day and
    # the class cannot hide the test by spreading the week.
    d=simple(subject_hours=1,extra_subject_hours=2);d['plans'][0]['kind']='test'
    d['classes'][0]['availability']=[{'day':day,'slot':s,'value':'unavailable'} for day in range(1,5) for s in range(8)]
    result=solve(d,seconds=3);assert result['status']=='complete',result
    assigned=sorted(l['slot'] for l in result['lessons'])
    assert all(s//8==0 for s in assigned),assigned
    assert assigned==list(range(assigned[0],assigned[0]+3)),assigned
    test=next(l for l in result['lessons'] if l['id']=='p0:0')['slot']
    assert assigned[0]<test<assigned[-1],(test,assigned)
    assert not warnings(result,needle='контрольная')
    assert not warnings(result,needle='последним уроком')

def test_solver_respects_class_availability_wish():
    d=simple(subject_hours=2,extra_subject_hours=1)
    d['classes'][0]['availability']=[{'day':0,'slot':s,'value':'undesirable'} for s in range(8)]
    result=solve(d,seconds=2);assert result['status']=='complete',result
    assert not warnings(result,rule='availability',needle='5А')

def test_solver_keeps_preferred_lessons():
    d=simple(subject_hours=4,extra_subject_hours=2)
    first=solve(d,seconds=2);assert first['status']=='complete',first
    previous=[dict(l,lock='preferred') for l in first['lessons']]
    second=solve(d,seconds=2,previous=previous);assert second['status']=='complete',second
    kept={l['id']:l['slot'] for l in second['lessons']}
    assert all(kept[l['id']]==l['slot'] for l in first['lessons'])
    assert not warnings(score(d,second['lessons'],'',previous),rule='stability')

def test_solver_keeps_an_unlocked_rerun_stable():
    # Regeneration with a source version must not reshuffle freely placeable
    # lessons, not only the ones the administrator marked as wishes.
    d=simple(subject_hours=4,extra_subject_hours=2)
    first=solve(d,seconds=2);assert first['status']=='complete',first
    second=solve(d,seconds=2,previous=first['lessons']);assert second['status']=='complete',second
    assert not warnings(score(d,second['lessons'],'',first['lessons']),rule='stability')

# --- two shifts and pairs --------------------------------------------------------------

def test_pair_never_crosses_a_day_or_shift_boundary():
    d=small(7);d['settings']['bells']=two_shift_bells();d['classes'][1]['shift']=2
    d['subjects'][0]['double_allowed']=True
    for p in d['plans']: p['hours']=4;p['pair_required']=True
    assert not prepare_errors(d)
    result=solve(d,seconds=3);assert result['status']=='complete',result
    assert not validate_schedule(d,result['lessons'])
    stride=10
    for l in result['lessons']:
        assert d['settings']['bells'][l['slot']%stride]['shift']==(1 if l['id'].startswith('p0') else 2)
    pairs={}
    for l in result['lessons']:
        base,ordinal=l['id'].rsplit(':',1); pairs.setdefault(f'{base}#{int(ordinal)//2}',[]).append(l['slot'])
    for slots in pairs.values():
        assert len(slots)==2 and slots[1]==slots[0]+1,slots
        assert slots[0]//stride==slots[1]//stride,slots

def test_two_shift_groups_share_a_slot_with_distinct_resources():
    d=small(7);d['settings']['bells']=two_shift_bells();d['classes'][1]['shift']=2
    d['groups']=[MODELS['groups'](id=f'g{i}',name=f'Подгруппа {i}',class_id='c0',size=5).model_dump(mode='json') for i in range(2)]
    d['plans'][0]['kind']='groups'
    d['plans'][0]['parts']=[{'group_id':'g0','teacher_ids':['t0']},{'group_id':'g1','teacher_ids':['t1']}]
    result=solve(d,seconds=3);assert result['status']=='complete',result
    assert not validate_schedule(d,result['lessons'])
    for l in result['lessons']:
        if l['id'].startswith('p0'):
            assert l['slot']%10<5, l
            assert len({p['teacher_id'] for p in l['parts']})==2
            assert len({p['room_id'] for p in l['parts']})==2
    assert all(l['slot']%10>=5 for l in result['lessons'] if l['id'].startswith('p1'))
