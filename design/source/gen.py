import json, datetime, os
R='/tmp/claude-0/-home-claude/4fb9a2df-5978-53ad-9997-837627599b25/scratchpad/canvas/project/'
# tokens
BG='#F4F4F1'; SURF='#FFFFFF'; INK='#1B1C1E'; INK2='#45484D'; INK3='#666A71'; LINE='#E2E2DC'; LINE2='#CFCFC8'
ACC='#2447D6'; ACCS='#E9EDFC'; ACCD='#1A36A8'; NEU='#ECECE7'
FONT="'Onest', system-ui, sans-serif"; MONO="'JetBrains Mono', ui-monospace, monospace"

TASKS=[
 dict(t='Прогноз загрузки столовой колледжа',ind='Образование',org='Колледж цифровых технологий',s=96,lv='priority',
      res='Веб-прототип, который показывает ожидаемую очередь по 15-минутным интервалам и даёт администратору обновлять данные.',data='Чеки за 3 месяца, расписание',term='4 недели',n=4),
 dict(t='Отчёт по остаткам небольшого магазина',ind='Ритейл',org='ИП «Береке Маркет»',s=92,lv='priority',
      res='Интерактивный отчёт с динамикой продаж и списком товаров, которые пора пополнить на этой неделе.',data='CSV продаж и остатков, 6 мес.',term='3 недели',n=2),
 dict(t='Единая панель заявок на ремонт',ind='ЖКХ',org='КСК «Сарыарка-12»',s=81,lv='ready',
      res='Реестр обращений жителей с фильтрами, ответственными и сменой статуса заявки.',data='Таблица обращений за полгода',term='3 недели',n=3),
 dict(t='Расписание волонтёрских смен',ind='Социальная сфера',org='ОФ «Қамқор»',s=74,lv='ready',
      res='Страница записи на смены и обзор заполненности для координатора мероприятия.',data='Шаблоны прошлых расписаний',term='4 недели',n=1),
 dict(t='Telegram-бот записи на техосмотр',ind='Транспорт',org='СТО «АвтоДом»',s=58,lv='working',
      res='Бот, который показывает свободные окна и записывает клиента без звонка администратору.',data='Не указаны',term='Не указан',n=0),
 dict(t='Учёт посещаемости спортивных секций',ind='Спорт',org='Спорткомплекс «Жастар»',s=45,lv='working',
      res='Электронный журнал посещений с отчётом для тренера за месяц.',data='Бумажные журналы',term='Не указан',n=1),
 dict(t='Помощник читателя',ind='Культура',org='Городская библиотека № 3',s=30,lv='draft',
      res='Прототип',data='Не указаны',term='Не указан',n=1),
]
LV={'priority':('Приоритетная',ACC,'#FFFFFF','none'),
    'ready':('Готовая',ACCS,ACCD,'none'),
    'working':('Рабочая',NEU,INK,'none'),
    'draft':('Черновик',SURF,INK2,f'1px dashed {LINE2}')}
FILL={'priority':ACC,'ready':ACC,'working':INK2,'draft':'#A9A9A2'}

def badge(lv):
    lab,bg,fg,br=LV[lv]
    b=f'border: {br};' if br!='none' else ''
    return f'<span style="display: inline-flex; align-items: center; height: 24px; padding: 0 10px; border-radius: 6px; background: {bg}; color: {fg}; {b} font-size: 13px; font-weight: 600; white-space: nowrap;">{lab}</span>'

def meter(s,lv,w=120):
    ticks=''.join(f'<span style="position: absolute; top: -3px; left: {p}%; width: 1px; height: 12px; background: {INK3};"></span>' for p in (40,70,90))
    return (f'<div style="position: relative; width: {w}px; height: 6px; border-radius: 3px; background: {NEU};">'
            f'<div style="width: {s}%; height: 6px; border-radius: 3px; background: {FILL[lv]};"></div>{ticks}</div>')

I={
'search':'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>',
'data':'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><ellipse cx="12" cy="5.5" rx="7.5" ry="2.8"></ellipse><path d="M4.5 5.5v13c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8v-13"></path><path d="M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"></path></svg>',
'clock':'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"></circle><path d="M12 7.5V12l3 2"></path></svg>',
'resp':'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"></path></svg>',
'chev':'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M6 9l6 6 6-6"></path></svg>',
'plus':'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"></path></svg>',
'check':'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"></path></svg>',
'arrow':'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"></path></svg>',
'sort':'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M7 4v16M3.5 16.5L7 20l3.5-3.5M13 6h8M13 11h6M13 16h4"></path></svg>',
}

