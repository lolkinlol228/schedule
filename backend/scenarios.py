"""Editable input datasets, never precomputed solver results."""
import random
from copy import deepcopy
from .demo import demo_data
from .domain import MODELS, validate_data

SCENARIOS = [
    ('balanced','Обычная школа','Четыре класса, предметные учителя, подгруппы, лаборатория и контрольные.','Проверьте полный цикл от справочников до публикации.'),
    ('small','Мало учеников','Два малокомплектных класса по 8 учеников.','Попробуйте объединение совместимых классов и сравните нагрузку.'),
    ('few_rooms','Мало кабинетов','Четыре класса делят один обычный кабинет и спортзал.','Ресурсов недостаточно для всего плана: изучите частичное решение и диагностику.'),
    ('few_teachers','Мало учителей','Всего три преподавателя с несколькими квалификациями и ограниченной нагрузкой.','Проверьте дефицит нагрузки и добавьте альтернативного преподавателя.'),
    ('scarce','Мало всего','Два небольших класса, два учителя и два кабинета, один кабинет доступен не всю неделю.','Проверьте влияние доступности на небольшую школу.'),
    ('many_students','Много учеников','В каждом классе 38 учеников, большинство кабинетов вмещают только 27.','Диагностика должна учитывать вместимость; увеличьте число подходящих кабинетов.'),
    ('many_rooms','Много кабинетов','Четыре класса и 24 кабинета с разным оборудованием.','Сравните выбор кабинетов при свободных ресурсах.'),
    ('many_teachers','Много учителей','Четыре класса и 35 преподавателей; в планах есть альтернативы.','Изменяйте доступность и наблюдайте перераспределение нагрузки.'),
    ('large','Много всего','28 классов, 600 учеников, 60 преподавателей и 35 кабинетов.','Проверьте расчёт большой школы и фильтры расписания.'),
    ('two_shifts','Две смены по пять уроков','Четыре класса, 10 звонков: по пять в каждой смене. 5 и 9 классы учатся в первую смену, 7 классы — во вторую.','Классы занимаются в своей смене, учителя и кабинеты используются обеими сменами.'),
    ('calendar','Отсутствия и закрытия','Недоступность преподавателя, закрытая лаборатория и календарные исключения.','Выберите неделю с 14 сентября 2026 года, затем сравните с базовой неделей.'),
]

def two_shift_bells():
    bells=[]
    for shift,start in [(1,480),(2,810)]:
        minute=start
        for i in range(5):
            bells.append({'shift':shift,'start':f'{minute//60:02}:{minute%60:02}','end':f'{(minute+45)//60:02}:{(minute+45)%60:02}'})
            minute+=45+(15 if i in (1,3) else 5)
    return bells

def _requalify(d, class_id, grade, letter='А'):
    """Перевести класс в другую параллель: курсы и строки плана создаются заново.

    Нужно сценарию двух смен: нормы РК запрещают 5, 9 и 11 классам вторую смену,
    поэтому вторая смена демонстрации собирается из 7 классов.
    """
    school_class=next(c for c in d['classes'] if c['id']==class_id)
    for plan in [p for p in d['plans'] if p['class_id']==class_id]:
        course=next(c for c in d['courses'] if c['id']==plan['course_id'])
        subject=course['name'].split(' · ')[0]
        new_id=f'{course["subject_id"]}-{grade}-{course["language"]}'
        if not any(c['id']==new_id for c in d['courses']):
            d['courses'].append({**course,'id':new_id,'name':f'{subject} · {grade} · {course["language"]}','grade':grade})
        plan['course_id']=new_id; plan['name']=f'{grade}{letter} · {subject}'
    school_class.update(grade=grade,letter=letter,name=f'{grade}{letter}')
    return school_class

