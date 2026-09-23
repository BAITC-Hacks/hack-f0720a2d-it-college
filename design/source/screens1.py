from ds import *
R='/tmp/claude-0/-home-claude/4fb9a2df-5978-53ad-9997-837627599b25/scratchpad/canvas/project/'
def W(name,html): open(R+name,'w').write(html)

TASKS=[
 dict(t='Прогноз загрузки столовой колледжа',ind='Образование',org='Колледж цифровых технологий',s=95,
      res='Веб-прототип, который показывает ожидаемую очередь по 15-минутным интервалам и даёт администратору обновлять данные.',data='Чеки за 3 месяца, расписание',term='4 недели',n=4),
 dict(t='Отчёт по остаткам небольшого магазина',ind='Ритейл',org='ИП «Береке Маркет»',s=90,
      res='Интерактивный отчёт с динамикой продаж и списком товаров, которые пора пополнить на этой неделе.',data='CSV продаж и остатков, 6 мес.',term='3 недели',n=2),
 dict(t='Единая панель заявок на ремонт',ind='ЖКХ',org='КСК «Сарыарка-12»',s=80,
      res='Реестр обращений жителей с фильтрами, ответственными и сменой статуса заявки.',data='Таблица обращений за полгода',term='3 недели',n=3),
 dict(t='Расписание волонтёрских смен',ind='Социальная сфера',org='ОФ «Қамқор»',s=75,
      res='Страница записи на смены и обзор заполненности для координатора мероприятия.',data='Шаблоны прошлых расписаний',term='4 недели',n=1),
 dict(t='Telegram-бот записи на техосмотр',ind='Транспорт',org='СТО «АвтоДом»',s=60,
      res='Бот, который показывает свободные окна и записывает клиента без звонка администратору.',data='Не указаны',term='Не указан',n=0),
 dict(t='Учёт посещаемости спортивных секций',ind='Спорт',org='Спорткомплекс «Жастар»',s=45,
      res='Электронный журнал посещений с отчётом для тренера за месяц.',data='Бумажные журналы',term='Не указан',n=0),
 dict(t='Помощник читателя',ind='Культура',org='Городская библиотека № 3',s=30,
      res=None,data='Каталог (без описания)',term='Не указан',n=1),
]

COLS='40px minmax(0, 1fr) 200px 190px'
def rowA(i,t):
    s=t['s']; lv=level(s)
    draftnote = f'<span style="align-self: flex-start; padding: 4px 10px; border-radius: 6px; border: 1px dashed {LINE2}; font-size: 13px; color: {INK2};">Требует уточнения · отклик открыт</span>' if lv=='draft' else ''
    res = f'<span style="color: {INK3}; font-style: italic;">не указан</span>' if not t['res'] else f'<span style="color: {INK2};">{t["res"]}</span>'
    return f'''<a href="#" style="display: grid; grid-template-columns: {COLS}; column-gap: 24px; align-items: start; padding: 22px 24px; background: {SURF}; border-bottom: 1px solid {LINE}; text-decoration: none; color: {INK};">
<div style="font-family: {MONO}; font-size: 15px; font-weight: 600; color: {INK3}; padding-top: 3px;">{i:02d}</div>
<div style="display: flex; flex-direction: column; gap: 8px; min-width: 0;">
<div style="font-size: 21px; font-weight: 600; line-height: 1.25; letter-spacing: -0.01em;">{t["t"]}</div>
<div style="display: flex; gap: 8px; font-size: 15px; line-height: 1.45;"><span style="color: {INK3}; flex-shrink: 0;">Результат:</span>{res}</div>
<div style="display: flex; gap: 8px; align-items: center; font-size: 13px; color: {INK3};"><span style="color: {INK2}; font-weight: 500;">{t["ind"]}</span><span>·</span><span>{t["org"]}</span></div>
{draftnote}
</div>
<div style="display: flex; flex-direction: column; gap: 6px; font-size: 14px; color: {INK2}; padding-top: 4px;"><span style="display: flex; gap: 6px; align-items: center;">{I["data"]}{t["data"]}</span><span style="display: flex; gap: 6px; align-items: center;">{I["clock"]}{t["term"]}</span><span style="display: flex; gap: 6px; align-items: center;">{I["resp"]}{t["n"]} {"отклик" if t["n"]==1 else "отклика" if 2<=t["n"]<=4 else "откликов"}</span></div>
<div style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
<div style="display: flex; align-items: center; gap: 10px;">{badge(lv)}<span style="font-family: {MONO}; font-size: 26px; font-weight: 600; letter-spacing: -0.02em; min-width: 44px; text-align: right;">{fmt(s)}</span></div>
{meter(s,lv,160)}
</div>
</a>'''