def header():
    return f'''<header style="height: 64px; box-sizing: border-box; padding: 0 40px; display: flex; align-items: center; gap: 40px; background: {SURF}; border-bottom: 1px solid {LINE};">
<a href="#" style="display: flex; align-items: center; gap: 10px; text-decoration: none; color: {INK};"><span style="width: 28px; height: 28px; border-radius: 7px; background: {INK}; color: #FFFFFF; display: flex; align-items: center; justify-content: center; font-family: {MONO}; font-size: 13px; font-weight: 600;">AS</span><span style="font-size: 18px; font-weight: 700; letter-spacing: -0.02em;">AI Sana</span></a>
<nav aria-label="Основная навигация" style="display: flex; gap: 4px; flex-grow: 1;">
<a href="#" aria-current="page" style="padding: 8px 12px; border-radius: 8px; background: {NEU}; color: {INK}; font-size: 15px; font-weight: 600; text-decoration: none;">Каталог</a>
<a href="#" style="padding: 8px 12px; border-radius: 8px; color: {INK2}; font-size: 15px; font-weight: 500; text-decoration: none;">Мои задачи</a>
<a href="#" style="padding: 8px 12px; border-radius: 8px; color: {INK2}; font-size: 15px; font-weight: 500; text-decoration: none;">Отклики</a>
</nav>
<div role="group" aria-label="Роль" style="display: flex; padding: 3px; border-radius: 9px; background: {NEU};">
<button type="button" aria-pressed="true" style="height: 32px; padding: 0 12px; border: 0; border-radius: 7px; background: {SURF}; color: {INK}; font: 600 14px {FONT}; box-shadow: 0 1px 2px rgba(0,0,0,0.08);">Бизнес</button>
<button type="button" aria-pressed="false" style="height: 32px; padding: 0 12px; border: 0; border-radius: 7px; background: transparent; color: {INK2}; font: 500 14px {FONT};">Команда</button>
</div>
<a href="#" style="height: 40px; padding: 0 16px; display: flex; align-items: center; gap: 8px; border-radius: 8px; background: {ACC}; color: #FFFFFF; font-size: 15px; font-weight: 600; text-decoration: none;">{I["plus"]}Создать задачу</a>
</header>'''

def page(title, w, h, body, props='{}'):
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
{header()}
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

def eyebrow(t): return f'<div style="font-family: {MONO}; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: {INK3};">{t}</div>'

def checkbox(label,count,on=False,extra=''):
    box = (f'<span style="width: 18px; height: 18px; border-radius: 5px; background: {INK}; color: #FFFFFF; display: flex; align-items: center; justify-content: center;">{I["check"]}</span>' if on
           else f'<span style="width: 18px; height: 18px; box-sizing: border-box; border-radius: 5px; border: 1.5px solid {LINE2}; background: {SURF};"></span>')
    return f'''<label style="display: flex; align-items: center; gap: 10px; min-height: 36px; font-size: 15px; color: {INK}; cursor: pointer;"><input type="checkbox" {"checked" if on else ""} style="position: absolute; opacity: 0; width: 1px; height: 1px;">{box}<span style="flex-grow: 1;">{label}{extra}</span><span style="font-family: {MONO}; font-size: 13px; color: {INK3};">{count}</span></label>'''

