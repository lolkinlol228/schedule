"""Scheduling domain: event expansion, eligibility and independent validation."""
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from .domain import limits, validate_data, applicable_rules, slot_stride, class_slots, requires_first_shift

DAYS = ['Понедельник','Вторник','Среда','Четверг','Пятница']

#: Порог «сложного предмета» в шкале `Subject.difficulty` (1–10). Восьмёрке
#: соответствуют группы приложения 4 к СП № ҚР ДСМ-76 с наибольшим числом
#: баллов: математика и государственные языки (11 баллов → 10), иностранный
#: язык (10 → 9), физика, химия, информатика, биология (9 → 8). Предметы с
#: меньшим баллом (история — 8 → 7, естествознание — 6 → 5) считаются
#: облегчающими урок, что и нужно для расстановки краёв учебного дня.
HARD_DIFFICULTY = 8

def is_hard(subject):
    return subject['difficulty']>=HARD_DIFFICULTY

def class_day_base(hours):
    """Идеальная дневная нагрузка класса: недельные часы, разделённые на дни.

    Сумма отклонений `|нагрузка_дня - base|` по пяти дням равна `extra + 2*D`,
    где `D` — суммарный недобор относительно base. Поэтому минимизация этого
    отклонения одновременно убирает пустые дни и перегруженные дни.
    """
    return hours//5


def indexes(data):
    return {k:{r['id']:r for r in v} for k,v in data.items() if isinstance(v,list)}

def room_signature(room):
    """Interchangeable rooms share a signature: same capacity, equipment, floor and rules.

    The solver may only pick between groups of identical rooms, so the quality
    metric has to compare this signature instead of raw room identifiers. Two
    identical rooms are a free swap, not a real room change.
    """
    return json.dumps({k:v for k,v in room.items() if k not in ['id','name','teacher_id']},sort_keys=True)

def events(data, week=''):
    ix = indexes(data)
    plans = {p['id']:p for p in data['plans'] if p['active'] and ix['classes'][p['class_id']]['active']}
    merges = [m for m in data['merges'] if m['active'] and (not m['week'] or m['week']==week)]
    merged = {pid for m in merges for pid in m['plan_ids']}
    bundles = [[p] for pid,p in plans.items() if pid not in merged]
    bundles += [[plans[pid] for pid in m['plan_ids'] if pid in plans] for m in merges]
    result=[]
    for bundle in bundles:
        if not bundle: continue
        p=bundle[0]; course=ix['courses'][p['course_id']]; subject=ix['subjects'][course['subject_id']]
        classes=[q['class_id'] for q in bundle]
        if p['kind']=='groups':
            parts=[{'group_id':part['group_id'],'size':ix['groups'][part['group_id']]['size'],'teacher_ids':part['teacher_ids']} for part in p['parts']]
        else:
            tids=set(p['teacher_ids'])
            for q in bundle: tids &= set(q['teacher_ids'])
            parts=[{'group_id':'','size':sum(ix['classes'][c]['size'] for c in classes),'teacher_ids':sorted(tids)}]
        for n in range(p['hours']):
            result.append({'id':'+'.join(sorted(q['id'] for q in bundle))+f':{n}', 'plan_ids':[q['id'] for q in bundle],
                'class_ids':classes,'subject_id':subject['id'],'course_id':course['id'],'topic':p['topic']+n,'kind':p['kind'],
                'pair_required':p['pair_required'],'ordinal':n,'parts':parts,'tags':sorted(set(subject['tags']+sum([q['tags'] for q in bundle],[]))),
                'accessible':any(ix['classes'][c]['accessible'] for c in classes), 'active':subject['active'] and course['active'] and all(ix['groups'][pt['group_id']]['active'] for pt in parts if pt['group_id'])})
    return result