def sidebar(levels_on=(True,True,True,True), themes_on=()):
    rng=lambda r: f' <span style="font-family: {MONO}; font-size: 12px; color: {INK3};">{r}</span>'
    th=['Образование','Ритейл','ЖКХ','Социальная сфера','Транспорт','Спорт','Культура']
    return f'''<aside aria-label="Фильтры" style="width: 256px; flex-shrink: 0; display: flex; flex-direction: column; gap: 28px;">
{field("Поиск",f'<span style="display: flex; align-items: center; gap: 8px; height: 44px; box-sizing: border-box; padding: 0 12px; border: 1px solid {LINE2}; border-radius: 8px; background: {SURF}; color: {INK3};">{I["search"]}<input id="q" type="search" placeholder="Название или результат" style="border: 0; outline: none; background: transparent; font: 400 15px {FONT}; color: {INK}; width: 100%;"></span>',fid="q")}
<fieldset style="border: 0; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px;">
<legend style="display: flex; justify-content: space-between; width: 100%; padding: 0 0 6px; font-size: 14px; font-weight: 600;">Готовность описания</legend>
{checkbox("Приоритетная",2,levels_on[0],rng("90–100"))}{checkbox("Готовая",2,levels_on[1],rng("70–89"))}{checkbox("Рабочая",2,levels_on[2],rng("40–69"))}{checkbox("Черновик",1,levels_on[3],rng("0–39"))}
</fieldset>
<fieldset style="border: 0; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px;">
<legend style="padding: 0 0 6px; font-size: 14px; font-weight: 600;">Тема</legend>
{"".join(checkbox(x,1,x in themes_on) for x in th)}
</fieldset>
<div style="padding: 16px; border-radius: 10px; background: {NEU}; font-size: 13px; line-height: 1.5; color: {INK2};">Рейтинг показывает, насколько полно бизнес описал задачу, а не известность компании. Откликнуться можно на любую задачу.</div>
</aside>'''

def table_head():
    return f'''<div style="display: grid; grid-template-columns: {COLS}; column-gap: 24px; padding: 12px 24px; background: {BG}; border-bottom: 1px solid {LINE};">
{eyebrow("№")}{eyebrow("Задача и ожидаемый результат")}{eyebrow("Условия")}<div style="display: flex; justify-content: flex-end;">{eyebrow("Готовность ↓")}</div></div>'''

def cat_top(sub,chips=''):
    return f'''<div style="display: flex; align-items: flex-end; justify-content: space-between; gap: 24px;">
<div style="display: flex; flex-direction: column; gap: 8px;">
<h1 style="margin: 0; font-size: 40px; font-weight: 700; letter-spacing: -0.03em; line-height: 1.1;">Каталог задач</h1>
<p style="margin: 0; font-size: 16px; color: {INK2};">{sub}</p>
</div>
<div style="display: flex; flex-direction: column; gap: 8px; align-items: flex-end;"><label for="sort" style="font-size: 13px; color: {INK3};">Сортировка</label>
<span style="display: flex; align-items: center; gap: 8px; height: 40px; box-sizing: border-box; padding: 0 12px; border: 1px solid {LINE2}; border-radius: 8px; background: {SURF}; color: {INK};">{I["sort"]}<select id="sort" style="appearance: none; border: 0; background: transparent; font: 500 14px {FONT}; color: {INK}; outline: none;"><option>По рейтингу готовности</option><option>Сначала новые</option><option>Меньше откликов</option></select>{I["chev"]}</span></div>
</div>{chips}'''

# --- Catalog main
body = f'''<div style="padding: 40px; display: flex; gap: 40px; align-items: flex-start;">{sidebar()}
<main style="flex-grow: 1; min-width: 0; display: flex; flex-direction: column; gap: 24px;">
{cat_top("7 опубликованных задач. Чем полнее описание, тем выше задача в списке.")}
<div style="border: 1px solid {LINE}; border-radius: 12px; overflow: hidden; background: {SURF};">{table_head()}{"".join(rowA(i+1,t) for i,t in enumerate(TASKS))}</div>
</main></div>'''
W('Main.dc.html',page('Каталог задач',1440,1440,body,'team','Каталог'))

# --- Catalog filtered + empty
def fchip(t): return f'<span style="display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 6px 0 12px; border-radius: 16px; background: {INK}; color: #FFFFFF; font-size: 14px; font-weight: 500;">{t}<button type="button" aria-label="Убрать фильтр {t}" style="width: 24px; height: 24px; border: 0; border-radius: 12px; background: transparent; color: #FFFFFF; display: flex; align-items: center; justify-content: center; padding: 0;">{I["x"]}</button></span>'
chips=f'<div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">{fchip("Приоритетная")}{fchip("Культура")}<a href="#" style="font-size: 14px; margin-left: 4px;">Сбросить все</a></div>'
empty=f'''<div style="display: flex; flex-direction: column; align-items: center; text-align: center; gap: 16px; padding: 72px 40px; background: {SURF}; border: 1px dashed {LINE2}; border-radius: 12px;">
<span style="width: 56px; height: 56px; border-radius: 28px; background: {NEU}; color: {INK2}; display: flex; align-items: center; justify-content: center;">{I["filter"]}</span>
<h2 style="margin: 0; font-size: 24px; font-weight: 600; letter-spacing: -0.01em;">Нет задач с такими фильтрами</h2>
<p style="margin: 0; max-width: 460px; font-size: 16px; line-height: 1.5; color: {INK2};">В теме «Культура» сейчас одна задача, и её описание ещё черновое. Уберите фильтр готовности — задача станет видна, и на неё можно откликнуться.</p>
<div style="display: flex; gap: 12px; margin-top: 8px;">{btn("Показать все уровни","dark")}{btn("Сбросить фильтры","secondary")}</div>
</div>'''
body = f'''<div style="padding: 40px; display: flex; gap: 40px; align-items: flex-start;">{sidebar((True,False,False,False),("Культура",))}
<main style="flex-grow: 1; min-width: 0; display: flex; flex-direction: column; gap: 24px;">
{cat_top("0 из 7 задач по выбранным фильтрам.",'')}{chips}{empty}
</main></div>'''
W('CatalogEmpty.dc.html',page('Каталог — пустой результат',1440,1100,body,'team','Каталог'))
