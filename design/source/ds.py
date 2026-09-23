# AI Sana — design tokens + component helpers (source of truth for artboards)
BG='#F4F4F1'; SURF='#FFFFFF'; INK='#1B1C1E'; INK2='#45484D'; INK3='#666A71'; LINE='#E2E2DC'; LINE2='#CFCFC8'
ACC='#2447D6'; ACCS='#E9EDFC'; ACCD='#1A36A8'; NEU='#ECECE7'
ERR='#B42318'; ERRS='#FDECEA'; OK='#1E7A4C'; OKS='#E6F3EB'
FONT="'Onest', system-ui, sans-serif"; MONO="'JetBrains Mono', ui-monospace, monospace"

LV={'priority':('Приоритетная',ACC,'#FFFFFF',''),
    'ready':('Готовая',ACCS,ACCD,''),
    'working':('Рабочая',NEU,INK,''),
    'draft':('Черновик',SURF,INK2,f'border: 1px dashed {LINE2};')}
FILL={'priority':ACC,'ready':ACC,'working':INK2,'draft':'#A9A9A2'}
def level(s): return 'priority' if s>=90 else 'ready' if s>=70 else 'working' if s>=40 else 'draft'
def fmt(x): return (str(int(x)) if float(x).is_integer() else str(x).replace('.',','))

def svg(d,w=16,sw=1.8): return f'<svg width="{w}" height="{w}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{d}</svg>'
I={
'search':svg('<circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path>',18),
'data':svg('<ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"></ellipse><path d="M4.5 5.5v13c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-13"></path><path d="M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"></path>'),
'clock':svg('<circle cx="12" cy="12" r="8.5"></circle><path d="M12 7.5V12l3 2"></path>'),
'resp':svg('<path d="M4 5h16v11H9l-5 4z"></path>'),
'chev':svg('<path d="M6 9l6 6 6-6"></path>'),
'plus':svg('<path d="M12 5v14M5 12h14"></path>',18,2),
'check':svg('<path d="M5 12.5l4.5 4.5L19 7.5"></path>',14,2.6),
'checkL':svg('<path d="M5 12.5l4.5 4.5L19 7.5"></path>',28,2.2),
'arrow':svg('<path d="M5 12h14M13 6l6 6-6 6"></path>'),
'back':svg('<path d="M19 12H5M11 6l-6 6 6 6"></path>'),
'sort':svg('<path d="M7 4v16M3.5 16.5L7 20l3.5-3.5M13 6h8M13 11h6M13 16h4"></path>'),
'alert':svg('<circle cx="12" cy="12" r="9"></circle><path d="M12 7.5v5.5M12 16.5v.5"></path>',18),
'info':svg('<circle cx="12" cy="12" r="9"></circle><path d="M12 11v5.5M12 7.5v.5"></path>',18),
'spark':svg('<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6"></path>'),
'link':svg('<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"></path><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"></path>'),
'edit':svg('<path d="M4 20h4L19 9l-4-4L4 16z"></path><path d="M13.5 6.5l4 4"></path>'),
'alertS':svg('<circle cx="12" cy="12" r="9"></circle><path d="M12 7.5v5.5M12 16.5v.5"></path>',15),
'x':svg('<path d="M6 6l12 12M18 6L6 18"></path>'),
'filter':svg('<path d="M4 5h16l-6 7.5V19l-4 1.5v-8z"></path>',28,1.6),
'inbox':svg('<path d="M3 13l3-8h12l3 8v6H3z"></path><path d="M3 13h5l1.5 2.5h5L16 13h5"></path>',28,1.6),
'external':svg('<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"></path>',14),
}

def eyebrow(t,color=None): return f'<div style="font-family: {MONO}; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: {color or INK3};">{t}</div>'

def badge(lv,text=None):
    lab,bg,fg,br=LV[lv]
    return f'<span style="display: inline-flex; align-items: center; height: 24px; padding: 0 10px; border-radius: 6px; background: {bg}; color: {fg}; {br} font-size: 13px; font-weight: 600; white-space: nowrap;">{text or lab}</span>'

