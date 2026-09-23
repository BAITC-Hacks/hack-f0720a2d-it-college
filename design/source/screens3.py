from ds import *
R='/tmp/claude-0/-home-claude/4fb9a2df-5978-53ad-9997-837627599b25/scratchpad/canvas/project/'
def W(name,html): open(R+name,'w').write(html)

def sec(lab,text,e,mx):
    empty = not text
    body = f'<p style="margin: 0; font-size: 16px; line-height: 1.6; color: {INK3 if empty else INK}; {"font-style: italic;" if empty else ""}">{text or "Бизнес пока не указал эти сведения — уточните в отклике или на консультации."}</p>'
    return f'<div style="display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: 24px; padding: 20px 0; border-top: 1px solid {LINE};"><div style="display: flex; flex-direction: column; gap: 6px;"><h3 style="margin: 0; font-size: 15px; font-weight: 600;">{lab}</h3>{state_tag(e,mx)}</div>{body}</div>'

def task_page(t, vals, texts, formhtml, extra_top=''):
    lv=level(t['s'])
    strip = f'<div style="height: 4px; background: {ACC}; border-radius: 12px 12px 0 0; margin: -1px -1px 0;"></div>' if lv=='priority' else ''
    hero = f'''<section style="display: flex; flex-direction: column; background: {SURF}; border: 1px solid {LINE}; border-radius: 12px;">{strip}<div style="padding: 32px; display: flex; flex-direction: column; gap: 20px;">
<div style="display: flex; gap: 8px; align-items: center; font-size: 14px; color: {INK2};"><span style="font-weight: 600;">{t["ind"]}</span><span style="color: {INK3};">·</span><span>{t["org"]}</span><span style="color: {INK3};">·</span><span style="color: {INK3};">опубликована {t["date"]}</span></div>
<h1 style="margin: 0; font-size: 44px; font-weight: 700; letter-spacing: -0.03em; line-height: 1.08;">{t["t"]}</h1>
<div style="display: flex; flex-direction: column; gap: 8px; padding: 20px; border-radius: 10px; background: {BG};">{eyebrow("Ожидаемый результат")}<p style="margin: 0; font-size: 19px; line-height: 1.5; font-weight: 500; color: {INK if texts["expected_result"] else INK3}; {"" if texts["expected_result"] else "font-style: italic;"}">{texts["expected_result"] or "Не указан. Предложите свой вариант результата в отклике."}</p></div>
{extra_top}
</div></section>'''
    secs = panel(f'<h2 style="margin: 0; font-size: 22px; font-weight: 600;">Описание задачи</h2><div>'+''.join(sec(l,texts[k],vals[k],m) for k,l,m in FIELDS if k!='expected_result')+'</div>',32,8)
    rating = panel(f'''<div style="display: flex; justify-content: space-between; align-items: center;">{eyebrow("Готовность описания")}<a href="#" style="font-size: 13px; text-decoration: none;">Как считается</a></div>
{score_block(t["s"],332,48)}
{breakdown(vals)}
{('<div style="display: flex; flex-direction: column; gap: 4px;">'+eyebrow("Не хватает")+missing(vals)+'</div>') if t["s"]<100 else ''}
<p style="margin: 0; font-size: 13px; line-height: 1.5; color: {INK3};">Рейтинг показывает полноту описания задачи, а не известность компании. Отклик открыт при любом уровне.</p>''',24,18)
    left = f'<div style="display: flex; flex-direction: column; gap: 24px; min-width: 0;">{crumbs([("Каталог","#"),(t["t"],None)])}{hero}{secs}</div>'
    right = f'<aside style="display: flex; flex-direction: column; gap: 16px; padding-top: 44px;">{rating}{formhtml}</aside>'
    return f'<div style="padding: 32px 80px 40px; display: grid; grid-template-columns: minmax(0, 1fr) 420px; gap: 40px; align-items: start;">{left}{right}</div>'

def pform(idea='',plan='',dl='',link='',errors=None,team='Data Sparks'):
    errors=errors or {}
    summ = alert("error",f"Проверьте {len(errors)} поля","Исправьте отмеченные поля — остальное сохранится.") if errors else ''
    return panel(f'''<div style="display: flex; flex-direction: column; gap: 6px;"><h2 style="margin: 0; font-size: 22px; font-weight: 600;">Предложить решение</h2><span style="font-size: 14px; color: {INK2};">От команды <b style="font-weight: 600; color: {INK};">{team}</b> · число откликов не ограничено</span></div>
{summ}
{field("Идея решения",ta(idea,"Как вы решите задачу и почему так","p_idea",4,invalid="idea" in errors),error=errors.get("idea",""),meta=f'<span style="font-family: {MONO}; font-size: 12px; color: {ERR if "idea" in errors else INK3};">{len(idea)} / мин. 10</span>',fid="p_idea")}
{field("План работы",ta(plan,"Этапы: что сделаете на каждой неделе","p_plan",4,invalid="plan" in errors),error=errors.get("plan",""),fid="p_plan")}
<div style="display: grid; grid-template-columns: 140px minmax(0, 1fr); gap: 12px;">
{field("Срок",inp(dl,"3 недели","p_dl",invalid="dl" in errors),fid="p_dl")}
{field("Ссылка на прототип",inp(link,"https://","p_link",invalid="link" in errors,t="url"),fid="p_link")}
</div>
{''.join(f'<div role="alert" style="display: flex; gap: 6px; font-size: 13px; line-height: 1.45; font-weight: 500; color: {ERR};"><span style="flex-shrink: 0; margin-top: 1px;">{I["alertS"]}</span>{errors[k]}</div>' for k in ("dl","link") if k in errors)}
{btn("Отправить предложение","primary",'',None,'md',True)}
<span style="font-size: 13px; line-height: 1.45; color: {INK3}; text-align: center;">Бизнес сравнит все отклики и сам решит, с кем работать.</span>''',24,18)