# ---------------- Variant A: ledger ----------------
def rowA(i,t):
    s,lv=t['s'],t['lv']
    draftnote = f'<span style="align-self: flex-start; padding: 4px 10px; border-radius: 6px; border: 1px dashed {LINE2}; font-size: 13px; color: {INK2};">Требует уточнения · отклик открыт</span>' if lv=='draft' else ''
    resstyle = f'color: {INK3}; font-style: italic;' if lv=='draft' else f'color: {INK2};'
    top = f'border-top: 3px solid {ACC};' if lv=='priority' else ''
    return f'''<a href="#" style="display: grid; grid-template-columns: 40px minmax(0, 1fr) 190px 180px; column-gap: 24px; align-items: start; padding: 22px 24px; background: {SURF}; border-bottom: 1px solid {LINE}; text-decoration: none; color: {INK};">
<div style="font-family: {MONO}; font-size: 15px; font-weight: 600; color: {INK3}; padding-top: 3px;">{i:02d}</div>
<div style="display: flex; flex-direction: column; gap: 8px; min-width: 0;">
<div style="font-size: 21px; font-weight: 600; line-height: 1.25; letter-spacing: -0.01em;">{t["t"]}</div>
<div style="display: flex; gap: 8px; font-size: 15px; line-height: 1.45;"><span style="color: {INK3}; flex-shrink: 0;">Результат:</span><span style="{resstyle}">{t["res"]}</span></div>
<div style="display: flex; gap: 8px; align-items: center; font-size: 13px; color: {INK3};"><span style="color: {INK2}; font-weight: 500;">{t["ind"]}</span><span>·</span><span>{t["org"]}</span></div>
{draftnote}
</div>
<div style="display: flex; flex-direction: column; gap: 6px; font-size: 14px; color: {INK2}; padding-top: 4px;"><span style="display: flex; gap: 6px; align-items: center;">{I["data"]}{t["data"]}</span><span style="display: flex; gap: 6px; align-items: center;">{I["clock"]}{t["term"]}</span><span style="display: flex; gap: 6px; align-items: center;">{I["resp"]}{t["n"]} откл.</span></div>
<div style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
<div style="display: flex; align-items: center; gap: 10px;">{badge(lv)}<span style="font-family: {MONO}; font-size: 26px; font-weight: 600; letter-spacing: -0.02em; min-width: 44px; text-align: right;">{s}</span></div>
{meter(s,lv,150)}
</div>
</a>'''

sideA = f'''<aside style="width: 256px; flex-shrink: 0; display: flex; flex-direction: column; gap: 28px;">
<label style="display: flex; flex-direction: column; gap: 8px;"><span style="font-size: 14px; font-weight: 600;">Поиск</span>
<span style="display: flex; align-items: center; gap: 8px; height: 44px; padding: 0 12px; border: 1px solid {LINE2}; border-radius: 8px; background: {SURF}; color: {INK3};">{I["search"]}<input type="search" placeholder="Название или результат" style="border: 0; outline: none; background: transparent; font: 400 15px {FONT}; color: {INK}; width: 100%;"></span></label>
<div style="display: flex; flex-direction: column; gap: 4px;">
<div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px;"><span style="font-size: 14px; font-weight: 600;">Готовность описания</span><a href="#" style="font-size: 13px; text-decoration: none;">Сбросить</a></div>
{checkbox("Приоритетная",2,True,f' <span style="font-family: {MONO}; font-size: 12px; color: {INK3};">90–100</span>')}
{checkbox("Готовая",2,True,f' <span style="font-family: {MONO}; font-size: 12px; color: {INK3};">70–89</span>')}
{checkbox("Рабочая",2,True,f' <span style="font-family: {MONO}; font-size: 12px; color: {INK3};">40–69</span>')}
{checkbox("Черновик",1,True,f' <span style="font-family: {MONO}; font-size: 12px; color: {INK3};">0–39</span>')}
</div>
<div style="display: flex; flex-direction: column; gap: 4px;">
<div style="font-size: 14px; font-weight: 600; margin-bottom: 6px;">Тема</div>
{checkbox("Образование",1)}{checkbox("Ритейл",1)}{checkbox("ЖКХ",1)}{checkbox("Социальная сфера",1)}{checkbox("Транспорт",1)}{checkbox("Спорт",1)}{checkbox("Культура",1)}
</div>
<div style="padding: 16px; border-radius: 10px; background: {NEU}; font-size: 13px; line-height: 1.5; color: {INK2};">Рейтинг показывает, насколько полно бизнес описал задачу, а не известность компании. Откликнуться можно на любую задачу.</div>
</aside>'''