def meter(s,lv=None,w=120,h=6):
    lv=lv or level(s)
    ticks=''.join(f'<span style="position: absolute; top: -3px; left: {p}%; width: 1px; height: {h+6}px; background: {INK3};"></span>' for p in (40,70,90))
    return (f'<div role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{s}" aria-label="Готовность {fmt(s)} из 100" style="position: relative; width: {w}px; height: {h}px; border-radius: {h//2}px; background: {NEU};">'
            f'<div style="width: {s}%; height: {h}px; border-radius: {h//2}px; background: {FILL[lv]};"></div>{ticks}</div>')

def score_block(s,w=260,big=40,sub='из 100'):
    lv=level(s)
    return f'''<div style="display: flex; flex-direction: column; gap: 12px;">
<div style="display: flex; align-items: baseline; gap: 8px;"><span style="font-family: {MONO}; font-size: {big}px; font-weight: 600; letter-spacing: -0.03em; line-height: 1;">{fmt(s)}</span><span style="font-size: 14px; color: {INK3};">{sub}</span><span style="margin-left: auto;">{badge(lv)}</span></div>
{meter(s,lv,w,8)}
<div style="display: flex; justify-content: space-between; width: {w}px; font-family: {MONO}; font-size: 11px; color: {INK3};"><span>0</span><span style="margin-left: 34%;">40</span><span style="margin-left: 22%;">70</span><span>90</span><span>100</span></div>
</div>'''

def btn(label,kind='primary',icon='',href=None,size='md',full=False,extra=''):
    h={'md':44,'sm':36,'lg':52}[size]; fs={'md':15,'sm':14,'lg':16}[size]
    st={'primary':f'background: {ACC}; color: #FFFFFF; border: 1px solid {ACC};',
        'secondary':f'background: {SURF}; color: {INK}; border: 1px solid {LINE2};',
        'ghost':f'background: transparent; color: {INK2}; border: 1px solid transparent;',
        'dark':f'background: {INK}; color: #FFFFFF; border: 1px solid {INK};',
        'danger':f'background: {SURF}; color: {ERR}; border: 1px solid {LINE2};',
        'disabled':f'background: {NEU}; color: #8E9197; border: 1px solid {NEU};'}[kind]
    w='width: 100%;' if full else ''
    base=f'height: {h}px; box-sizing: border-box; padding: 0 {16 if size!="sm" else 12}px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; border-radius: 8px; {st} font: 600 {fs}px {FONT}; text-decoration: none; white-space: nowrap; {w} {extra}'
    if href is not None: return f'<a href="{href}" style="{base}">{icon}{label}</a>'
    dis=' disabled' if kind=='disabled' else ''
    return f'<button type="button"{dis} style="{base}">{icon}{label}</button>'

def field(label,control,hint='',error='',meta='',fid=''):
    lab=f'<div style="display: flex; justify-content: space-between; align-items: baseline; gap: 12px;"><label for="{fid}" style="font-size: 14px; font-weight: 600; color: {INK};">{label}</label>{meta}</div>'
    h=f'<div style="font-size: 13px; line-height: 1.45; color: {INK3};">{hint}</div>' if hint else ''
    e=f'<div role="alert" style="display: flex; gap: 6px; align-items: flex-start; font-size: 13px; line-height: 1.45; font-weight: 500; color: {ERR};"><span style="flex-shrink: 0; margin-top: 1px;">{I["alertS"]}</span>{error}</div>' if error else ''
    return f'<div style="display: flex; flex-direction: column; gap: 8px;">{lab}{control}{e}{h}</div>'