def scenario_data(key, seed=42):
    if key not in {s[0] for s in SCENARIOS}: raise ValueError('Сценарий не найден')
    rng=random.Random(seed); d=demo_data(key=='large')
    title=next(s[1] for s in SCENARIOS if s[0]==key)
    d['settings']['school']='Демонстрация · '+title
    if key in ('small','scarce'):
        d['classes']=d['classes'][:2]
        for c in d['classes']: c['size']=8 if key=='small' else 10
        d['plans']=[p for p in d['plans'] if p['class_id'] in {'c0','c1'}]
    if key=='two_shifts':
        d['settings']['bells']=two_shift_bells()
        # Вторая смена только там, где это разрешено нормой: 5 и 9 классы
        # остаются в первой смене, во вторую переходят 7 классы.
        _requalify(d,'c1',9); _requalify(d,'c2',7); _requalify(d,'c3',7,'Б')
        for i,c in enumerate(d['classes']): c['shift']=1+i//2
        for p in d['plans']: p['hours']=3
    if key=='many_students':
        for c in d['classes']: c['size']=38
    if key in ('few_rooms','scarce'):
        d['rooms']=[d['rooms'][0],d['rooms'][-1]]
    if key=='many_rooms':
        for i in range(6,24):
            r=deepcopy(d['rooms'][0]);r.update(id=f'r{i}',name=f'{101+i}',floor=1+i%3)
            if i%4==0:r['tags']=['projector']
            d['rooms'].append(r)
    if key=='many_teachers':
        for i in range(12,35):
            t=deepcopy(d['teachers'][i%12]);t.update(id=f't{i}',name=f'Преподаватель {i+1:02}')
            d['teachers'].append(t)
    if key in ('few_teachers','scarce'):
        d['teachers']=d['teachers'][:(2 if key=='scarce' else 3)]
        for t in d['teachers']:
            t['qualifications']=[{'subject_id':s['id'],'level':'primary'} for s in d['subjects']]
            t.update(target=18,maximum=20,daily_soft=4,daily_hard=5)
    # Seed changes inputs (teacher choices/room preferences), never supplies a solution.
    for p in d['plans']:
        sid=next(c['subject_id'] for c in d['courses'] if c['id']==p['course_id'])
        pool=[t['id'] for t in d['teachers'] if any(q['subject_id']==sid and q['level']=='primary' for q in t['qualifications'])]
        rng.shuffle(pool)
        p['teacher_ids']=pool[:3] if key=='many_teachers' else pool[:1]
    for course in d['courses']:
        course['topics']=[f'{course["name"].split(" · ")[0]}: тема {i}' for i in range(1,41)]
    def add(kind,**kw):
        obj=MODELS[kind](**kw).model_dump(mode='json'); d[kind].append(obj);return obj
    # Every reference section has an example, but only relevant constraints are active.
    c=d['classes'][0];half=c['size']//2
    for i,size in enumerate([half,c['size']-half]):add('groups',id=f'demo-g{i}',name=f'{c["name"]} · подгруппа {i+1}',class_id=c['id'],size=size,language=c['language'],purpose='Практика иностранного языка')
    for i,(start,end) in enumerate([('2026-09-01','2026-10-23'),('2026-11-02','2026-12-25'),('2027-01-11','2027-03-19'),('2027-03-29','2027-05-31')]):add('periods',id=f'demo-period{i}',name=f'{i+1} четверть',start=start,end=end)
    add('exceptions',id='demo-holiday',name='Учебные каникулы (пример)',start='2026-10-26',end='2026-10-30')
    pair=[p for p in d['plans'] if p['class_id'] in ('c0','c1') and p['course_id'].startswith('history-')]
    common=pair[0]['teacher_ids'];pair[1]['teacher_ids']=common[:]
    add('merges',id='demo-merge',name='История · объединение 5А и 5Б',plan_ids=[p['id'] for p in pair],active=key=='small')
    for subject in d['subjects']:
        if subject['id']=='science':subject['double_allowed']=True
    if key in ('balanced','calendar'):
        p=next(p for p in d['plans'] if p['id']=='p0-english')
        teachers=[t['id'] for t in d['teachers'] if any(q['subject_id']=='english' and q['level'] in ('primary','acceptable') for q in t['qualifications'])]
        p.update(kind='groups',parts=[{'group_id':f'demo-g{i}','teacher_ids':[teachers[i]]} for i in range(2)],merge_allowed=False)
        lab=next(p for p in d['plans'] if p['id']=='p1-science');lab.update(kind='lab',tags=['lab'],hours=2,pair_required=True,merge_allowed=False)
        test=next(p for p in d['plans'] if p['id']=='p0-history');test.update(kind='test',merge_allowed=False)
        # Keep the example merge on another compatible subject. Classes taught
        # together need one common teacher, so both lines share the seeded choice.
        math=[p for p in d['plans'] if p['id'] in ('p0-math','p1-math')]
        math[1]['teacher_ids']=math[0]['teacher_ids'][:]
        d['merges'][0]['plan_ids']=[p['id'] for p in math]
    if key in ('scarce','calendar'):
        d['rooms'][0]['availability']=[{'day':day,'slot':s,'value':'unavailable'} for day in [1,3] for s in range(8)]
    if key=='two_shifts':
        # Пример объединения переносится на две строки одной параллели и одной
        # смены: строки объединяемых классов должны вести вместе.
        pair=[p for p in d['plans'] if p['id'] in ('p2-math','p3-math')]
        pair[1]['teacher_ids']=pair[0]['teacher_ids'][:]
        d['merges'][0].update(plan_ids=[p['id'] for p in pair],name='Математика · объединение 7А и 7Б')
    if key=='calendar':
        add('exceptions',id='demo-absence',name='Отсутствие преподавателя',start='2026-09-14',end='2026-09-16',scope='teachers',resource_id=d['teachers'][0]['id'])
        add('exceptions',id='demo-room-closed',name='Ремонт лаборатории',start='2026-09-14',end='2026-09-18',scope='rooms',resource_id=d['rooms'][0]['id'])
    errors=validate_data(d)
    if errors: raise ValueError('; '.join(errors))
    return d

def catalogue():
    result=[]
    for key,title,description,observe in SCENARIOS:
        d=scenario_data(key)
        result.append({'id':key,'title':title,'description':description,'observe':observe,
            'counts':{k:len(d[k]) for k in MODELS},'students':sum(c['size'] for c in d['classes']),
            'hours':sum(p['hours'] for p in d['plans'])})
    return result
