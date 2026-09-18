import copy
import pytest
from backend.domain import *
from backend.solver import solve
from backend.scheduling import validate_schedule, events, rooms_for, prepare_errors

def small(grade=5):
    """Two classes with one teacher each. `grade` matters for the norm profile:
    5, 9 and 11 classes may study only in the first shift, so tests that put a
    class into the second shift ask for a parallel the norms allow there.
    """
    d=empty_data();d['settings']['confirmed']=True
    def add(k,**kw):d[k].append(MODELS[k](**kw).model_dump(mode='json'))
    add('rules',id='weekly',name='Предел школы',key='weekly_max',value=35)
    add('subjects',id='s',name='Математика',merge_allowed=True)
    for i in range(2):
        add('classes',id=f'c{i}',name=f'{grade}{"АБ"[i]}',grade=grade,letter='АБ'[i],size=10)
        add('teachers',id=f't{i}',name=f'Учитель {i}',qualifications=[{'subject_id':'s','level':'primary'}])
        add('rooms',id=f'r{i}',name=f'Кабинет {i}',recommended=20,absolute=23,tags=['lab'])
        add('courses',id=f'course{i}',name='Математика',subject_id='s',grade=grade)
        add('plans',id=f'p{i}',name=f'План {i}',class_id=f'c{i}',course_id=f'course{i}',teacher_ids=['t0'],hours=2,merge_allowed=True,topic=4)
    return d

def assert_valid(d,r):
    assert r['status']=='complete',r
    assert not validate_schedule(d,r['lessons'])

def test_teacher_room_collisions_and_no_student_gaps():
    d=small();r=solve(d,seconds=1);assert_valid(d,r)
    occupied=set()
    for l in r['lessons']:
        for p in l['parts']:
            assert (p['teacher_id'],l['slot']) not in occupied
            occupied.add((p['teacher_id'],l['slot']))

def test_synchronous_groups_get_distinct_resources():
    d=small();d['plans']=d['plans'][:1]
    d['groups']=[Group(id=f'g{i}',name=f'Подгруппа {i}',class_id='c0',size=5).model_dump(mode='json') for i in range(2)]
    d['plans'][0].update(kind='groups',parts=[{'group_id':f'g{i}','teacher_ids':[f't{i}']} for i in range(2)])
    r=solve(d,seconds=1);assert_valid(d,r)
    for l in r['lessons']:
        assert len({p['teacher_id'] for p in l['parts']})==2
        assert len({p['room_id'] for p in l['parts']})==2

def test_laboratory_and_unavailable_teacher():
    d=small();d['rooms'][0]['tags']=[];d['plans'][0].update(kind='lab',tags=['lab'])
    d['teachers'][0]['availability']=[{'day':0,'slot':s,'value':'unavailable'} for s in range(8)]
    r=solve(d,seconds=1);assert_valid(d,r)
    assert all(l['slot']//8!=0 for l in r['lessons'])
    assert all(l['parts'][0]['room_id']=='r1' for l in r['lessons'] if l['id'].startswith('p0:'))

def test_primary_qualification_is_preferred():
    d=small();d['plans']=d['plans'][:1];d['plans'][0]['hours']=1;d['plans'][0]['teacher_ids']=['t0','t1']
    d['teachers'][1]['qualifications'][0]['level']='acceptable'
    r=solve(d,seconds=1);assert_valid(d,r);assert r['lessons'][0]['parts'][0]['teacher_id']=='t0'

def test_compatible_topic_four_merge():
    d=small();d['merges']=[Merge(id='m',name='Объединение',plan_ids=['p0','p1']).model_dump(mode='json')]
    r=solve(d,seconds=1);assert_valid(d,r);assert len(r['lessons'])==2
    assert all(len(e['class_ids'])==2 and e['topic']>=4 for e in events(d))

@pytest.mark.parametrize('field,value',[('language','kk'),('program','Другая'),('version','2'),('grade',6),('level','Профильный')])
def test_incompatible_merges_rejected(field,value):
    d=small();d['courses'][1][field]=value;d['merges']=[Merge(id='m',name='Объединение',plan_ids=['p0','p1']).model_dump(mode='json')]
    assert validate_data(d)

def test_different_topics_rejected():
    d=small();d['plans'][1]['topic']=5;d['merges']=[Merge(id='m',name='Объединение',plan_ids=['p0','p1']).model_dump(mode='json')];assert validate_data(d)

@pytest.mark.parametrize('size,expected',[(23,True),(24,False)])
def test_capacity_tolerance_never_exceeds_absolute(size,expected):
    d=small();e=events(d)[0];p={'size':size};assert bool(rooms_for(d,e,p))==expected
    d['rooms'][0]['absolute']=21;d['rooms'][1]['absolute']=21
    assert not rooms_for(d,e,{'size':22})

def test_locked_lesson_stays_and_manual_collision_fails():
    d=small();r=solve(d,seconds=1);assert_valid(d,r);locked=copy.deepcopy(r['lessons'][0]);locked['lock']='locked'
    newer=solve(d,seconds=1,previous=[locked]);assert_valid(d,newer)
    actual=next(l for l in newer['lessons'] if l['id']==locked['id']);assert actual['slot']==locked['slot'];assert actual['parts']==locked['parts']
    bad=copy.deepcopy(r['lessons']);bad[1]['slot']=bad[0]['slot'];assert validate_schedule(d,bad)

def test_impossible_returns_diagnostics():
    d=small();d['rooms']=[];r=solve(d,seconds=1)
    assert r['status'] in ['partial','infeasible','timeout'];assert r['diagnostics'];assert r['diagnostics'][0]['actions']

def test_student_gap_rejected():
    d=small();lessons=[{'id':'p0:0','slot':0,'parts':[{'teacher_id':'t0','room_id':'r0'}]},{'id':'p0:1','slot':2,'parts':[{'teacher_id':'t0','room_id':'r0'}]}]
    assert any('окно' in e for e in validate_schedule(d,lessons,complete=False))

def test_control_after_pe_forbidden():
    d=small();d['subjects'].append(Subject(id='pe',name='Физкультура',pe=True).model_dump(mode='json'));d['courses'][1]['subject_id']='pe';d['plans'][1]['class_id']='c0';d['plans'][0]['kind']='test'
    d['teachers'][0]['qualifications'].append({'subject_id':'pe','level':'primary'})
    lessons=[{'id':'p1:0','slot':0,'parts':[{'teacher_id':'t0','room_id':'r0'}]},{'id':'p0:0','slot':1,'parts':[{'teacher_id':'t0','room_id':'r0'}]}]
    assert any('Контрольная' in e for e in validate_schedule(d,lessons,complete=False))

def test_calendar_blocks_selected_week_only():
    d=small();d['exceptions']=[ExceptionDay(id='h',name='Праздник',start='2026-09-14',end='2026-09-14').model_dump(mode='json')]
    r=solve(d,week='2026-09-14',seconds=1);assert r['status']=='complete';assert all(l['slot']//8!=0 for l in r['lessons'])

def test_invalid_bells_and_unconfirmed_profile():
    d=small();d['settings']['bells'][0]['end']='09:00';assert validate_data(d)
    d=small();d['settings']['confirmed']=False;assert prepare_errors(d)

def test_required_pair():
    d=small();d['subjects'][0]['double_allowed']=True;d['plans'][0]['pair_required']=True
    r=solve(d,seconds=1);assert_valid(d,r)
    pair=sorted([l for l in r['lessons'] if l['id'].startswith('p0:')],key=lambda l:l['id'])
    assert pair[1]['slot']==pair[0]['slot']+1 and pair[0]['parts']==pair[1]['parts']
