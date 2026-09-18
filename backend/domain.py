"""Typed input contract and cross-record validation, shared by every write path."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from . import norms

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    @field_validator('*', mode='before')
    @classmethod
    def safe_text(cls,value):
        def check(v):
            if isinstance(v,str) and any(ord(ch)<32 and ch not in '\n\r\t' for ch in v): raise ValueError('Недопустимый управляющий символ в тексте')
            if isinstance(v,list):
                for item in v:check(item)
        check(value)
        return value

class Record(Strict):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160, title='Название')
    active: bool = Field(True, title='Активен')

class Availability(Strict):
    day: int = Field(ge=0, le=4, title='День недели')
    slot: int = Field(ge=0, le=15, title='Позиция в сетке звонков (с нуля)')
    value: Literal['unavailable','undesirable','possible','preferred'] = 'unavailable'

class SchoolClass(Record):
    shift: int = Field(1, ge=1, le=2, title='Смена')
    grade: int = Field(5, ge=5, le=11, title='Параллель')
    letter: str = Field('А', min_length=1, max_length=3, title='Буква')
    language: Literal['ru','kk'] = Field('ru', title='Язык потока')
    size: int = Field(20, ge=1, le=100, title='Учеников')
    level: str = Field('Базовый', title='Профиль')
    accessible: bool = Field(False, title='Есть маломобильные ученики')
    availability: list[Availability] = Field(default_factory=list, title='Доступность')

class Group(Record):
    class_id: str = Field(title='Класс')
    size: int = Field(10, ge=1, le=100, title='Учеников')
    purpose: str = Field('', title='Назначение')
    language: Literal['ru','kk'] = Field('ru', title='Язык')
    level: str = Field('Базовый', title='Уровень')
    synchronous: bool = Field(True, title='Синхронное занятие')

class Qualification(Strict):
    subject_id: str = Field(title='Предмет')
    level: Literal['primary','acceptable','emergency'] = Field('primary', title='Квалификация')

class Teacher(Record):
    qualifications: list[Qualification] = Field(default_factory=list, title='Квалификации')
    contract: int = Field(18, ge=0, le=40, title='Договорная нагрузка')
    target: int = Field(25, ge=0, le=40, title='Целевая нагрузка')
    maximum: int = Field(35, ge=1, le=40, title='Максимум в неделю')
    daily_soft: int = Field(6, ge=1, le=8, title='Желательно уроков в день')
    daily_hard: int = Field(7, ge=1, le=8, title='Максимум уроков в день')
    consecutive: int = Field(3, ge=1, le=8, title='Желательно уроков подряд')
    base_room: str = Field('', title='Базовый кабинет')
    method_day: int = Field(-1, ge=-1, le=4, title='Методический день (−1 — нет)')
    method_hard: bool = Field(False, title='Методический день обязателен')
    overtime: int = Field(0, ge=0, le=10, title='Допустимые сверхурочные часы (для предложений)')
    availability: list[Availability] = Field(default_factory=list, title='Доступность')

    @model_validator(mode='after')
    def limits(self):
        if self.target > self.maximum or self.daily_soft > self.daily_hard:
            raise ValueError('Целевая нагрузка не может превышать жёсткий максимум')
        return self

class Room(Record):
    floor: int = Field(1, ge=1, le=20, title='Этаж')
    recommended: int = Field(25, ge=1, le=200, title='Рекомендуемая вместимость')
    absolute: int = Field(28, ge=1, le=200, title='Сертифицированная вместимость')
    tags: list[str] = Field(default_factory=list, title='Оборудование')
    subjects: list[str] = Field(default_factory=list, title='Разрешённые предметы (пусто — любые)')
    teacher_id: str = Field('', title='Закреплённый преподаватель')
    availability: list[Availability] = Field(default_factory=list, title='Доступность')

    @model_validator(mode='after')
    def capacity(self):
        if self.recommended > self.absolute:
            raise ValueError('Рекомендуемая вместимость выше сертифицированной')
        return self

class Subject(Record):
    difficulty: int = Field(5, ge=1, le=10, title='Сложность (1–10)')
    pe: bool = Field(False, title='Физкультура')
    merge_allowed: bool = Field(False, title='Можно объединять')
    double_allowed: bool = Field(False, title='Можно сдваивать')
    tags: list[str] = Field(default_factory=list, title='Обязательное оборудование')

class Course(Record):
    subject_id: str = Field(title='Предмет')
    grade: int = Field(5, ge=5, le=11, title='Параллель')
    language: Literal['ru','kk'] = Field('ru', title='Язык')
    program: str = Field('Основная', title='Программа')
    version: str = Field('1', title='Версия программы')
    level: str = Field('Базовый', title='Уровень')
    topics: list[str] = Field(default_factory=list, title='Темы (пусто — нумерация)')

class Part(Strict):
    group_id: str = Field(title='Подгруппа')
    teacher_ids: list[str] = Field(min_length=1, title='Основной и альтернативные учителя')

class Plan(Record):
    class_id: str = Field(title='Класс')
    course_id: str = Field(title='Курс')
    hours: int = Field(3, ge=1, le=40, title='Часов в неделю')
    teacher_ids: list[str] = Field(default_factory=list, title='Основной и альтернативные учителя')
    kind: Literal['normal','lab','test','groups'] = Field('normal', title='Тип занятия')
    parts: list[Part] = Field(default_factory=list, title='Состав подгрупп')
    pair_required: bool = Field(False, title='Обязательная пара')
    tags: list[str] = Field(default_factory=list, title='Оборудование')
    merge_allowed: bool = Field(False, title='Можно объединять')
    topic: int = Field(1, ge=1, le=10000, title='Текущая тема')

class Merge(Record):
    plan_ids: list[str] = Field(min_length=2, max_length=4, title='Строки плана')
    week: str = Field('', title='Неделя (пусто — постоянно)')

class ExceptionDay(Record):
    start: date = Field(title='Начало')
    end: date = Field(title='Окончание')
    scope: Literal['school','classes','teachers','rooms'] = Field('school', title='Ресурс')
    resource_id: str = Field('', title='Объект')
    slots: list[int] = Field(default_factory=list, title='Уроки с нуля (пусто — весь день)')
    @model_validator(mode='after')
    def dates(self):
        if self.end < self.start or any(x < 0 or x > 15 for x in self.slots):
            raise ValueError('Проверьте даты и номера уроков')
        return self

class Period(Record):
    start: date = Field(title='Начало')
    end: date = Field(title='Окончание')
    @model_validator(mode='after')
    def dates(self):
        if self.end < self.start: raise ValueError('Окончание раньше начала')
        return self

class Rule(Record):
    key: Literal['lesson_minutes','break_minutes','daily_max','weekly_max','tests_daily','first_shift','availability','teacher_gaps','teacher_load','consecutive','method_day','difficulty','distribution','room_changes','qualification','merge','stability'] = Field(title='Правило')
    version: str = Field('1', title='Версия')
    source: str = Field('Локальное правило школы', title='Источник')
    effective: date = Field(default_factory=date.today, title='Дата действия')
    grade: int = Field(0, ge=0, le=11, title='Параллель (0 — все)')
    kind: Literal['hard','soft','informational'] = Field('hard', title='Тип')
    value: int = Field(7, ge=0, le=1000, title='Значение')
    unit: str = Field('уроков', title='Единица')
    priority: Literal['low','medium','high','critical'] = Field('medium', title='Приоритет')
    comment: str = Field('', title='Комментарий')

    @model_validator(mode='after')
    def supported_kind(self):
        hard_keys={'lesson_minutes','break_minutes','daily_max','weekly_max','tests_daily','first_shift'}
        if self.kind=='hard' and self.key not in hard_keys: raise ValueError('Это пожелание решателя. Выберите мягкое правило и его приоритет')
        if self.kind=='soft' and self.key in hard_keys: raise ValueError('Для этого норматива выберите обязательное или справочное правило')
        if self.key in {'lesson_minutes','break_minutes','daily_max','weekly_max'} and self.value<1: raise ValueError('Норматив должен быть положительным')
        if self.key=='daily_max' and self.value>8: raise ValueError('В MVP не более восьми уроков в день')
        if self.key=='lesson_minutes' and self.value>45: raise ValueError('Продолжительность урока не более 45 минут')
        if self.key=='break_minutes' and self.value<5: raise ValueError('Обычная перемена не короче пяти минут')
        if self.key=='first_shift' and self.value>1: raise ValueError('Признак «только первая смена» включается единицей или отключается нулём')
        if self.kind=='soft' and self.grade!=0: raise ValueError('Пожелания решателя применяются ко всей школе: укажите параллель 0')
        return self

class Bell(Strict):
    shift: int = Field(1, ge=1, le=2, title='Смена')
    start: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$', title='Начало')
    end: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$', title='Конец')

def default_bells():
    result, minute = [], 480
    for i in range(8):
        result.append(Bell(start=f'{minute//60:02}:{minute%60:02}', end=f'{(minute+45)//60:02}:{(minute+45)%60:02}'))
        minute += 45 + (15 if i in [1,3] else 5)
    return result

class Settings(Strict):
    school: str = Field('Моя школа', min_length=1, max_length=160, title='Название школы')
    year_start: date = Field(date(2026,9,1), title='Начало учебного года')
    year_end: date = Field(date(2027,5,31), title='Конец учебного года')
    confirmed: bool = Field(False, title='Недельные нормативы проверены ответственным сотрудником')
    normative_date: date = Field(default_factory=date.today, title='Дата применимого нормативного профиля')
    accessible_floors: list[int] = Field(default_factory=lambda:[1], title='Доступные этажи')
    bells: list[Bell] = Field(default_factory=default_bells, min_length=5, max_length=16, title='Звонки')

def slot_stride(data):
    # Retain the original encoding for existing one-shift snapshots.
    return max(8, len(data['settings']['bells']))

def class_slots(data, school_class):
    return [i for i,b in enumerate(data['settings']['bells']) if b.get('shift',1)==school_class.get('shift',1)]

def bell_label(data, slot):
    bells=data['settings']['bells']; shift=bells[slot].get('shift',1)
    number=sum(b.get('shift',1)==shift for b in bells[:slot+1])
    return f'{shift} смена · {number} урок'

MODELS = {'classes':SchoolClass,'groups':Group,'teachers':Teacher,'rooms':Room,'subjects':Subject,'courses':Course,'plans':Plan,'merges':Merge,'exceptions':ExceptionDay,'periods':Period,'rules':Rule}

def applicable_rules(data):
    as_of=data['settings'].get('normative_date',date.today().isoformat())
    return [r for r in data['rules'] if r['active'] and r['effective']<=as_of]

def limits(data, key, grade=0, fallback=1000):
    values = [r['value'] for r in applicable_rules(data) if r['key']==key and r['kind']=='hard' and r['grade'] in (0,grade)]
    return (max(values) if key=='break_minutes' else min(values)) if values else fallback

def requires_first_shift(data, grade):
    """True, когда профиль норм требует для параллели только первую смену.

    Правило-признак нельзя свести к `limits()`: у него не минимум, а приоритет
    более конкретной записи. Запись для параллели важнее общей, поэтому школу
    можно перевести на первую смену целиком (`grade=0`) или отключить норму для
    отдельной параллели (`value=0`).
    """
    rows=[r for r in applicable_rules(data) if r['key']=='first_shift' and r['kind']=='hard' and r['grade'] in (0,grade)]
    specific=[r for r in rows if r['grade']==grade]
    chosen=max(specific or rows,key=lambda r:r['value'],default=None)
    return bool(chosen and chosen['value']>=1)

def class_slots_for_shift(data, shift):
    return [i for i,b in enumerate(data['settings']['bells']) if b.get('shift',1)==shift]

def validate_data(data):
    errors = []
    index = {kind:{r['id']:r for r in data[kind]} for kind in MODELS}
    def ref(kind, rid, label):
        r = index[kind].get(rid)
        if not r: errors.append(f'{label}: объект не найден')
        return r
    for kind in MODELS:
        if len(index[kind]) != len(data[kind]): errors.append(f'{kind}: повторяющиеся идентификаторы')
    for g in data['groups']: ref('classes',g['class_id'],g['name'])
    for t in data['teachers']:
        for q in t['qualifications']: ref('subjects',q['subject_id'],t['name'])
        if t['base_room']: ref('rooms',t['base_room'],t['name'])
    for r in data['rooms']:
        for sid in r['subjects']: ref('subjects',sid,r['name'])
        if r['teacher_id']: ref('teachers',r['teacher_id'],r['name'])
    for c in data['courses']: ref('subjects',c['subject_id'],c['name'])
    if errors:return list(dict.fromkeys(errors))
    for p in data['plans']:
        c, course = ref('classes',p['class_id'],p['name']), ref('courses',p['course_id'],p['name'])
        if c and course and any(c[k]!=course[k] for k in ['grade','language','level']): errors.append(f'{p["name"]}: курс не соответствует параллели, языку или уровню класса')
        for tid in p['teacher_ids']: ref('teachers',tid,p['name'])
        if p['kind']=='groups':
            groups = [ref('groups',part['group_id'],p['name']) for part in p['parts']]
            if len(groups)<2 or len({g['id'] for g in groups if g})!=len(groups): errors.append(f'{p["name"]}: нужны разные подгруппы')
            if c and all(groups) and (sum(g['size'] for g in groups)!=c['size'] or any(g['class_id']!=c['id'] for g in groups)): errors.append(f'{p["name"]}: подгруппы должны полностью покрывать свой класс')
            for part in p['parts']:
                for tid in part['teacher_ids']: ref('teachers',tid,p['name'])
        elif not p['teacher_ids']: errors.append(f'{p["name"]}: укажите преподавателя')
        if p['pair_required'] and (p['hours']%2 or (course and not index['subjects'][course['subject_id']]['double_allowed'])): errors.append(f'{p["name"]}: пара требует чётного числа часов и разрешения предмета')
    if errors:return list(dict.fromkeys(errors))
    occupied = set()
    for m in data['merges']:
        ps = [ref('plans',pid,m['name']) for pid in m['plan_ids']]
        if not all(ps): continue
        if len({index['classes'][p['class_id']].get('shift',1) for p in ps})>1: errors.append(f'{m["name"]}: нельзя объединять классы разных смен')
        cs = [index['courses'][p['course_id']] for p in ps]
        keys = ['subject_id','grade','language','program','version','level']
        if (len({p['class_id'] for p in ps})!=len(ps) or any(any(c[k]!=cs[0][k] for k in keys) for c in cs) or
            any(p['topic']!=ps[0]['topic'] or p['hours']!=ps[0]['hours'] or p['kind']!='normal' or not p['merge_allowed'] for p in ps) or not index['subjects'][cs[0]['subject_id']]['merge_allowed']): errors.append(f'{m["name"]}: несовместимые классы, программы, темы или типы уроков')
        # Classes taught together share one teacher, so the merged lines need a
        # common teacher who is allowed to teach the subject.
        common=set(ps[0]['teacher_ids'])
        for p in ps[1:]: common &= set(p['teacher_ids'])
        if not any(t['id'] in common and any(q['subject_id']==cs[0]['subject_id'] and q['level'] in ('primary','acceptable') for q in t['qualifications']) for t in index['teachers'].values()):
            errors.append(f'{m["name"]}: у объединяемых строк нет общего преподавателя с подходящей квалификацией')
        if m['active']:
            for pid in m['plan_ids']:
                if (pid,m['week']) in occupied: errors.append(f'{m["name"]}: строка плана уже объединена')
                occupied.add((pid,m['week']))
        if m['week']:
            try:
                if date.fromisoformat(m['week']).weekday()!=0: raise ValueError()
            except ValueError: errors.append(f'{m["name"]}: неделя должна начинаться в понедельник')
    for e in data['exceptions']:
        if e['scope']!='school': ref(e['scope'],e['resource_id'],e['name'])
    settings = data['settings']
    if settings['year_end'] < settings['year_start']: errors.append('Учебный год: окончание раньше начала')
    def minutes(s): return int(s[:2])*60+int(s[3:])
    bells = settings['bells']
    for i,b in enumerate(bells):
        if not 0 < minutes(b['end'])-minutes(b['start']) <= limits(data,'lesson_minutes',fallback=45): errors.append('Продолжительность урока нарушает норматив')
        if i:
            gap = minutes(b['start'])-minutes(bells[i-1]['end'])
            if gap < limits(data,'break_minutes',fallback=5): errors.append('Перемена короче разрешённой')
    if [b.get('shift',1) for b in bells] != sorted(b.get('shift',1) for b in bells): errors.append('Звонки должны идти по времени: сначала первая смена, затем вторая')
    for shift in sorted({b.get('shift',1) for b in bells}):
        rows=[b for b in bells if b.get('shift',1)==shift]
        if not 5<=len(rows)<=8:
            errors.append(f'Смена {shift}: задайте от 5 до 8 звонков'); continue
        breaks=[minutes(b['start'])-minutes(a['end']) for a,b in zip(rows,rows[1:])]
        if not ((breaks[1]>=30 or breaks[2]>=30) or (breaks[1]>=15 and breaks[3]>=15)): errors.append(f'Смена {shift}: нужна большая перемена — 30 минут после 2/3 урока или 15 минут после 2 и 4')
    for c in data['classes']:
        if c['active'] and not class_slots(data,c): errors.append(f'{c["name"]}: нет звонков для смены {c.get("shift",1)}')
    # Правовое ограничение смены. Класс, для параллели которого профиль норм
    # требует первую смену, не может быть объявлен во второй: перенос решения о
    # смене на решатель запрещён, поэтому данные отклоняются явно.
    for c in data['classes']:
        if c['active'] and c.get('shift',1)!=1 and requires_first_shift(data,c['grade']):
            errors.append(f'{c["name"]}: для {c["grade"]} классов нормой разрешена только первая смена')
    return list(dict.fromkeys(errors))

def empty_data():
    d = {k:[] for k in MODELS}; d['settings']=Settings().model_dump(mode='json')
    for key,val,name,unit in [('lesson_minutes',45,'Длительность урока','минут'),('break_minutes',5,'Минимальная перемена','минут'),('daily_max',8,'Дневной максимум','уроков'),('tests_daily',1,'Контрольных за день','работ')]:
        d['rules'].append(Rule(id=key,name=name,key=key,value=val,unit=unit).model_dump(mode='json'))
    # Профиль норм Республики Казахстан: потолки по параллелям и смены. Значения
    # и источники — в `backend/norms.py`; школу ограничивает флаг подтверждения.
    for row in norms.rules():
        d['rules'].append(Rule(**row).model_dump(mode='json'))
    for key,name,priority in [('availability','Пожелания доступности','high'),('teacher_gaps','Окна преподавателей','high'),('teacher_load','Целевая нагрузка','medium'),('consecutive','Уроки подряд','medium'),('method_day','Методический день','high'),('difficulty','Сложность и утомляемость','medium'),('distribution','Равномерность нагрузки и предметов','medium'),('room_changes','Смена кабинетов','low'),('qualification','Допустимая квалификация','medium'),('merge','Объединение и вместимость','low'),('stability','Сохранение размещения','high')]:
        d['rules'].append(Rule(id=key,name=name,key=key,kind='soft',value=1,unit='приоритет',priority=priority).model_dump(mode='json'))
    return d