def availability(resource, slot, stride=8):
    values = [a['value'] for a in resource.get('availability',[]) if a['day']==slot//stride and a['slot']==slot%stride]
    for v in ['unavailable','undesirable','preferred']:
        if v in values: return v
    return 'possible'

def blocked(data, kind, rid, slot, week=''):
    stride=slot_stride(data)
    ix=indexes(data) if kind!='school' else None
    if slot%stride >= len(data['settings']['bells']): return True
    if kind!='school':
        r=ix[kind][rid]
        if kind=='classes' and slot%stride not in class_slots(data,r): return True
        if not r['active'] or availability(r,slot,stride)=='unavailable': return True
        if kind=='teachers' and r['method_hard'] and r['method_day']==slot//stride: return True
    if not week: return False
    current=date.fromisoformat(week)+timedelta(days=slot//stride)
    if not date.fromisoformat(data['settings']['year_start']) <= current <= date.fromisoformat(data['settings']['year_end']): return True
    return any(e['active'] and date.fromisoformat(e['start'])<=current<=date.fromisoformat(e['end']) and
        (e['scope']=='school' or e['scope']==kind and e['resource_id']==rid) and (not e['slots'] or slot%stride in e['slots']) for e in data['exceptions'])

def teachers_for(data, event, part):
    return [t for t in data['teachers'] if t['active'] and t['id'] in part['teacher_ids'] and
            any(q['subject_id']==event['subject_id'] and q['level'] in ('primary','acceptable') for q in t['qualifications'])]

def rooms_for(data, event, part):
    return [r for r in data['rooms'] if r['active'] and part['size']<=min(r['absolute'],r['recommended']+3) and
        set(event['tags'])<=set(r['tags']) and (not r['subjects'] or event['subject_id'] in r['subjects']) and
        (not event['accessible'] or r['floor'] in data['settings']['accessible_floors'])]

def prepare_errors(data):
    result=validate_data(data)
    if not data['settings']['confirmed']: result.append('Подтвердите недельные нормативы в настройках учебного года')
    ix=indexes(data)
    # An active plan line that points at archived reference data can never be
    # placed. Without this check the generator reported it as an unsolvable
    # request and the diagnostics blamed teachers or rooms.
    archived={}
    for kind,label in [('subjects','Предмет'),('courses','Курс'),('groups','Подгруппа')]:
        for row in data[kind]:
            if not row['active']: archived[kind,row['id']]=f'{label} «{row["name"]}» в архиве'
    for p in data['plans']:
        if not p['active'] or not ix['classes'].get(p['class_id'],{}).get('active'): continue
        blockers=[]
        course=ix['courses'].get(p['course_id'])
        if course:
            blockers+=[archived.get(('courses',course['id'])),archived.get(('subjects',course['subject_id']))]
        for part in p['parts']: blockers.append(archived.get(('groups',part['group_id'])))
        found=next((x for x in blockers if x),None)
        if found: result.append(f'{p["name"]}: {found}. Верните запись из архива или отключите строку плана')
    for c in data['classes']:
        if not c['active']: continue
        rules=[r for r in applicable_rules(data) if r['kind']=='hard' and r['key']=='weekly_max' and r['grade'] in (0,c['grade'])]
        if not rules: result.append(f'{c["name"]}: задайте подтверждённый недельный предел')
        hours=sum(p['hours'] for p in data['plans'] if p['active'] and p['class_id']==c['id'])
        if hours>limits(data,'weekly_max',c['grade']): result.append(f'{c["name"]}: {hours} часов превышают недельный норматив {limits(data,"weekly_max",c["grade"])}')
        if hours>5*min(len(class_slots(data,c)),limits(data,'daily_max',c['grade'],8)): result.append(f'{c["name"]}: часы плана не помещаются в пятидневную неделю')
    if not any(p['active'] and ix['classes'].get(p['class_id'],{}).get('active') for p in data['plans']): result.append('Добавьте хотя бы одну активную строку учебного плана')
    return list(dict.fromkeys(result))

def validate_schedule(data, lessons, week='', complete=True, locked=None):
    stride=slot_stride(data)
    ix=indexes(data); ev={e['id']:e for e in events(data,week)}
    errors=[]; seen=set(); occupancy={k:{} for k in ['classes','teachers','rooms']}
    class_day=defaultdict(set); teacher_day=defaultdict(set); class_subject_day=Counter(); tests=Counter(); class_slot={}
    actual={l['id']:l for l in lessons}
    # Занятия первой смены в текущей сетке звонков: нужны для правовой проверки.
    first_shift={s for s in range(5*stride) if s%stride<len(data['settings']['bells']) and data['settings']['bells'][s%stride].get('shift',1)==1}
    legal_shift={c['id']:first_shift if requires_first_shift(data,c['grade']) else set(range(5*stride)) for c in data['classes']}
    if complete:
        missing=set(ev)-set(actual)
        if missing: errors.append(f'Не размещено занятий: {len(missing)}')
    for l in lessons:
        eid=l['id']; e=ev.get(eid); s=l['slot']
        if not e: errors.append(f'Занятие {eid} отсутствует в учебном плане'); continue
        if eid in seen: errors.append('Повторяющееся занятие'); continue
        seen.add(eid)
        if not e['active']: errors.append('Предмет, курс или подгруппа архивированы')
        if not 0<=s<5*stride or s%stride>=len(data['settings']['bells']): errors.append('Урок за пределами сетки звонков'); continue
        day=s//stride
        for cid in e['class_ids']:
            if (cid,s) in occupancy['classes']: errors.append(f'{ix["classes"][cid]["name"]}: два занятия одновременно')
            occupancy['classes'][(cid,s)]=eid
            if blocked(data,'classes',cid,s,week): errors.append(f'{ix["classes"][cid]["name"]}: время недоступно')
            if s not in legal_shift[cid]: errors.append(f'{ix["classes"][cid]["name"]}: для {ix["classes"][cid]["grade"]} классов нормой разрешена только первая смена')
            class_day[cid,day].add(s%stride); class_slot[cid,s]=e
            class_subject_day[cid,day,e['subject_id']]+=1
            if e['kind']=='test': tests[cid,day]+=1
        if len(l['parts'])!=len(e['parts']): errors.append('Неверное количество синхронных подгрупп'); continue
        for part,assignment in zip(e['parts'],l['parts']):
            tid,rid=assignment['teacher_id'],assignment['room_id']
            if tid not in {t['id'] for t in teachers_for(data,e,part)}: errors.append('Учитель не разрешён или не имеет допустимой квалификации')
            if rid not in {r['id'] for r in rooms_for(data,e,part)}: errors.append('Кабинет не соответствует вместимости, оборудованию или доступному этажу')
            for kind,resource in [('teachers',tid),('rooms',rid)]:
                if resource not in ix[kind]: continue
                if (resource,s) in occupancy[kind]: errors.append(f'{ix[kind][resource]["name"]}: два занятия одновременно')
                occupancy[kind][resource,s]=eid
                if blocked(data,kind,resource,s,week): errors.append(f'{ix[kind][resource]["name"]}: время недоступно')
            teacher_day[tid,day].add(s%stride)
        if locked and eid in locked:
            old=locked[eid]
            if old['slot']!=s or old['parts']!=l['parts']: errors.append('Заблокированное занятие нельзя перемещать или заменять')
    for (cid,day),slots in class_day.items():
        c=ix['classes'][cid]
        if len(slots)!=max(slots)-min(slots)+1: errors.append(f'{c["name"]}, {DAYS[day]}: окно у учеников')
        if len(slots)>limits(data,'daily_max',c['grade'],8): errors.append(f'{c["name"]}: превышен дневной максимум')
    for (cid,day,sid),count in class_subject_day.items():
        if count>2: errors.append(f'{ix["classes"][cid]["name"]}: более двух уроков одного предмета в день')
    for (cid,day),count in tests.items():
        if count>limits(data,'tests_daily',ix['classes'][cid]['grade'],1): errors.append('Превышено число контрольных за день')
    for (cid,s),e in class_slot.items():
        prev=class_slot.get((cid,s-1)) if s%stride else None
        if prev:
            if e['subject_id']==prev['subject_id'] and not ix['subjects'][e['subject_id']]['double_allowed']: errors.append('Сдвоенное занятие по предмету запрещено')
            if e['kind']=='test' and (prev['kind']=='test' or ix['subjects'][prev['subject_id']]['pe']): errors.append('Контрольная сразу после физкультуры или другой контрольной запрещена')
    for t in data['teachers']:
        if sum(len(teacher_day[t['id'],d]) for d in range(5))>t['maximum']: errors.append(f'{t["name"]}: превышена недельная нагрузка')
        if any(len(teacher_day[t['id'],d])>t['daily_hard'] for d in range(5)): errors.append(f'{t["name"]}: превышена дневная нагрузка')
    for e in ev.values():
        if e['ordinal']>0 and e['id'] in actual:
            before=e['id'].rsplit(':',1)[0]+f':{e["ordinal"]-1}'
            if before in actual and actual[before]['slot']>=actual[e['id']]['slot']: errors.append('Темы курса должны идти по порядку')
        if e['pair_required'] and e['ordinal']%2==0:
            other=e['id'].rsplit(':',1)[0]+f':{e["ordinal"]+1}'
            a,b=actual.get(e['id']),actual.get(other)
            if bool(a)!=bool(b) or a and (b['slot']!=a['slot']+1 or a['slot']//stride!=b['slot']//stride or a['parts']!=b['parts']): errors.append('Обязательная пара должна идти подряд с теми же ресурсами')
    if locked and set(locked)-set(actual): errors.append('Заблокированное занятие нельзя удалять')
    return list(dict.fromkeys(errors))

def score(data, lessons, week='', previous=None):
    """Weighted cost of a timetable, mirroring every soft term of the CP-SAT model.

    `previous` is the placement the schedule was derived from. It is optional:
    stability is only meaningful when a source version was supplied, so manual
    edits (which are supposed to move lessons) are scored without it.

    Bonuses of the solver are not reported as costs: a `preferred` availability
    window and a `practicable` stay in the base room lower the search objective
    but are not violations, so they never appear in `warnings`.
    """
    stride=slot_stride(data)
    ix=indexes(data); es=events(data,week); ev={e['id']:e for e in es}; warnings=[]
    priorities={'low':1,'medium':5,'high':20,'critical':100}
    def weight(key):
        return max([priorities[r['priority']] for r in applicable_rules(data) if r['kind']=='soft' and r['key']==key] or [0])
    def add(key,message,amount=1):
        if amount>0 and weight(key): warnings.append({'rule':key,'message':message,'penalty':weight(key)*amount})
    active=[e for e in es if e['active']]
    planned_hours=Counter((cid,e['subject_id']) for e in active for cid in e['class_ids'])
    planned_tests=Counter(cid for e in active if e['kind']=='test' for cid in e['class_ids'])
    slots=defaultdict(set); rooms=defaultdict(dict); byclass=defaultdict(dict)
    subject_days=defaultdict(set); test_days=defaultdict(set)
    for l in lessons:
        e=ev.get(l['id'])
        if not e: continue
        s=l['slot']; day=s//stride; subj=ix['subjects'][e['subject_id']]
        for cid in e['class_ids']:
            byclass[cid][s]=e
            subject_days[cid,e['subject_id']].add(day)
            if e['kind']=='test': test_days[cid].add(day)
        if len(e['class_ids'])>1: add('merge',f'{subj["name"]}: объединённое занятие')
        if len(l['parts'])!=len(e['parts']): continue
        for part,assignment in zip(e['parts'],l['parts']):
            t=ix['teachers'].get(assignment['teacher_id']); r=ix['rooms'].get(assignment['room_id'])
            if not t or not r: continue
            slots[t['id'],day].add(s%stride); rooms[t['id']][s]=room_signature(r)
            if availability(t,s,stride)=='undesirable': add('availability',f'{t["name"]}: нежелательное время',4)
            if availability(r,s,stride)=='undesirable': add('availability',f'{r["name"]}: нежелательное время',4)
            for cid in e['class_ids']:
                c=ix['classes'][cid]
                if availability(c,s,stride)=='undesirable': add('availability',f'{c["name"]}: нежелательное время',4)
            if t['method_day']==day: add('method_day',f'{t["name"]}: занятие в методический день')
            if not any(q['subject_id']==e['subject_id'] and q['level']=='primary' for q in t['qualifications']): add('qualification',f'{t["name"]}: допустимая квалификация')
            if part['size']>r['recommended']: add('merge',f'{r["name"]}: превышение рекомендуемой вместимости на {part["size"]-r["recommended"]}',part['size']-r['recommended'])
    for t in data['teachers']:
        total=0
        fair=max(1,-(-t['target']//5))
        for day in range(5):
            ss=slots[t['id'],day]; total+=len(ss)
            if ss:
                add('teacher_gaps',f'{t["name"]}, {DAYS[day]}: окна',max(ss)-min(ss)+1-len(ss))
                add('teacher_load',f'{t["name"]}, {DAYS[day]}: выше желаемой дневной нагрузки',max(0,len(ss)-t['daily_soft']))
                add('teacher_load',f'{t["name"]}, {DAYS[day]}: неравномерная нагрузка по дням',max(0,len(ss)-fair))
                for start in range(stride-t['consecutive']):
                    if all(s in ss for s in range(start,start+t['consecutive']+1)): add('consecutive',f'{t["name"]}: более {t["consecutive"]} уроков подряд')
        if total: add('teacher_load',f'{t["name"]}: отклонение от целевой недельной нагрузки',abs(total-t['target']))
        # Interchangeable rooms count as one room: the metric works on signatures.
        base=ix['rooms'].get(t['base_room']); base_signature=room_signature(base) if base else None
        per_day=defaultdict(set)
        for s,signature in rooms[t['id']].items(): per_day[s//stride].add(signature)
        for day,used in sorted(per_day.items()):
            add('room_changes',f'{t["name"]}, {DAYS[day]}: работа в нескольких кабинетах',len(used)-1)
            if base_signature and any(x!=base_signature for x in used): add('room_changes',f'{t["name"]}, {DAYS[day]}: занятие вне базового кабинета')
    for cid,ss in byclass.items():
        if not ss: continue
        bounds=defaultdict(list)
        for s in ss: bounds[s//stride].append(s%stride)
        first={day:min(v) for day,v in bounds.items()}; last={day:max(v) for day,v in bounds.items()}
        for s,e in ss.items():
            subj=ix['subjects'][e['subject_id']]; local=s%stride; day=s//stride
            # First and last position are two separate wishes, as in the model.
            if e['kind']=='test' and local==first[day]: add('difficulty',f'{ix["classes"][cid]["name"]}, {DAYS[day]}: контрольная первым уроком')
            if e['kind']=='test' and local==last[day]: add('difficulty',f'{ix["classes"][cid]["name"]}, {DAYS[day]}: контрольная последним уроком')
            if is_hard(subj) and local==first[day]: add('difficulty',f'{ix["classes"][cid]["name"]}, {DAYS[day]}: сложный предмет первым уроком')
            if is_hard(subj) and local==last[day]: add('difficulty',f'{ix["classes"][cid]["name"]}, {DAYS[day]}: сложный предмет последним уроком')
            prev=ss.get(s-1) if s%stride else None
            if prev and ix['subjects'][prev['subject_id']]['pe'] and is_hard(subj): add('difficulty',f'{ix["classes"][cid]["name"]}: сложный предмет после физкультуры')
            if s%stride>=2 and s-1 in ss and s-2 in ss and all(is_hard(ix['subjects'][ss[q]['subject_id']]) for q in [s-2,s-1,s]): add('difficulty',f'{ix["classes"][cid]["name"]}: три сложных предмета подряд')
        counts=Counter((s//stride,e['subject_id']) for s,e in ss.items())
        for (day,sid),n in counts.items():
            if n>1: add('distribution',f'{ix["classes"][cid]["name"]}, {DAYS[day]}: повтор предмета',n-1)
    # Равномерность дневной нагрузки класса: тот же модуль отклонения от ideal,
    # что и мягкая цель модели. При недельных часах меньше пяти слагаемое
    # постоянно (сумма нагрузки равна часам) и потому не создаётся.
    class_planned=Counter(cid for e in active for cid in e['class_ids'])
    for cid,hours in class_planned.items():
        if hours<5: continue
        base=class_day_base(hours); load=Counter(s//stride for s in byclass.get(cid,{}))
        deviation=sum(abs(load.get(day,0)-base) for day in range(5))
        add('distribution',f'{ix["classes"][cid]["name"]}: дневная нагрузка отклоняется от ровной раскладки на {deviation}',deviation)
    for (cid,sid),hours in planned_hours.items():
        want=min(hours,5); used=len(subject_days[cid,sid])
        if want>used: add('distribution',f'{ix["classes"][cid]["name"]}: {ix["subjects"][sid]["name"]} стоит в {used} днях из {want}')
    for cid,total_tests in planned_tests.items():
        want=min(total_tests,5); used=len(test_days[cid])
        if want>used: add('distribution',f'{ix["classes"][cid]["name"]}: контрольные стоят в {used} днях из {want}')
    if previous:
        prior={l['id']:l for l in previous}
        for l in lessons:
            old=prior.get(l['id'])
            if not old or old.get('lock')=='locked' or old['slot']==l['slot']: continue
            e=ev.get(l['id'])
            label=', '.join(ix['classes'][c]['name'] for c in e['class_ids'])+' · '+ix['subjects'][e['subject_id']]['name'] if e else l['id']
            add('stability',f'{label}: размещение изменено относительно исходной версии',3 if old.get('lock')=='preferred' else 1)
    return {'penalty':sum(w['penalty'] for w in warnings),'warnings':warnings}

def capacity_issues(data, week=''):
    """Necessary capacity bounds; passing these is not proof of feasibility."""
    es=events(data,week); stride=slot_stride(data); ix=indexes(data); issues=[]
    required=sum(len(e['parts']) for e in es)
    for kind,eligible,label in [('teachers',teachers_for,'Преподаватели'),('rooms',rooms_for,'Кабинеты')]:
        ids={r['id'] for e in es for part in e['parts'] for r in eligible(data,e,part)}
        capacity=0
        for rid in ids:
            r=ix[kind][rid]
            daily=[sum(not blocked(data,kind,rid,day*stride+slot,week) for slot in range(len(data['settings']['bells']))) for day in range(5)]
            capacity+=min(r['maximum'],sum(min(n,r['daily_hard']) for n in daily)) if kind=='teachers' else sum(daily)
        if required>capacity:
            issues.append({'resource':kind,'required':required,'capacity':capacity,'deficit':required-capacity,
                'message':f'{label}: требуется {required} ресурсных часов, доступно не более {capacity}. Не хватает как минимум {required-capacity}.',
                'action':'Добавьте квалифицированных учителей и назначения в плане либо пересмотрите учебный план. Увеличивайте пределы нагрузки только если это допустимо.' if kind=='teachers' else 'Добавьте подходящие кабинеты, пересмотрите их доступность или распределение классов по сменам.'})
    return issues

def diagnose(data, missing, week=''):
    ix=indexes(data); result=[]
    for e in missing:
        label=', '.join(ix['classes'][c]['name'] for c in e['class_ids'])+' · '+ix['subjects'][e['subject_id']]['name']
        ts=[teachers_for(data,e,p) for p in e['parts']]; rs=[rooms_for(data,e,p) for p in e['parts']]
        if any(not x for x in ts): reason='Нет разрешённого преподавателя с основной или допустимой квалификацией'; actions=['Назначьте квалифицированного преподавателя в учебном плане.']
        elif any(not x for x in rs): reason='Нет кабинета с нужным оборудованием, вместимостью или доступным этажом'; actions=['Проверьте оборудование и сертифицированную вместимость кабинетов.']
        else: reason='Занятие не размещено в найденном варианте. Это само по себе не доказывает невозможность полного расписания'; actions=['Посмотрите подтверждённые ограничения ресурсов над списком.','Проверьте доступность и разрешённых преподавателей. Если дефицит не выявлен, попробуйте повторный расчёт.']
        result.append({'lesson_id':e['id'],'title':label,'reason':reason,'actions':actions,'effect':'Требует повторной генерации; эффект ещё не проверен','requires_confirmation':True})
    return result
