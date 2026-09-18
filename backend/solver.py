"""CP-SAT model. No handwritten search; independent validator gates every result."""
import time
import os
from collections import Counter, defaultdict
import ortools
from ortools.sat.python import cp_model
from .domain import limits, applicable_rules, slot_stride
from .scheduling import events, indexes, blocked, availability, teachers_for, rooms_for, prepare_errors, validate_schedule, score, diagnose, capacity_issues, room_signature, is_hard, class_day_base
from .hints import warm_start

# An omitted mandatory lesson must outweigh every soft term combined.
MISSING_WEIGHT=100000000

#: До этого числа занятий модель пробует заведомо ровную раскладку недели
#: отдельной попыткой. Попытка стоит времени, а в большой школе её жёсткие
#: границы почти неразрешимы, поэтому там работает только мягкая цель.
IDEAL_PROBE_MAX_EVENTS=250
#: Бюджет попытки ровной недели в секундах (не больше доли интерактивного лимита).
IDEAL_PROBE_SECONDS=2.

def solve(data, week='', seed=42, seconds=10, previous=None, cancel=None, solver_ready=None):
    stride=slot_stride(data)
    started=time.monotonic(); seconds=max(.1,seconds-1.2 if seconds>=3 else seconds*.85); errors=prepare_errors(data)
    if errors: return {'status':'invalid','lessons':[],'errors':errors,'diagnostics':[],'elapsed':time.monotonic()-started}
    es=events(data,week); ix=indexes(data); old={l['id']:l for l in previous or []}
    required=[e for e in es if e['active']]
    warm=warm_start(data,es,week,seed,min(.6,seconds/5)) if not old else []
    hints={l['id']:l for l in warm}
    m=cp_model.CpModel(); solver=cp_model.CpSolver()
    if solver_ready: solver_ready(solver)
    starts={}; present={}; at={}; selections={}; resources=defaultdict(list); teaching=defaultdict(list); class_events=defaultdict(list)
    penalties=[]; balance_terms=[]; ideal=[]; teacher_slots=defaultdict(list); gap_totals=[]; class_of_event={e['id']:e['class_ids'] for e in es}
    priorities={'low':1,'medium':5,'high':20,'critical':100}
    # Which room group a teacher works in on a given day. Kept at day resolution:
    # a per-slot conjunction for every identical-room candidate multiplied the
    # model by three and made the first complete grid unreachable in time.
    td_terms={}
    def weight(key): return max([priorities[r['priority']] for r in applicable_rules(data) if r['kind']=='soft' and r['key']==key] or [0])
    def conjunction(a,b,name):
        z=m.new_bool_var(name); m.add(z<=a); m.add(z<=b); m.add(z>=a+b-1); return z
    # Identical rooms are interchangeable. Model their common capacity once and
    # assign concrete room numbers after solving, preserving all explicit locks.
    room_groups={}; room_group_of={}; signatures={}
    concrete_rooms=any(e['pair_required'] for e in es)
    signature_of={r['id']:room_signature(r) for r in data['rooms']}
    for r in data['rooms']:
        # Pairs require the same physical room across both slots. Group capacity
        # alone cannot guarantee that after assigning concrete room numbers.
        signature=r['id'] if concrete_rooms else room_signature(r)
        group=signatures.setdefault(signature,r['id']); room_groups.setdefault(group,[]).append(r['id']); room_group_of[r['id']]=group
    room_intervals=defaultdict(list)
    # Resources have fixed intervals for unavailable hours, optional intervals for lessons.
    unavailable={}
    for kind in ('classes','teachers','rooms'):
        for r in data[kind]:
            unavailable[kind,r['id']]={s for s in range(5*stride) if blocked(data,kind,r['id'],s,week)}
            if kind=='teachers':
                for s in unavailable[kind,r['id']]: resources[kind,r['id']].append(m.new_fixed_size_interval_var(s,1,f'blocked_{kind}_{r["id"]}_{s}'))
    # Seed hints are feasible-looking only; they never override constraints.
    for ei,e in enumerate(es):
        eid=e['id']; starts[eid]=m.new_int_var(0,5*stride-1,f's_{ei}'); present[eid]=m.new_bool_var(f'p_{ei}')
        allowed=[s for s in range(5*stride) if all(s not in unavailable['classes',c] for c in e['class_ids'])]
        at[eid]={s:m.new_bool_var(f'a_{ei}_{s}') for s in allowed}
        m.add(sum(at[eid].values())==present[eid]); m.add(starts[eid]==sum(s*v for s,v in at[eid].items()))
        if not e['active']: m.add(present[eid]==0)
        dayvars=[]
        for d in range(5):
            dv=m.new_bool_var(f'd_{ei}_{d}'); m.add(dv==sum(v for s,v in at[eid].items() if s//stride==d)); dayvars.append(dv)
        for cid in e['class_ids']: class_events[cid].append(e)
        subj=ix['subjects'][e['subject_id']]
        for s,v in at[eid].items():
            if subj['difficulty']>=7 and not(s//stride in (1,2) and s%stride in (1,2,3)): penalties.append(v*weight('difficulty'))
            for cid in e['class_ids']:
                # Wishes of a class are soft exactly like the wishes of its teacher;
                # 'unavailable' is already a hard block.
                av=availability(ix['classes'][cid],s,stride)
                if av in ('undesirable','preferred'): penalties.append(v*weight('availability')*(4 if av=='undesirable' else -1))
        if len(e['class_ids'])>1: penalties.append(present[eid]*weight('merge'))
        for pi,part in enumerate(e['parts']):
            # Rooms: one choice per group of identical rooms, concrete numbers later.
            room_opts={}
            for r in [r for r in rooms_for(data,e,part) if room_group_of[r['id']]==r['id']]:
                rid=r['id']; group=room_group_of[rid]; choice=m.new_bool_var(f'rooms_{ei}_{pi}_{rid}'); room_opts[rid]=choice
                penalties.append(choice*max(0,part['size']-r['recommended'])*weight('merge'))
                room_intervals[group].append(m.new_optional_fixed_size_interval_var(starts[eid],1,choice,f'room_{ei}_{pi}_{rid}'))
                for s in unavailable['rooms',rid]:
                    if s in at[eid]: m.add(choice+at[eid][s]<=1)
                # Room wishes need a slot level conjunction, so it is built only for
                # the slots that actually carry a wish.
                for s,v in at[eid].items():
                    av=availability(r,s,stride)
                    if av not in ('undesirable','preferred'): continue
                    used=conjunction(choice,v,f'roomat_{ei}_{pi}_{rid}_{s}')
                    penalties.append(used*weight('availability')*(4 if av=='undesirable' else -1))
            m.add(sum(room_opts.values())==present[eid]); selections[eid,pi,'rooms']=room_opts
            # Teachers. A single candidate is implied by the presence of the event.
            teacher_candidates=teachers_for(data,e,part); teacher_opts={}; sole=len(teacher_candidates)==1
            for t in teacher_candidates:
                rid=t['id']; choice=m.new_bool_var(f'teachers_{ei}_{pi}_{rid}'); teacher_opts[rid]=choice
                resources['teachers',rid].append(m.new_optional_fixed_size_interval_var(starts[eid],1,choice,f'i_teachers_{ei}_{pi}_{rid}'))
                if not any(q['subject_id']==e['subject_id'] and q['level']=='primary' for q in t['qualifications']): penalties.append(choice*weight('qualification'))
                for day,dv in enumerate(dayvars):
                    tv=conjunction(choice,dv,f'td_{ei}_{pi}_{rid}_{day}'); teaching[rid,day].append(tv); td_terms[eid,pi,rid,day]=tv
                    if t['method_day']==day: penalties.append(tv*weight('method_day'))
                for s,v in at[eid].items():
                    # With a single candidate the event presence already implies the
                    # assignment; the interval has to stay slot specific.
                    occupied=v if sole else conjunction(choice,v,f'ts_{ei}_{pi}_{rid}_{s}')
                    teacher_slots[rid,s].append(occupied)
                    av=availability(t,s,stride)
                    if av in ('undesirable','preferred'): penalties.append(occupied*weight('availability')*(4 if av=='undesirable' else -1))
            m.add(sum(teacher_opts.values())==present[eid]); selections[eid,pi,'teachers']=teacher_opts
        if eid in old:
            l=old[eid]
            if l.get('lock')=='locked':
                m.add(present[eid]==1); m.add(starts[eid]==l['slot'])
                for pi,part in enumerate(l['parts']):
                    for kind,field in [('teachers','teacher_id'),('rooms','room_id')]:
                        rid=room_group_of.get(part[field],part[field]) if kind=='rooms' else part[field]
                        m.add(selections.get((eid,pi,kind),{}).get(rid,0)==1)
            else:
                # Stability covers every unlocked lesson of the source version, not
                # only explicit wishes; an explicit wish weighs more.
                multiplier=3 if l.get('lock')=='preferred' else 1
                if 'slot' in l:
                    if l['slot'] in at[eid]:
                        penalties.append((present[eid]-at[eid][l['slot']])*weight('stability')*multiplier); m.add_hint(at[eid][l['slot']],1)
                    else: penalties.append(present[eid]*weight('stability')*multiplier)
                for pi,part in enumerate(l.get('parts',[])):
                    for kind,key in [('teachers','teacher_id'),('rooms','room_id')]:
                        wanted=room_group_of.get(part.get(key),part.get(key))
                        for rid,var in selections.get((eid,pi,kind),{}).items(): m.add_hint(var,int(rid==wanted))
        elif eid in hints:
            hint=hints[eid];m.add_hint(present[eid],1);m.add_hint(starts[eid],hint['slot'])
            for s,v in at[eid].items():m.add_hint(v,int(s==hint['slot']))
            for pi,p in enumerate(hint['parts']):
                for kind,key in [('teachers','teacher_id'),('rooms','room_id')]:
                    wanted=room_group_of[p[key]] if kind=='rooms' else p[key]
                    for rid,var in selections[eid,pi,kind].items():m.add_hint(var,int(rid==wanted))
    for intervals in resources.values(): m.add_no_overlap(intervals)
    for group,intervals in room_intervals.items(): m.add_cumulative(intervals,[1]*len(intervals),len(room_groups[group]))
    for c in data['classes']:
        cid=c['id']; ces=class_events[cid]
        planned=Counter(e['subject_id'] for e in ces if e['active'])
        class_hours=sum(planned.values())
        # Идеальная раскладка недельных часов по дням. Сумма модулей отклонения
        # по пяти дням равна extra + 2*недобор, поэтому одна цель одновременно
        # запрещает пустые учебные дни и перегруженные дни. При недельных часах
        # меньше пяти сумма постоянна, слагаемые не создаются.
        day_base=class_day_base(class_hours)
        planned_tests=sum(1 for e in ces if e['active'] and e['kind']=='test')
        hard_subjects={e['subject_id'] for e in ces if is_hard(ix['subjects'][e['subject_id']])}
        ideal_bounds=class_hours>=5
        subject_days=defaultdict(list); test_days=[]
        for day in range(5):
            occupied=[]; subjectslots=defaultdict(dict); testvars=[]
            for slot in range(stride):
                s=day*stride+slot; vs=[at[e['id']][s] for e in ces if s in at[e['id']]]
                o=m.new_bool_var(f'c_{cid}_{s}'); m.add(sum(vs)==o); occupied.append(o)
                for sid in {e['subject_id'] for e in ces}:
                    sv=m.new_bool_var(f'cs_{cid}_{sid}_{s}'); m.add(sv==sum(at[e['id']].get(s,0) for e in ces if e['subject_id']==sid)); subjectslots[sid][slot]=sv
                testvars.append(sum(at[e['id']].get(s,0) for e in ces if e['kind']=='test'))
            m.add_automaton(occupied,0,[0,1,2],[(0,0,0),(0,1,1),(1,1,1),(1,0,2),(2,0,2)])
            m.add(sum(occupied)<=limits(data,'daily_max',c['grade'],8)); m.add(sum(testvars)<=limits(data,'tests_daily',c['grade'],1))
            if ideal_bounds:
                load=sum(occupied)
                deviation=m.new_int_var(0,class_hours,f'loaddev_{cid}_{day}')
                m.add_abs_equality(deviation,load-day_base); balance_terms.append(deviation*weight('distribution'))
                # Жёсткие границы идеальной раскладки [base, base+1]. Если они
                # разрешимы, неделя класса получается заведомо ровной, поэтому
                # модель пробует их отдельной попыткой до общего поиска.
                ideal.append((load,day_base,day_base+1))
            # A test may not open or close the school day of its class, and a hard
            # subject may not be the first or the last lesson of the day.
            for slot in range(stride):
                if slot:
                    z=m.new_bool_var(f'testfirst_{cid}_{day}_{slot}'); m.add(z>=testvars[slot]-sum(occupied[:slot])); penalties.append(z*weight('difficulty'))
                    hard=sum(subjectslots[sid][slot] for sid in hard_subjects)
                    z=m.new_bool_var(f'hardfirst_{cid}_{day}_{slot}'); m.add(z>=hard-sum(occupied[:slot])); penalties.append(z*weight('difficulty'))
                if slot<stride-1:
                    z=m.new_bool_var(f'testlast_{cid}_{day}_{slot}'); m.add(z>=testvars[slot]-sum(occupied[slot+1:])); penalties.append(z*weight('difficulty'))
                    hard=sum(subjectslots[sid][slot] for sid in hard_subjects)
                    z=m.new_bool_var(f'hardlast_{cid}_{day}_{slot}'); m.add(z>=hard-sum(occupied[slot+1:])); penalties.append(z*weight('difficulty'))
            for sid,ss in subjectslots.items():
                m.add(sum(ss.values())<=2)
                repeat=m.new_int_var(0,1,f'repeat_{cid}_{day}_{sid}'); m.add_max_equality(repeat,[sum(ss.values())-1,0]); penalties.append(repeat*weight('distribution'))
                if not ix['subjects'][sid]['double_allowed']:
                    for slot in range(stride-1): m.add(ss[slot]+ss[slot+1]<=1)
                used=m.new_bool_var(f'used_{cid}_{sid}_{day}'); m.add_max_equality(used,list(ss.values())); subject_days[sid].append(used)
            used=m.new_bool_var(f'testday_{cid}_{day}'); m.add_max_equality(used,testvars); test_days.append(used)
            for slot in range(stride-1):
                pe=sum(ss[slot] for sid,ss in subjectslots.items() if ix['subjects'][sid]['pe'])
                m.add(pe+testvars[slot+1]<=1); m.add(testvars[slot]+testvars[slot+1]<=1)
                hard_next=sum(ss[slot+1] for sid,ss in subjectslots.items() if is_hard(ix['subjects'][sid]))
                z=m.new_bool_var(f'fatigue_{cid}_{day}_{slot}'); m.add(z>=pe+hard_next-1); penalties.append(z*weight('difficulty'))
            for slot in range(stride-2):
                hard=sum(ss[q] for sid,ss in subjectslots.items() if is_hard(ix['subjects'][sid]) for q in range(slot,slot+3))
                z=m.new_bool_var(f'threehard_{cid}_{day}_{slot}'); m.add(z>=hard-2); penalties.append(z*weight('difficulty'))
        # Spread every subject, and the control works, over as many weekdays as the
        # plan allows: three hours in three days beat "two plus one".
        # Inequalities keep the counting variables satisfiable by construction while
        # the minimal value still matches what score() reports.
        for sid,hours in planned.items():
            deficit=m.new_int_var(0,5,f'spread_{cid}_{sid}'); m.add(deficit>=min(hours,5)-sum(subject_days[sid])); penalties.append(deficit*weight('distribution'))
        if planned_tests:
            deficit=m.new_int_var(0,5,f'testspread_{cid}'); m.add(deficit>=min(planned_tests,5)-sum(test_days)); penalties.append(deficit*weight('distribution'))
    for t in data['teachers']:
        teacher_gaps=[]
        total=sum(v for day in range(5) for v in teaching[t['id'],day]); m.add(total<=t['maximum'])
        delta=m.new_int_var(0,40,f'load_{t["id"]}'); m.add_abs_equality(delta,total-t['target']); penalties.append(delta*weight('teacher_load'))
        fair=max(1,-(-t['target']//5))
        for day in range(5):
            count=sum(teaching[t['id'],day]); m.add(count<=t['daily_hard'])
            excess=m.new_int_var(0,8,f'excess_{t["id"]}_{day}'); m.add_max_equality(excess,[0,count-t['daily_soft']]); penalties.append(excess*weight('teacher_load'))
            # Fairness between days: no day may carry more than its equal share.
            uneven=m.new_int_var(0,8,f'fair_{t["id"]}_{day}'); m.add_max_equality(uneven,[0,count-fair]); penalties.append(uneven*weight('teacher_load'))
            occupied=[]
            for slot in range(stride):
                v=m.new_bool_var(f'teacher_slot_{t["id"]}_{day}_{slot}');m.add(v==sum(teacher_slots[t['id'],day*stride+slot]));occupied.append(v)
            for slot in range(1,stride-1):
                before=m.new_bool_var(f'before_{t["id"]}_{day}_{slot}');after=m.new_bool_var(f'after_{t["id"]}_{day}_{slot}')
                m.add_max_equality(before,occupied[:slot]);m.add_max_equality(after,occupied[slot+1:])
                gap=m.new_bool_var(f'gap_{t["id"]}_{day}_{slot}');m.add(gap>=before+after-occupied[slot]-1);teacher_gaps.append(gap);penalties.append(gap*weight('teacher_gaps'))
            for slot in range(stride-t['consecutive']):
                excess=m.new_bool_var(f'consecutive_{t["id"]}_{day}_{slot}');m.add(excess>=sum(occupied[slot:slot+t['consecutive']+1])-t['consecutive']);penalties.append(excess*weight('consecutive'))
        gaps=m.new_int_var(0,5*stride,f'gaps_{t["id"]}');m.add(gaps==sum(teacher_gaps));gap_totals.append(gaps)
    if gap_totals:
        worst=m.new_int_var(0,5*stride,'worst_teacher_gaps');m.add_max_equality(worst,gap_totals);penalties.append(worst*weight('teacher_gaps'))
    # Room discipline: a teacher keeps one room group per working day and stays in
    # the personal base room. Identical rooms are interchangeable, so this works on
    # signatures, not on concrete numbers; score() reports the same two terms.
    continuity=weight('room_changes')
    if continuity:
        for t in data['teachers']:
            tid=t['id']; base=signature_of.get(t['base_room'])
            buckets=defaultdict(list)
            for (eid,pi,owner,day),tv in td_terms.items():
                if owner!=tid: continue
                for group,choice in selections.get((eid,pi,'rooms'),{}).items(): buckets[day,signature_of[group]].append((tv,choice))
            # Swapping between identical rooms is not a change, so a teacher who can
            # only ever reach one kind of room needs no terms at all.
            kinds=sorted({group for _,group in buckets}); position={group:i for i,group in enumerate(kinds)}
            if len(kinds)<2 and base not in position: continue
            per_day=defaultdict(list)
            for (day,group),terms in sorted(buckets.items(),key=lambda x:(x[0][0],position[x[0][1]])):
                used=m.new_int_var(0,1,f'rg_{tid}_{day}_{position[group]}')
                for tv,choice in terms: m.add(used>=tv+choice-1)
                per_day[day].append(used)
                if base and group!=base: penalties.append(used*continuity)
            for day,groups in sorted(per_day.items()):
                if len(groups)<2: continue
                many=m.new_int_var(0,len(groups)-1,f'rgd_{tid}_{day}'); m.add(many>=sum(groups)-1); penalties.append(many*continuity)
    for e in es:
        if e['ordinal']>0:
            before=e['id'].rsplit(':',1)[0]+f':{e["ordinal"]-1}'
            m.add(starts[e['id']]>starts[before]).only_enforce_if([present[e['id']],present[before]])
            # Omit later topics first when a partial result is necessary.
            if not any(old.get(k,{}).get('lock')=='locked' for k in [before,e['id']]): m.add(present[e['id']]<=present[before])
        if e['pair_required'] and e['ordinal']%2==0:
            a=e['id']; b=a.rsplit(':',1)[0]+f':{e["ordinal"]+1}'
            m.add(present[a]==present[b]); m.add(starts[b]==starts[a]+1).only_enforce_if(present[a])
            # The second lesson must stay in the same day, inside the grid of its
            # own class and shift: a pair never crosses a day or a shift boundary.
            for s,v in at[a].items():
                if (s+1)//stride!=s//stride or s+1 not in at[b]: m.add(v==0)
            for pi in range(len(e['parts'])):
                for kind in ['teachers','rooms']:
                    for rid,v in selections[a,pi,kind].items(): m.add(v==selections[b,pi,kind].get(rid,0))
    soft=sum(penalties)
    balance=sum(balance_terms)
    # Objective of last resort: dropping a mandatory lesson always costs more than
    # every soft wish together. Only used when no complete timetable exists.
    m.minimize(sum((1-p)*MISSING_WEIGHT for p in present.values())+soft+balance)
    partial=m.clone()
    for e in required: m.add(present[e['id']]==1)
    m.clear_objective()
    solver.parameters.random_seed=seed; solver.parameters.num_search_workers=8
    solver.parameters.log_search_progress=os.getenv('SOLVER_LOG')=='1'
    if cancel and cancel.is_set(): return {'status':'cancelled','lessons':[],'errors':[],'elapsed':time.monotonic()-started}
    def hint_from(source):
        m.clear_hints()
        for e in es:
            eid=e['id']; m.add_hint(starts[eid],source.value(starts[eid]))
            for pi in range(len(e['parts'])):
                for kind in ('teachers','rooms'):
                    for var in selections[eid,pi,kind].values(): m.add_hint(var,source.value(var))
    first_solver=None; optimizing=False
    # Попытка идеальной раскладки идёт первой: перестановки, выравнивающие неделю,
    # в общем поиске почти никогда не выбираются, потому что каждая из них
    # ухудшает какое-нибудь другое пожелание. Если жёсткие границы разрешимы,
    # расписание получается ровным сразу; если нет — работает мягкая цель.
    # В большой школе границы почти наверняка неразрешимы, и попытка съела бы
    # интерактивный бюджет, поэтому она ограничена размером школы.
    if ideal and seconds>=2 and len(es)<=IDEAL_PROBE_MAX_EVENTS:
        ideal_model=m.clone()
        for expr,floor,ceiling in ideal:
            ideal_model.add(expr>=floor); ideal_model.add(expr<=ceiling)
        probe=cp_model.CpSolver()
        probe.parameters.random_seed=seed; probe.parameters.num_search_workers=8
        probe.parameters.cp_model_probing_level=0; probe.parameters.symmetry_level=0
        probe.parameters.max_time_in_seconds=min(IDEAL_PROBE_SECONDS,seconds*.3)
        probe.parameters.stop_after_first_solution=True
        if solver_ready: solver_ready(probe)
        if probe.solve(ideal_model) in (cp_model.FEASIBLE,cp_model.OPTIMAL):
            for expr,floor,ceiling in ideal:
                m.add(expr>=floor); m.add(expr<=ceiling)
            first_solver=probe; solver=probe; status=cp_model.FEASIBLE
    if not first_solver:
        # Phase 1 places every mandatory lesson. Optimising the wishes right away spends
        # the interactive budget on omission combinations instead of finishing the grid.
        # It keeps a real share of the budget because presolving a large school already
        # costs a noticeable part of it.
        phase1=max(.05,min(4.,seconds*.45)) if len(es)<=IDEAL_PROBE_MAX_EVENTS else seconds*.6
        solver.parameters.cp_model_probing_level=0
        solver.parameters.symmetry_level=0
        solver.parameters.max_time_in_seconds=phase1
        solver.parameters.stop_after_first_solution=True
        status=solver.solve(m)
        first_solver=solver if status in (cp_model.FEASIBLE,cp_model.OPTIMAL) else None
    if first_solver:
        # Phase 2 keeps the complete grid and minimises the weighted wishes.
        m.minimize(soft); optimizing=True; hint_from(first_solver)
    else: m=partial
    # Phase 2a levels the weekly hours of every class over the days: rearranging a
    # grid is a long sequence of swaps, and among the other wishes those swaps are
    # never chosen.
    elapsed=time.monotonic()-started
    if first_solver and not ideal and balance_terms and seconds-elapsed>1.5:
        m.clear_objective(); m.minimize(balance)
        level=cp_model.CpSolver()
        level.parameters.copy_from(solver.parameters)
        if solver_ready: solver_ready(level)
        level.parameters.stop_after_first_solution=False
        level.parameters.max_time_in_seconds=(seconds-elapsed)*.55
        if level.solve(m) in (cp_model.OPTIMAL,cp_model.FEASIBLE): hint_from(level)
        m.clear_objective(); m.minimize(soft)
    remaining=seconds-(time.monotonic()-started)
    if remaining>.1 and not(cancel and cancel.is_set()):
        runner=cp_model.CpSolver()
        if first_solver: runner.parameters.copy_from(solver.parameters)
        if solver_ready: solver_ready(runner)
        runner.parameters.stop_after_first_solution=False
        runner.parameters.max_time_in_seconds=remaining
        final=runner.solve(m)
        if final in (cp_model.OPTIMAL,cp_model.FEASIBLE): solver=runner; status=final
        elif first_solver: solver=first_solver; status=cp_model.FEASIBLE
    elif first_solver: solver=first_solver; status=cp_model.FEASIBLE
    lessons=[]
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        for e in es:
            eid=e['id']
            if solver.value(present[eid]):
                parts=[]
                for pi in range(len(e['parts'])):
                    parts.append({field:next(r for r,v in selections[eid,pi,kind].items() if solver.value(v)) for kind,field in [('teachers','teacher_id'),('rooms','room_id')]})
                lessons.append({'id':eid,'slot':solver.value(starts[eid]),'parts':parts,'lock':old.get(eid,{}).get('lock','free'),'origin':'generator'})
    # Concrete room numbers. Preference order: manual lock, the room of the source
    # version, the room the teacher already uses that day, the base room of the
    # teacher, the room the class already uses that day, then the lowest free id.
    used_rooms=defaultdict(set); last_room={}; class_room={}
    for l in sorted(lessons,key=lambda l:(l['lock']!='locked',l['slot'],l['id'])):
        day=l['slot']//stride
        for pi,p in enumerate(l['parts']):
            candidates=room_groups[p['room_id']]
            wanted=old.get(l['id'],{}).get('parts',[{}]*len(l['parts']))[pi].get('room_id')
            if not wanted: wanted=last_room.get((p['teacher_id'],day)) or ix['teachers'][p['teacher_id']]['base_room']
            if not wanted: wanted=next((class_room.get((cid,day)) for cid in class_of_event.get(l['id'],[]) if class_room.get((cid,day))),None)
            if wanted in candidates and wanted not in used_rooms[l['slot']]: rid=wanted
            else: rid=next((r for r in candidates if r not in used_rooms[l['slot']]),None)
            if rid is not None:
                p['room_id']=rid; used_rooms[l['slot']].add(rid); last_room[p['teacher_id'],day]=rid
                for cid in class_of_event.get(l['id'],[]): class_room[cid,day]=rid
    # A warm start is only a fallback when independently validated; CP-SAT remains
    # the search engine and can improve/reassign every non-locked event.
    if len(warm)>len(lessons): lessons=warm
    missing=[e for e in required if e['id'] not in {l['id'] for l in lessons}]
    locked={eid:l for eid,l in old.items() if l.get('lock')=='locked'}
    errors=validate_schedule(data,lessons,week,False,locked) if lessons else []
    if errors: lessons=[]
    return {'status':'cancelled' if cancel and cancel.is_set() else 'invalid' if errors else 'complete' if lessons and not missing else 'partial' if lessons else 'infeasible' if status in (cp_model.INFEASIBLE,cp_model.OPTIMAL) else 'timeout',
        'lessons':lessons,'missing':[e['id'] for e in missing], 'diagnostics':diagnose(data,missing,week), 'capacity_issues':capacity_issues(data,week) if missing else [], 'errors':errors,
        'elapsed':round(time.monotonic()-started,3),'solver_version':ortools.__version__,'seed':seed,'quality':score(data,lessons,week,previous), 'optimal':optimizing and status==cp_model.OPTIMAL}