def inp(value='',ph='',fid='',invalid=False,t='text'):
    b=f'border: 1.5px solid {ERR}; background: {ERRS};' if invalid else f'border: 1px solid {LINE2}; background: {SURF};'
    inv=' aria-invalid="true"' if invalid else ''
    return f'<input id="{fid}" type="{t}" value="{value}" placeholder="{ph}"{inv} style="height: 44px; box-sizing: border-box; padding: 0 12px; border-radius: 8px; {b} font: 400 15px {FONT}; color: {INK}; width: 100%; outline: none;">'

def ta(value='',ph='',fid='',rows=3,invalid=False,focus=False):
    b=f'border: 1.5px solid {ERR}; background: {ERRS};' if invalid else (f'border: 1.5px solid {ACC}; background: {SURF}; box-shadow: 0 0 0 3px {ACCS};' if focus else f'border: 1px solid {LINE2}; background: {SURF};')
    inv=' aria-invalid="true"' if invalid else ''
    return f'<textarea id="{fid}" rows="{rows}" placeholder="{ph}"{inv} style="box-sizing: border-box; padding: 12px; border-radius: 8px; {b} font: 400 15px/1.5 {FONT}; color: {INK}; width: 100%; resize: vertical; outline: none;">{value}</textarea>'

def select(value,fid=''):
    return f'<span style="position: relative; display: flex; align-items: center; height: 44px; box-sizing: border-box; padding: 0 12px; border: 1px solid {LINE2}; border-radius: 8px; background: {SURF};"><select id="{fid}" style="appearance: none; border: 0; background: transparent; font: 400 15px {FONT}; color: {INK}; outline: none; flex-grow: 1;"><option>{value}</option></select><span style="color: {INK3}; display: flex;">{I["chev"]}</span></span>'

def checkbox(label,count='',on=False,extra=''):
    box = (f'<span style="width: 18px; height: 18px; flex-shrink: 0; border-radius: 5px; background: {INK}; color: #FFFFFF; display: flex; align-items: center; justify-content: center;">{I["check"]}</span>' if on
           else f'<span style="width: 18px; height: 18px; flex-shrink: 0; box-sizing: border-box; border-radius: 5px; border: 1.5px solid {LINE2}; background: {SURF};"></span>')
    c=f'<span style="font-family: {MONO}; font-size: 13px; color: {INK3};">{count}</span>' if count!='' else ''
    return f'''<label style="position: relative; display: flex; align-items: center; gap: 10px; min-height: 36px; font-size: 15px; line-height: 1.4; color: {INK}; cursor: pointer;"><input type="checkbox" {"checked" if on else ""} style="position: absolute; opacity: 0; width: 1px; height: 1px;">{box}<span style="flex-grow: 1;">{label}{extra}</span>{c}</label>'''

def alert(kind,title,text,icon=None):
    c={'info':(ACCS,ACCD,I['info']),'warn':(NEU,INK,I['alert']),'error':(ERRS,ERR,I['alert']),'ok':(OKS,OK,I['check']),'draft':(SURF,INK2,I['info'])}[kind]
    br=f'border: 1px dashed {LINE2};' if kind=='draft' else ''
    tcol = INK
    return f'<div role="{"alert" if kind=="error" else "status"}" style="display: flex; gap: 12px; align-items: flex-start; padding: 14px 16px; border-radius: 10px; background: {c[0]}; {br}"><span style="color: {c[1]}; display: flex; flex-shrink: 0; margin-top: 1px;">{c[2]}</span><div style="display: flex; flex-direction: column; gap: 4px;"><div style="font-size: 15px; font-weight: 600; color: {c[1] if kind in ("error","ok","info") else tcol};">{title}</div><div style="font-size: 14px; line-height: 1.5; color: {INK2};">{text}</div></div></div>'

def panel(inner,pad=24,gap=20,extra=''):
    return f'<section style="display: flex; flex-direction: column; gap: {gap}px; padding: {pad}px; background: {SURF}; border: 1px solid {LINE}; border-radius: 12px; {extra}">{inner}</section>'

