"""Explicit, verified alternatives; never mutate the school's master data."""
import copy
from .domain import Merge, validate_data
from .scheduling import indexes, events, rooms_for

def proposals(data, week=''):
    ix=indexes(data); expanded=copy.deepcopy(data);changed=[]
    for p in expanded['plans']:
        if not p['active']:continue
        sid=ix['courses'][p['course_id']]['subject_id']
        for part in p['parts'] if p['kind']=='groups' else [p]:
            alternatives=[t['id'] for t in data['teachers'] if t['active'] and any(q['subject_id']==sid and q['level'] in ['primary','acceptable'] for q in t['qualifications'])]
            extra=[t for t in alternatives if t not in part['teacher_ids']]
            if extra:part['teacher_ids']+=extra;changed.append(p['name'])
    if changed:
        yield {'title':'Использовать квалифицированных альтернативных учителей','changes':list(dict.fromkeys(changed)),'data':expanded}
    merged={pid for m in data['merges'] if m['active'] and (not m['week'] or m['week']==week) for pid in m['plan_ids']}
    plans=[p for p in data['plans'] if p['active'] and p['merge_allowed'] and p['kind']=='normal' and p['id'] not in merged]
    for i,p in enumerate(plans):
        for other in plans[i+1:]:
            candidate=copy.deepcopy(data)
            merge=Merge(id='proposal-merge',name=f'{p["name"]} + {other["name"]}',plan_ids=[p['id'],other['id']],week=week).model_dump(mode='json')
            candidate['merges'].append(merge)
            if validate_data(candidate):continue
            e=next((e for e in events(candidate,week) if set(e['plan_ids'])=={p['id'],other['id']}),None)
            if e and rooms_for(candidate,e,e['parts'][0]):
                yield {'title':'Объединить совместимые классы','changes':[merge['name']],'data':candidate}
                return

def coverage(data, lessons, week=''):
    es={e['id']:e for e in events(data,week)}
    return sum(len(es[l['id']]['class_ids']) for l in lessons if l['id'] in es)
