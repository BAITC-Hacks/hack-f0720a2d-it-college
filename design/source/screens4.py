from ds import *
R='/tmp/claude-0/-home-claude/4fb9a2df-5978-53ad-9997-837627599b25/scratchpad/canvas/project/'
def W(name,html): open(R+name,'w').write(html)

MY=[('Прогноз загрузки столовой колледжа',95,4,'2 новых'),('Напоминания пациентам о записи',95,0,'опубл. сегодня'),('Учёт посещаемости спортивных секций',45,0,'опубл. 5 дней назад')]
def mylist(sel):
    items=''
    for i,(t,s,n,note) in enumerate(MY):
        on=i==sel
        st=f'background: {SURF}; border: 1px solid {INK};' if on else f'background: transparent; border: 1px solid transparent;'
        items+=f'''<a href="#"{' aria-current="true"' if on else ''} style="display: flex; flex-direction: column; gap: 10px; padding: 16px; border-radius: 10px; {st} text-decoration: none; color: {INK};">
<span style="font-size: 16px; font-weight: 600; line-height: 1.3;">{t}</span>
<span style="display: flex; align-items: center; gap: 10px;"><span style="font-family: {MONO}; font-size: 14px; font-weight: 600;">{fmt(s)}</span>{meter(s,None,64)}<span style="margin-left: auto; display: flex; align-items: center; gap: 6px; font-size: 13px; color: {INK2};">{I["resp"]}{n}</span></span>
<span style="font-size: 12px; color: {INK3};">{note}</span></a>'''
    return f'<aside style="width: 300px; flex-shrink: 0; display: flex; flex-direction: column; gap: 8px;"><div style="display: flex; justify-content: space-between; align-items: center; padding: 0 4px 8px;"><h2 style="margin: 0; font-size: 15px; font-weight: 600;">Мои задачи</h2><span style="font-family: {MONO}; font-size: 13px; color: {INK3};">3</span></div>{items}</aside>'

def taskhead(t,s,sub):
    return f'''<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 32px; padding: 28px; background: {SURF}; border: 1px solid {LINE}; border-radius: 12px;">
<div style="display: flex; flex-direction: column; gap: 10px; min-width: 0;"><span style="font-size: 14px; color: {INK3};">{sub}</span><h1 style="margin: 0; font-size: 34px; font-weight: 700; letter-spacing: -0.025em; line-height: 1.1;">{t}</h1>
<div style="display: flex; gap: 16px; font-size: 14px;"><a href="#" style="display: inline-flex; gap: 6px; align-items: center; text-decoration: none;">Открыть в каталоге {I["external"]}</a><a href="#" style="display: inline-flex; gap: 6px; align-items: center; text-decoration: none;">{I["edit"]}Редактировать карточку</a></div></div>
<div style="width: 280px; flex-shrink: 0;">{score_block(s,280,36)}</div></div>'''

def tabs(items,sel):
    out=''
    for i,(l,n) in enumerate(items):
        on=i==sel
        out+=f'<button type="button" role="tab" aria-selected="{"true" if on else "false"}" style="height: 44px; padding: 0 4px; border: 0; border-bottom: 2px solid {INK if on else "transparent"}; background: transparent; font: {"600" if on else "500"} 15px {FONT}; color: {INK if on else INK2}; display: flex; gap: 8px; align-items: center;">{l}<span style="font-family: {MONO}; font-size: 12px; color: {INK3};">{n}</span></button>'
    return f'<div role="tablist" style="display: flex; gap: 28px; border-bottom: 1px solid {LINE};">{out}</div>'