T1=dict(t='Прогноз загрузки столовой колледжа',ind='Образование',org='Колледж цифровых технологий',s=95,date='18 сентября')
V1={'context':10,'need':10,'users':10,'data':20,'constraints':5,'expected_result':15,'success_criteria':15,'contact':10}
X1={'context':'В обеденный перерыв в столовой колледжа регулярно собирается очередь больше 40 человек, и часть студентов опаздывает на пары.',
 'need':'Заранее показывать студентам ожидаемую загрузку столовой и свободные интервалы, чтобы поток распределялся равномернее.',
 'users':'Студенты и преподаватели, сотрудники столовой, администратор учебного корпуса.',
 'data':'Обезличенные чеки кассы за 3 месяца, расписание занятий всех групп, ручные замеры очереди по времени за 2 недели.',
 'constraints':'Срок 4 недели, веб.',
 'expected_result':'Веб-прототип, который показывает ожидаемую очередь по 15-минутным интервалам и даёт администратору обновлять данные.',
 'success_criteria':'Ошибка прогноза не выше 15%; студент находит свободный интервал меньше чем за минуту.',
 'contact':'Куратор — заместитель директора по ИТ. Консультации по средам в 16:00, ответ в рабочем чате в течение дня.'}
W('Task.dc.html',page('Карточка задачи',1440,1780,task_page(T1,V1,X1,pform("Построим прогноз по расписанию и истории чеков и покажем загрузку на простой временной шкале.","Неделя 1 — очистка данных. Неделя 2 — базовый прогноз. Неделя 3 — API и интерфейс. Неделя 4 — проверка на пяти студентах.","4 недели","https://datasparks.kz/canteen")),'team','Каталог'))

T2=dict(t='Помощник читателя',ind='Культура',org='Городская библиотека № 3',s=30,date='20 сентября')
V2={'context':5,'need':10,'users':0,'data':10,'constraints':0,'expected_result':0,'success_criteria':0,'contact':5}
X2={'context':'Большая библиотека.','need':'Посетителям сложно находить нужные книги и залы, библиотекари тратят время на однотипные вопросы.',
 'users':'','data':'Каталог','constraints':'','expected_result':'','success_criteria':'','contact':'Telegram @lib3'}
lowbanner = alert("draft","Описание черновое — отклик всё равно открыт","Бизнес заполнил задачу на 30 из 100. Командам, скорее всего, понадобится созвон, чтобы уточнить результат и данные. Эти вопросы можно задать прямо в предложении.")
W('TaskLow.dc.html',page('Карточка задачи — низкий рейтинг и ошибки формы',1440,2060,task_page(T2,V2,X2,pform("Карта","","","culturelab",{"idea":"Слишком коротко: 5 символов. Опишите идею хотя бы одним предложением — минимум 10 символов.","plan":"Добавьте план: какие этапы и что будет готово в конце.","dl":"Укажите срок, например «3 недели».","link":"Ссылка должна начинаться с https:// — например https://culturelab.kz"},team="Culture Lab"),lowbanner),'team','Каталог'))

# success sent
sent = panel(f'''<span style="width: 48px; height: 48px; border-radius: 24px; background: {OKS}; color: {OK}; display: flex; align-items: center; justify-content: center;">{I["checkL"]}</span>
<div style="display: flex; flex-direction: column; gap: 8px;"><h2 style="margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.01em;">Предложение отправлено</h2><p style="margin: 0; font-size: 15px; line-height: 1.55; color: {INK2};">Колледж цифровых технологий получил ваш отклик. Решение принимает бизнес вручную — статус изменится в разделе «Мои отклики».</p></div>
<div style="display: flex; flex-direction: column; border-top: 1px solid {LINE};">
<div style="display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid {LINE}; font-size: 14px;"><span style="color: {INK3};">Статус</span><span style="display: inline-flex; align-items: center; height: 24px; padding: 0 10px; border-radius: 6px; background: {NEU}; font-size: 13px; font-weight: 600;">На рассмотрении</span></div>
<div style="display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid {LINE}; font-size: 14px;"><span style="color: {INK3};">Срок</span><span>4 недели</span></div>
<div style="display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid {LINE}; font-size: 14px;"><span style="color: {INK3};">Прототип</span><a href="#" style="text-decoration: none;">datasparks.kz/canteen</a></div>
<div style="display: flex; justify-content: space-between; padding: 12px 0; font-size: 14px;"><span style="color: {INK3};">Других откликов</span><span style="font-family: {MONO};">4</span></div></div>
<div style="display: flex; gap: 10px;">{btn("Мои отклики","primary",'',"#")}{btn("В каталог","secondary",'',"#")}</div>''',24,20)
W('ProposalSent.dc.html',page('Карточка задачи — предложение отправлено',1440,1780,task_page(T1,V1,X1,sent),'team','Каталог'))
