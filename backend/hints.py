"""Bounded greedy warm start for CP-SAT. Never backtracks or proves feasibility."""
import random
import time
from collections import defaultdict, Counter
from .domain import limits, slot_stride, class_slots
from .scheduling import indexes, teachers_for, rooms_for, blocked, validate_schedule

def warm_start(data, es, week, seed, budget=.6):
    if any(len(e['class_ids'])!=1 or e['pair_required'] for e in es): return []
    stride=slot_stride(data)
    started=time.monotonic(); ix=indexes(data); best=[]
    teacher_opts={(e['id'],i):teachers_for(data,e,p) for e in es for i,p in enumerate(e['parts'])}
    room_opts={(e['id'],i):rooms_for(data,e,p) for e in es for i,p in enumerate(e['parts'])}
    unavailable={(kind,r['id']):{s for s in range(5*stride) if blocked(data,kind,r['id'],s,week)} for kind in ['classes','teachers','rooms'] for r in data[kind]}
    byclass=defaultdict(list)
    for e in es: byclass[e['class_ids'][0]].append(e)
    for attempt in range(20):
        if time.monotonic()-started>budget: break
        rng=random.Random(seed+attempt); assigned=[]; used_t=set();used_r=set();td=Counter();tw=Counter()
        classes=list(byclass);rng.shuffle(classes)
        for cid in classes:
            pending=list(byclass[cid]);subject_daily=Counter();tests=Counter()
            for day in range(5):
                daily=min(limits(data,'daily_max',ix['classes'][cid]['grade'],8),len(class_slots(data,ix['classes'][cid])), (len(pending)+4-day)//(5-day))
                prev=None
                for slot in class_slots(data,ix['classes'][cid])[:daily]:
                    s=day*stride+slot
                    if s in unavailable['classes',cid]: break
                    remaining=Counter(e['subject_id'] for e in pending)
                    choices=sorted(pending,key=lambda e:(-remaining[e['subject_id']],rng.random()))
                    selected=None
                    for e in choices:
                        subj=ix['subjects'][e['subject_id']]
                        if not e['active'] or subject_daily[day,e['subject_id']]>=2:continue
                        if any(p['plan_ids']==e['plan_ids'] and p['ordinal']<e['ordinal'] for p in pending):continue
                        if prev and (prev['subject_id']==e['subject_id'] and not subj['double_allowed'] or e['kind']=='test' and (prev['kind']=='test' or ix['subjects'][prev['subject_id']]['pe'])):continue
                        if e['kind']=='test' and tests[day]>=limits(data,'tests_daily',ix['classes'][cid]['grade'],1):continue
                        parts=[];pt=set();pr=set()
                        for i,part in enumerate(e['parts']):
                            teachers=sorted(teacher_opts[e['id'],i],key=lambda t:(not any(q['subject_id']==e['subject_id'] and q['level']=='primary' for q in t['qualifications']),tw[t['id']]))
                            t=next((t for t in teachers if (t['id'],s) not in used_t and t['id'] not in pt and s not in unavailable['teachers',t['id']] and tw[t['id']]<t['maximum'] and td[t['id'],day]<t['daily_hard']),None)
                            room=next((r for r in room_opts[e['id'],i] if (r['id'],s) not in used_r and r['id'] not in pr and s not in unavailable['rooms',r['id']]),None)
                            if not t or not room:break
                            pt.add(t['id']);pr.add(room['id']);parts.append({'teacher_id':t['id'],'room_id':room['id']})
                        if len(parts)==len(e['parts']):selected=e,parts;break
                    if not selected:break
                    e,parts=selected;pending.remove(e);prev=e;subject_daily[day,e['subject_id']]+=1
                    if e['kind']=='test':tests[day]+=1
                    assigned.append({'id':e['id'],'slot':s,'parts':parts,'lock':'free','origin':'generator'})
                    for p in parts:
                        used_t.add((p['teacher_id'],s));used_r.add((p['room_id'],s));td[p['teacher_id'],day]+=1;tw[p['teacher_id']]+=1
        if len(assigned)>len(best):best=assigned
        if len(best)==len(es):break
    return best if not validate_schedule(data,best,week,False) else []
