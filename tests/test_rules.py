from backend.domain import limits,Rule,validate_data,Settings
from backend.scheduling import prepare_errors,score
from .test_solver import small

def test_stricter_applicable_rule_and_future_rule():
    d=small();d['settings']['normative_date']='2026-09-18'
    d['rules'].append(Rule(id='strict',name='Строгий предел',key='daily_max',value=6,effective='2026-09-01').model_dump(mode='json'))
    d['rules'].append(Rule(id='future',name='Будущий предел',key='daily_max',value=4,effective='2027-01-01').model_dump(mode='json'))
    assert limits(d,'daily_max',5)==6
    d['settings']['normative_date']='2027-01-02';assert limits(d,'daily_max',5)==4

def test_missing_course_reference_returns_validation_error():
    d=small();d['courses'][0]['subject_id']='missing';assert validate_data(d)

def test_weekly_limit_requires_applicable_confirmation():
    d=small();d['rules']=[r for r in d['rules'] if r['key']!='weekly_max'];assert prepare_errors(d)

def test_bad_bell_duration_is_rejected():
    d=small();d['settings']['bells'][0]['end']='07:59';assert validate_data(d)