FIELDS=[('context','Контекст',10),('need','Потребность',10),('users','Пользователи',10),('data','Данные и материалы',20),
        ('constraints','Ограничения',10),('expected_result','Ожидаемый результат',15),('success_criteria','Критерии успеха',15),('contact','Связь с бизнесом',10)]
HINT={'context':'Добавьте контекст','need':'Опишите потребность','users':'Опишите пользователей','data':'Добавьте данные и материалы',
      'constraints':'Укажите ограничения','expected_result':'Опишите ожидаемый результат','success_criteria':'Добавьте измеримые критерии успеха','contact':'Добавьте контакт и формат связи'}

def state_of(earned,mx): return 'complete' if earned>=mx else 'short' if earned>0 else 'empty'
def state_tag(earned,mx):
    st=state_of(earned,mx)
    if st=='complete': return f'<span style="display: inline-flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 600; color: {OK};">{I["check"]}Заполнено</span>'
    if st=='short': return f'<span style="font-size: 12px; font-weight: 600; color: {INK2};">Коротко · +{fmt(mx-earned)}</span>'
    return f'<span style="font-size: 12px; font-weight: 600; color: {INK3};">Пусто · +{fmt(mx)}</span>'

def breakdown(vals,w=None):
    rows=''
    for k,lab,mx in FIELDS:
        e=vals[k]; st=state_of(e,mx)
        col = ACC if st=='complete' else ('#A9A9A2' if st=='short' else NEU)
        rows+=f'''<div style="display: grid; grid-template-columns: minmax(0, 1fr) 96px 64px; gap: 12px; align-items: center; min-height: 32px;">
<span style="font-size: 14px; color: {INK};">{lab}</span>
<div style="height: 6px; border-radius: 3px; background: {NEU};"><div style="width: {e/mx*100:.0f}%; height: 6px; border-radius: 3px; background: {col};"></div></div>
<span style="font-family: {MONO}; font-size: 13px; text-align: right; color: {INK if e>0 else INK3};">{fmt(e)}/{mx}</span></div>'''
    return f'<div style="display: flex; flex-direction: column; gap: 4px;">{rows}</div>'

def missing(vals):
    out=''
    for k,lab,mx in FIELDS:
        e=vals[k]
        if e<mx: out+=f'<li style="display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-top: 1px solid {LINE}; font-size: 14px; line-height: 1.4;"><span>{HINT[k]}</span><span style="font-family: {MONO}; font-weight: 600; color: {ACCD}; white-space: nowrap;">+{fmt(mx-e)}</span></li>'
    return f'<ul style="list-style: none; margin: 0; padding: 0;">{out}</ul>'

def stepper(active):
    steps=['Описание','Уточнение','Карточка','Публикация']
    out=''
    for i,s in enumerate(steps):
        n=i+1
        if n<active: dot=f'<span style="width: 28px; height: 28px; border-radius: 14px; background: {INK}; color: #FFFFFF; display: flex; align-items: center; justify-content: center;">{I["check"]}</span>'; col=INK2; fw=500
        elif n==active: dot=f'<span style="width: 28px; height: 28px; border-radius: 14px; background: {ACC}; color: #FFFFFF; display: flex; align-items: center; justify-content: center; font-family: {MONO}; font-size: 13px; font-weight: 600;">{n}</span>'; col=INK; fw=600
        else: dot=f'<span style="width: 28px; height: 28px; box-sizing: border-box; border-radius: 14px; border: 1.5px solid {LINE2}; color: {INK3}; display: flex; align-items: center; justify-content: center; font-family: {MONO}; font-size: 13px; font-weight: 600;">{n}</span>'; col=INK3; fw=500
        cur=' aria-current="step"' if n==active else ''
        out+=f'<li{cur} style="display: flex; align-items: center; gap: 10px; font-size: 15px; font-weight: {fw}; color: {col};">{dot}{s}</li>'
        if n<4: out+=f'<li aria-hidden="true" style="width: 48px; height: 1px; background: {LINE2};"></li>'
    return f'<ol aria-label="Шаги создания задачи" style="list-style: none; margin: 0; padding: 0; display: flex; align-items: center; gap: 14px;">{out}</ol>'

