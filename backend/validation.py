"""Readable validation messages without Pydantic's internal English wording."""
from .domain import Settings, MODELS

def validation_message(error):
    kind=error['type']; ctx=error.get('ctx',{})
    if kind=='value_error': return str(ctx.get('error',error['msg'])).removeprefix('Value error, ')
    if kind=='too_long': return f'Допустимо не более {ctx["max_length"]} записей'
    if kind=='too_short': return f'Нужно не менее {ctx["min_length"]} записей'
    if kind=='missing': return 'Заполните обязательное поле'
    if kind=='greater_than_equal': return f'Минимальное значение — {ctx["ge"]}'
    if kind=='less_than_equal': return f'Максимальное значение — {ctx["le"]}'
    if kind=='string_too_short': return f'Введите не менее {ctx["min_length"]} символов'
    if kind=='string_too_long': return f'Введите не более {ctx["max_length"]} символов'
    if kind in ('int_parsing','int_type','int_from_float'): return 'Введите целое число'
    if kind=='extra_forbidden': return 'Неизвестное поле. Обновите страницу'
    if kind in ('literal_error','enum'): return 'Выберите одно из доступных значений'
    if kind.startswith('date_'): return 'Укажите корректную дату'
    if kind=='string_pattern_mismatch': return 'Укажите время в формате ЧЧ:ММ'
    return 'Проверьте значение поля'

def validation_errors(errors):
    titles={key:field.title or key for model in [Settings,*MODELS.values()] for key,field in model.model_fields.items()}
    titles.update(settings='Настройки',start='Начало',end='Конец',shift='Смена',password='Пароль',current='Текущий пароль')
    return [{'field':'.'.join(str(x) for x in e['loc'] if x!='body'),
             'message':(' · '.join(str(x+1) if isinstance(x,int) else titles.get(x,x) for x in e['loc'] if x not in ('body','settings')) or 'Настройки')+': '+validation_message(e)} for e in errors]