mainA = f'''<main style="flex-grow: 1; min-width: 0; display: flex; flex-direction: column; gap: 24px;">
<div style="display: flex; align-items: flex-end; justify-content: space-between; gap: 24px;">
<div style="display: flex; flex-direction: column; gap: 8px;">
<h1 style="margin: 0; font-size: 40px; font-weight: 700; letter-spacing: -0.03em; line-height: 1.1;">Каталог задач</h1>
<p style="margin: 0; font-size: 16px; color: {INK2};">7 опубликованных задач. Чем полнее описание, тем выше задача в списке.</p>
</div>
<label style="display: flex; align-items: center; gap: 10px; font-size: 14px; color: {INK2};">Сортировка
<span style="display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 12px; border: 1px solid {LINE2}; border-radius: 8px; background: {SURF}; color: {INK}; font-weight: 500;">{I["sort"]}<select style="appearance: none; border: 0; background: transparent; font: 500 14px {FONT}; color: {INK}; outline: none;"><option>По рейтингу готовности</option><option>Сначала новые</option><option>Меньше откликов</option></select>{I["chev"]}</span></label>
</div>
<div style="border: 1px solid {LINE}; border-radius: 12px; overflow: hidden; background: {SURF};">
<div style="display: grid; grid-template-columns: 40px minmax(0, 1fr) 190px 180px; column-gap: 24px; padding: 12px 24px; background: {BG}; border-bottom: 1px solid {LINE};">
{eyebrow("№")}{eyebrow("Задача и ожидаемый результат")}{eyebrow("Условия")}<div style="display: flex; justify-content: flex-end;">{eyebrow("Готовность ↓")}</div>
</div>
{"".join(rowA(i+1,t) for i,t in enumerate(TASKS))}
</div>
</main>'''
bodyA = f'<div style="padding: 40px; display: flex; gap: 40px; align-items: flex-start;">{sideA}{mainA}</div>'
open(R+'Main.dc.html','w').write(page('Каталог — вариант A, реестр',1440,1420,bodyA))

# ---------------- Variant B: card grid ----------------
def cardB(i,t):
    s,lv=t['s'],t['lv']
    lab=LV[lv][0]
    head_bg = ACC if lv=='priority' else SURF
    resstyle = f'color: {INK3}; font-style: italic;' if lv=='draft' else f'color: {INK};'
    strip = f'<div style="height: 4px; background: {ACC};"></div>' if lv=='priority' else ''
    warn = (f'<div style="padding: 10px 12px; border-radius: 8px; border: 1px dashed {LINE2}; font-size: 13px; line-height: 1.45; color: {INK2};">Не хватает: ожидаемого результата, данных, критериев успеха. Отклик открыт — уточните детали у бизнеса.</div>' if lv=='draft' else '')
    return f'''<article style="display: flex; flex-direction: column; background: {SURF}; border: 1px solid {LINE}; border-radius: 12px; overflow: hidden;">
{strip}
<div style="display: flex; flex-direction: column; gap: 16px; padding: 24px; flex-grow: 1;">
<div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
<span style="font-size: 13px; font-weight: 500; color: {INK2};">{t["ind"]} · {t["org"]}</span>
</div>
<h2 style="margin: 0; font-size: 23px; font-weight: 600; line-height: 1.22; letter-spacing: -0.015em;"><a href="#" style="color: {INK}; text-decoration: none;">{t["t"]}</a></h2>
<div style="display: flex; flex-direction: column; gap: 6px;">{eyebrow("Ожидаемый результат")}<p style="margin: 0; font-size: 16px; line-height: 1.5; {resstyle}">{t["res"]}</p></div>
{warn}
<div style="flex-grow: 1;"></div>
<div style="display: flex; align-items: center; gap: 14px; padding: 14px 16px; border-radius: 10px; background: {BG};">
<span style="font-family: {MONO}; font-size: 30px; font-weight: 600; letter-spacing: -0.03em; line-height: 1;">{s}</span>
<div style="display: flex; flex-direction: column; gap: 8px; flex-grow: 1;"><div style="display: flex; justify-content: space-between; align-items: center;">{badge(lv)}<span style="font-size: 12px; color: {INK3};">из 100</span></div>{meter(s,lv,230)}</div>
</div>
</div>
<div style="display: flex; align-items: center; gap: 16px; padding: 14px 24px; border-top: 1px solid {LINE}; font-size: 14px; color: {INK2};">
<span style="display: flex; gap: 6px; align-items: center;">{I["data"]}{t["data"]}</span>
<span style="display: flex; gap: 6px; align-items: center; margin-left: auto;">{I["resp"]}<span style="font-family: {MONO};">{t["n"]}</span></span>
</div>
</article>'''

def chip(label,count,on=False):
    st = f'background: {INK}; color: #FFFFFF; border: 1px solid {INK};' if on else f'background: {SURF}; color: {INK}; border: 1px solid {LINE2};'
    cc = '#C9CBD0' if on else INK3
    return f'<button type="button" aria-pressed="{"true" if on else "false"}" style="height: 40px; padding: 0 14px; border-radius: 20px; {st} font: 500 14px {FONT}; display: flex; align-items: center; gap: 8px;">{label}<span style="font-family: {MONO}; font-size: 12px; color: {cc};">{count}</span></button>'