P=[dict(team='Data Sparks',init='DS',skills='анализ данных · UX',tech='Python, FastAPI, Pandas',st='pending',
        idea='Прогноз по расписанию и истории чеков, загрузка на временной шкале с шагом 15 минут.',
        plan='1 нед. — данные · 2 — модель · 3 — API и интерфейс · 4 — тест на 5 студентах',dl='4 недели',link='datasparks.kz/canteen',date='22 сен'),
   dict(team='Retail Minds',init='RM',skills='аналитика · визуализация',tech='Python, SQL, Chart.js',st='accepted',
        idea='Модель спроса по часам + дашборд для столовой с рекомендацией, когда открывать вторую кассу.',
        plan='1 нед. — разбор чеков · 2 — прогноз · 3 — дашборд · 4 — пилот с поварами',dl='4 недели',link='retailminds.kz/demo',date='21 сен'),
   dict(team='Kind Tech',init='KT',skills='product · fullstack',tech='FastAPI, JavaScript, Figma',st='pending',
        idea='Страница «Когда идти в столовую» с живой очередью по отметкам студентов и прогнозом.',
        plan='1 нед. — интервью · 2 — прототип · 3 — сбор отметок · 4 — доработка',dl='3 недели',link='',date='22 сен'),
   dict(team='Civic Code',init='CC',skills='backend · frontend',tech='Python, JavaScript, SQLite',st='rejected',
        idea='Электронная очередь с талонами через сайт и уведомлением, когда подходит очередь.',
        plan='1 нед. — backend · 2 — интерфейс · 3 — тесты',dl='3 недели',link='civiccode.kz/queue',date='20 сен')]
ST={'pending':('На рассмотрении',NEU,INK),'accepted':('Выбрана',OKS,OK),'rejected':('Отклонена',SURF,INK3)}

def compare(props):
    n=len(props)
    cols=f'160px repeat({n}, minmax(0, 1fr))'
    def row(label,cells,pad='16px'):
        return f'<div style="display: grid; grid-template-columns: {cols}; border-top: 1px solid {LINE};"><div style="padding: {pad} 16px; font-size: 13px; font-weight: 600; color: {INK3};">{label}</div>{"".join(cells)}</div>'
    def cell(p,inner):
        bg = OKS if p['st']=='accepted' else SURF
        op = 'opacity: 0.6;' if p['st']=='rejected' else ''
        return f'<div style="padding: 16px; border-left: 1px solid {LINE}; background: {bg}; {op} font-size: 14px; line-height: 1.5; color: {INK};">{inner}</div>'
    head=''.join(cell(p,f'''<div style="display: flex; flex-direction: column; gap: 10px;"><div style="display: flex; align-items: center; gap: 10px;"><span style="width: 36px; height: 36px; border-radius: 18px; background: {INK}; color: #FFFFFF; display: flex; align-items: center; justify-content: center; font-family: {MONO}; font-size: 12px; font-weight: 600;">{p["init"]}</span><span style="display: flex; flex-direction: column;"><span style="font-size: 16px; font-weight: 600;">{p["team"]}</span><span style="font-size: 12px; color: {INK3};">отклик {p["date"]}</span></span></div>
<span style="align-self: flex-start; display: inline-flex; align-items: center; gap: 4px; height: 24px; padding: 0 10px; border-radius: 6px; background: {ST[p["st"]][1]}; color: {ST[p["st"]][2]}; {"border: 1px solid "+LINE2+";" if p["st"]=="rejected" else ""} font-size: 13px; font-weight: 600;">{I["check"] if p["st"]=="accepted" else ""}{ST[p["st"]][0]}</span></div>''') for p in props)
    def actions(p):
        if p['st']=='pending': return f'<div style="display: flex; flex-direction: column; gap: 8px;">{btn("Выбрать команду","primary",I["check"],None,"sm",True)}{btn("Отклонить","danger","",None,"sm",True)}</div>'
        if p['st']=='accepted': return f'<div style="display: flex; flex-direction: column; gap: 8px;"><span style="font-size: 13px; color: {OK}; font-weight: 600;">Этап 1 из 4 · данные</span>{btn("Подтвердить этап","dark","",None,"sm",True)}<span style="font-size: 12px; line-height: 1.4; color: {INK2};">Команда получит баллы за подтверждённый прогресс</span>{btn("Отменить выбор","ghost","",None,"sm",True)}</div>'
        return f'<div style="display: flex; flex-direction: column; gap: 8px;">{btn("Вернуть на рассмотрение","ghost","",None,"sm",True)}</div>'
    link=lambda p: f'<a href="#" style="display: inline-flex; gap: 6px; align-items: center; text-decoration: none; word-break: break-all;">{I["link"]}{p["link"]}</a>' if p['link'] else f'<span style="color: {INK3}; font-style: italic;">не приложена</span>'
    return f'''<div style="border: 1px solid {LINE}; border-radius: 12px; overflow: hidden; background: {SURF};">
<div style="display: grid; grid-template-columns: {cols};"><div style="padding: 16px; display: flex; align-items: flex-end;">{eyebrow("Сравнение")}</div>{head}</div>
{row("Навыки",[cell(p,f'<div style="display: flex; flex-direction: column; gap: 4px;"><span>{p["skills"]}</span><span style="font-family: {MONO}; font-size: 12px; color: {INK3};">{p["tech"]}</span></div>') for p in props])}
{row("Идея решения",[cell(p,p["idea"]) for p in props])}
{row("План",[cell(p,f'<span style="color: {INK2};">{p["plan"]}</span>') for p in props])}
{row("Срок",[cell(p,f'<span style="font-family: {MONO}; font-weight: 600;">{p["dl"]}</span>') for p in props])}
{row("Прототип",[cell(p,link(p)) for p in props])}
{row("Решение",[cell(p,actions(p)) for p in props])}
</div>'''