def header(role='business',active='Каталог'):
    if role=='business': items=['Каталог','Мои задачи','Предложения']
    else: items=['Каталог','Рекомендации','Мои отклики']
    AC=' aria-current="page"'
    nav=''.join(f'<a href="#"{AC if it==active else ""} style="padding: 8px 12px; border-radius: 8px; {"background: "+NEU+"; color: "+INK+"; font-weight: 600;" if it==active else "color: "+INK2+"; font-weight: 500;"} font-size: 15px; text-decoration: none;">{it}</a>' for it in items)
    b_on = role=='business'
    seg=lambda lab,on: f'<button type="button" aria-pressed="{"true" if on else "false"}" style="height: 32px; padding: 0 12px; border: 0; border-radius: 7px; background: {SURF if on else "transparent"}; color: {INK if on else INK2}; font: {"600" if on else "500"} 14px {FONT}; {"box-shadow: 0 1px 2px rgba(0,0,0,0.08);" if on else ""}">{lab}</button>'
    right = btn('Создать задачу','primary',I['plus'],href='#') if b_on else f'<span style="display: flex; align-items: center; gap: 10px; font-size: 14px; color: {INK2};"><span style="width: 32px; height: 32px; border-radius: 16px; background: {NEU}; display: flex; align-items: center; justify-content: center; font-family: {MONO}; font-size: 12px; font-weight: 600; color: {INK};">DS</span>Data Sparks</span>'
    if b_on: right = btn('Создать задачу','primary',I['plus'],href='#',size='sm')
    return f'''<header style="height: 64px; box-sizing: border-box; padding: 0 40px; display: flex; align-items: center; gap: 40px; background: {SURF}; border-bottom: 1px solid {LINE};">
<a href="#" style="display: flex; align-items: center; gap: 10px; text-decoration: none; color: {INK};"><span style="width: 28px; height: 28px; border-radius: 7px; background: {INK}; color: #FFFFFF; display: flex; align-items: center; justify-content: center; font-family: {MONO}; font-size: 13px; font-weight: 600;">AS</span><span style="font-size: 18px; font-weight: 700; letter-spacing: -0.02em;">AI Sana</span></a>
<nav aria-label="Основная навигация" style="display: flex; gap: 4px; flex-grow: 1;">{nav}</nav>
<div role="group" aria-label="Роль" style="display: flex; padding: 3px; border-radius: 9px; background: {NEU};">{seg("Бизнес",b_on)}{seg("Команда",not b_on)}</div>
{right}
</header>'''

def page(title,w,h,body,role='business',active='Каталог',nohead=False):
    hd='' if nohead else header(role,active)
    return f'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{title}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600;700&amp;family=JetBrains+Mono:wght@500;600&amp;display=swap">
<style>
body{{margin:0;font-family:{FONT};color:{INK};background:{BG};-webkit-font-smoothing:antialiased}}
a{{color:{ACC}}}a:hover{{color:{ACCD}}}
</style>
</helmet>
<div style="width: {w}px; height: {h}px; box-sizing: border-box; background: {BG}; font-family: {FONT}; color: {INK}; overflow: hidden;">
{hd}
{body}
</div>
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":{w},"height":{h}}}}}'>
class Component extends DCLogic {{
renderVals() {{ return {{}}; }}
}}
</script>
</body>
</html>
'''

def crumbs(items):
    out=[]
    for i,(t,href) in enumerate(items):
        out.append(f'<a href="{href}" style="color: {INK2}; text-decoration: none;">{t}</a>' if href else f'<span style="color: {INK};">{t}</span>')
    return f'<nav aria-label="Навигационная цепочка" style="display: flex; gap: 8px; font-size: 14px; color: {INK3};">{" <span>/</span> ".join(out)}</nav>'