def sel(label,val):
    return f'<label style="display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 12px; border: 1px solid {LINE2}; border-radius: 8px; background: {SURF}; font-size: 14px; color: {INK2};">{label}<select style="appearance: none; border: 0; background: transparent; font: 600 14px {FONT}; color: {INK}; outline: none;"><option>{val}</option></select>{I["chev"]}</label>'

bodyB = f'''<div style="padding: 48px 40px 40px; display: flex; flex-direction: column; gap: 28px;">
<div style="display: grid; grid-template-columns: minmax(0, 1fr) 420px; gap: 40px; align-items: end;">
<div style="display: flex; flex-direction: column; gap: 12px;">
<h1 style="margin: 0; font-size: 56px; font-weight: 700; letter-spacing: -0.035em; line-height: 1.02;">Задачи от бизнеса</h1>
<p style="margin: 0; font-size: 18px; line-height: 1.5; color: {INK2}; max-width: 640px;">Выберите задачу и отправьте своё решение. Рейтинг показывает, насколько полно описана задача: чем он выше, тем меньше уточнений понадобится на старте.</p>
</div>
<div style="display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px; background: {LINE}; border: 1px solid {LINE}; border-radius: 10px; overflow: hidden;">
<div style="background: {SURF}; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px;"><span style="font-family: {MONO}; font-size: 12px; color: {INK3};">0–39</span><span style="font-size: 13px; font-weight: 600;">Черновик</span></div>
<div style="background: {SURF}; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px;"><span style="font-family: {MONO}; font-size: 12px; color: {INK3};">40–69</span><span style="font-size: 13px; font-weight: 600;">Рабочая</span></div>
<div style="background: {SURF}; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px;"><span style="font-family: {MONO}; font-size: 12px; color: {INK3};">70–89</span><span style="font-size: 13px; font-weight: 600; color: {ACCD};">Готовая</span></div>
<div style="background: {ACC}; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px; color: #FFFFFF;"><span style="font-family: {MONO}; font-size: 12px; color: #C9D3FA;">90–100</span><span style="font-size: 13px; font-weight: 600;">Приоритетная</span></div>
</div>
</div>
<div style="display: flex; align-items: center; gap: 8px; padding: 12px; background: {SURF}; border: 1px solid {LINE}; border-radius: 12px;">
{chip("Все",7,True)}{chip("Приоритетные",2)}{chip("Готовые",2)}{chip("Рабочие",2)}{chip("Черновики",1)}
<div style="flex-grow: 1;"></div>
{sel("Тема","Все темы")}{sel("Порядок","По рейтингу")}
<label style="display: flex; align-items: center; gap: 8px; width: 240px; height: 40px; padding: 0 12px; border: 1px solid {LINE2}; border-radius: 8px; background: {SURF}; color: {INK3};"><span style="position: absolute; width: 1px; height: 1px; overflow: hidden;">Поиск</span>{I["search"]}<input type="search" placeholder="Поиск по задачам" style="border: 0; outline: none; background: transparent; font: 400 14px {FONT}; color: {INK}; width: 100%;"></label>
</div>
<div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px;">
{"".join(cardB(i,t) for i,t in enumerate(TASKS))}
</div>
</div>'''
open(R+'VariantB.dc.html','w').write(page('Каталог — вариант B, витрина',1440,1800,bodyB))

now=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
canvas={"v":3,"createdOnFiles":{"v":1,"at":now},"title":"AI Sana — дизайн","launch":{"view":"canvas"},"pages":[],
 "boards":{"Main.dc.html":{"x":0,"y":0,"w":1440,"h":1420,"title":"A · Реестр — плотный список с фильтрами слева"},
           "VariantB.dc.html":{"x":1520,"y":0,"w":1440,"h":1800,"title":"B · Витрина — карточки и фильтры-чипы сверху"}},
 "order":["Main.dc.html","VariantB.dc.html"],
 "notes":{"t1":{"x":0,"y":-300,"text":"Каталог: два варианта композиции","kind":"title1","maxW":2960}},"designSystems":[]}
json.dump(canvas,open(R+'canvas.json','w'),ensure_ascii=False,indent=1)
