from .domain import *
from .norms import RANK_POINTS, difficulty

def demo_data(large=False):
    d=empty_data(); d['settings']['school']='Школа «Горизонт»'; d['settings']['confirmed']=True
    def add(kind,**kw):
        obj=MODELS[kind](**kw).model_dump(mode='json'); d[kind].append(obj); return obj
    # Сложность предметов — приложение 4 к СП № ҚР ДСМ-76, переведённое в шкалу
    # проекта `backend.norms.difficulty`. Часы подобраны так, чтобы облегчающие
    # предметы могли закрывать первые и последние уроки дня: сложные предметы не
    # ставятся на края дня, а на пять дней нужно не меньше десяти таких уроков.
    subjects=[('math','Математика',4,False),('russian','Русский язык',4,False),('kazakh','Казахский язык',3,False),('english','Английский язык',3,False),('history','История',4,False),('science','Естествознание',4,False),('pe','Физкультура',4,True)]
    for sid,name,hours,pe in subjects: add('subjects',id=sid,name=name,difficulty=difficulty(RANK_POINTS[sid]),pe=pe,merge_allowed=True,tags=['gym'] if pe else [])
    count=28 if large else 4
    for i in range(60 if large else 12):
        # Two subject qualifications give real alternatives without a dense all-to-all graph.
        add('teachers',id=f't{i}',name=f'Преподаватель {i+1:02}',qualifications=[{'subject_id':subjects[i%7][0],'level':'primary'},{'subject_id':subjects[(i+1)%7][0],'level':'acceptable'}],target=24,maximum=35)
    for i in range(35 if large else 6): add('rooms',id=f'r{i}',name=f'{101+i}',tags=['gym'] if i>= (30 if large else 5) else ['projector','lab','pc'],recommended=24,absolute=27)
    for i in range(count):
        grade=5+i//4; language='kk' if i%4>=2 else 'ru'; cid=f'c{i}'
        add('classes',id=cid,name=f'{grade}{"АБВГ"[i%4]}',grade=grade,letter='АБВГ'[i%4],language=language,size=21 if i<16 else 22)
        for j,(sid,name,hours,__) in enumerate(subjects):
            course=f'{sid}-{grade}-{language}'
            if not any(c['id']==course for c in d['courses']): add('courses',id=course,name=f'{name} · {grade} · {language}',subject_id=sid,grade=grade,language=language)
            pool=[t['id'] for t in d['teachers'] if any(q['subject_id']==sid and q['level']=='primary' for q in t['qualifications'])]
            tid=pool[(i//2)%len(pool)]
            add('plans',id=f'p{i}-{sid}',name=f'{grade}{"АБВГ"[i%4]} · {name}',class_id=cid,course_id=course,hours=hours,teacher_ids=[tid],merge_allowed=True)
    return d