note = alert('info','Выбор только за вами','Можно выбрать одну команду, несколько или ни одной. Система не назначает исполнителей и не ранжирует команды — сравнивайте по идее, плану и сроку.')
main = f'''<main style="flex-grow: 1; min-width: 0; display: flex; flex-direction: column; gap: 24px;">
{taskhead("Прогноз загрузки столовой колледжа",95,"Образование · опубликована 18 сентября · 1-е место в каталоге")}
{tabs([("Все",4),("На рассмотрении",2),("Выбраны",1),("Отклонены",1)],0)}
{note}
{compare(P)}
</main>'''
body=f'<div style="padding: 40px; display: flex; gap: 32px; align-items: flex-start;">{mylist(0)}{main}</div>'
W('Business.dc.html',page('Кабинет бизнеса — сравнение предложений',1440,1500,body,'business','Мои задачи'))

# Empty: task with 0 proposals + low-ish rating
V={'context':10,'need':10,'users':5,'data':5,'constraints':0,'expected_result':15,'success_criteria':0,'contact':0}
emp = f'''<div style="display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 24px; align-items: start;">
<div style="display: flex; flex-direction: column; align-items: center; text-align: center; gap: 16px; padding: 64px 40px; background: {SURF}; border: 1px dashed {LINE2}; border-radius: 12px;">
<span style="width: 56px; height: 56px; border-radius: 28px; background: {NEU}; color: {INK2}; display: flex; align-items: center; justify-content: center;">{I["inbox"]}</span>
<h2 style="margin: 0; font-size: 24px; font-weight: 600;">Предложений пока нет</h2>
<p style="margin: 0; max-width: 440px; font-size: 16px; line-height: 1.55; color: {INK2};">Задача опубликована 5 дней назад и стоит на 6-м месте из 8. Команды чаще откликаются на задачи с понятными данными и критериями успеха.</p>
<div style="display: flex; gap: 12px; margin-top: 8px;">{btn("Дополнить карточку","primary",I["edit"],"#")}{btn("Открыть в каталоге","secondary","","#")}</div>
</div>
{panel(f'<div style="display: flex; justify-content: space-between; align-items: baseline;">{eyebrow("Что поднимет задачу")}<span style="font-family: {MONO}; font-size: 12px; color: {INK3};">45 → 100</span></div>{missing(V)}<p style="margin: 0; font-size: 13px; line-height: 1.5; color: {INK3};">С +25 баллами задача станет «Готовой» и поднимется выше в каталоге.</p>',24,14)}
</div>'''
main2 = f'''<main style="flex-grow: 1; min-width: 0; display: flex; flex-direction: column; gap: 24px;">
{taskhead("Учёт посещаемости спортивных секций",45,"Спорт · опубликована 18 сентября · 6-е место в каталоге")}
{tabs([("Все",0),("На рассмотрении",0),("Выбраны",0),("Отклонены",0)],0)}
{emp}
</main>'''
W('BusinessEmpty.dc.html',page('Кабинет бизнеса — нет предложений',1440,1000,f'<div style="padding: 40px; display: flex; gap: 32px; align-items: flex-start;">{mylist(2)}{main2}</div>','business','Мои задачи'))
