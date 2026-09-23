from ds import *
R='/tmp/claude-0/-home-claude/4fb9a2df-5978-53ad-9997-837627599b25/scratchpad/canvas/project/'
def W(name,html): open(R+name,'w').write(html)

RAW='Пациенты часто забывают о записи в нашу клинику и не приходят. Администратор обзванивает всех вручную. Хотим, чтобы напоминания приходили автоматически и пациент мог сам подтвердить или перенести визит.'
def ctop(step,title,sub):
    return f'''<div style="display: flex; flex-direction: column; gap: 28px;">
<div style="display: flex; justify-content: space-between; align-items: center;">{crumbs([("Мои задачи","#"),("Новая задача",None)])}<span style="font-size: 13px; color: {INK3};">Черновик сохранён · 14:32</span></div>
{stepper(step)}
<div style="display: flex; flex-direction: column; gap: 8px;"><h1 style="margin: 0; font-size: 40px; font-weight: 700; letter-spacing: -0.03em; line-height: 1.1;">{title}</h1><p style="margin: 0; font-size: 17px; line-height: 1.5; color: {INK2}; max-width: 760px;">{sub}</p></div></div>'''

def shell(inner,aside,cols='minmax(0, 1fr) 380px'):
    return f'<div style="padding: 40px 80px; display: grid; grid-template-columns: {cols}; gap: 40px; align-items: start;"><div style="display: flex; flex-direction: column; gap: 24px; min-width: 0;">{inner}</div><aside style="display: flex; flex-direction: column; gap: 16px;">{aside}</aside></div>'

# ---- Step 1: draft
form = panel(f'''
{field("Опишите задачу своими словами", ta(RAW,"Что происходит сейчас и что вы хотите изменить?","raw",6,focus=True), hint="Пишите как есть. На следующем шаге AI задаст уточняющие вопросы — он не дописывает факты за вас.", meta=f'<span style="font-family: {MONO}; font-size: 12px; color: {INK3};">198 / 10 000</span>', fid="raw")}
<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px;">
{field("Рабочее название", inp("Напоминания пациентам о записи","Например: Прогноз загрузки столовой","title"), hint="Можно изменить позже", fid="title")}
{field("Отрасль", select("Медицина и услуги","ind"), fid="ind")}
</div>
<div style="display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px solid {LINE};"><span style="font-size: 14px; color: {INK3};">Шаг 1 из 4</span><div style="display: flex; gap: 12px;">{btn("Отмена","ghost")}{btn("Проверить полноту","primary",'',None,'md',False)}</div></div>''',32,24)
aside = panel(f'''{eyebrow("Как считается рейтинг")}
<p style="margin: 0; font-size: 14px; line-height: 1.5; color: {INK2};">Баллы начисляются только за заполненные и подтверждённые поля карточки.</p>
<div style="display: flex; flex-direction: column;">{"".join(f'<div style="display: flex; justify-content: space-between; padding: 9px 0; border-top: 1px solid {LINE}; font-size: 14px;"><span>{l}</span><span style="font-family: {MONO}; color: {INK2};">{m}</span></div>' for _,l,m in FIELDS)}</div>
<p style="margin: 0; font-size: 13px; line-height: 1.5; color: {INK3};">Текст короче 30 символов даёт половину баллов поля.</p>''',24,14)
W('Create1Draft.dc.html',page('Новая задача — описание',1440,1000,f'<div style="padding: 40px 80px 0;">{ctop(1,"Опишите задачу","Начните с короткого описания. Карточку, рейтинг и публикацию соберём по шагам.")}</div>'+shell(form,aside),'business','Мои задачи'))

# ---- Step 1 error
form_e = panel(f'''
{alert("error","Проверьте 2 поля","Без описания и отрасли AI не сможет подобрать уточняющие вопросы.")}
{field("Опишите задачу своими словами", ta("Нужен бот","Что происходит сейчас и что вы хотите изменить?","raw2",6,invalid=True), error="Описание слишком короткое: 10 символов. Напишите хотя бы 2–3 предложения — что происходит сейчас и что нужно изменить.", meta=f'<span style="font-family: {MONO}; font-size: 12px; color: {ERR};">10 / мин. 30</span>', fid="raw2")}
<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px;">
{field("Рабочее название", inp("","Например: Прогноз загрузки столовой","title2"), hint="Необязательно — предложим после уточнения", fid="title2")}
{field("Отрасль", f'<span style="display: flex; align-items: center; height: 44px; box-sizing: border-box; padding: 0 12px; border: 1.5px solid {ERR}; border-radius: 8px; background: {ERRS};"><select id="ind2" aria-invalid="true" style="appearance: none; border: 0; background: transparent; font: 400 15px {FONT}; color: {INK3}; outline: none; flex-grow: 1;"><option>Выберите отрасль</option></select><span style="color: {INK3}; display: flex;">{I["chev"]}</span></span>', error="Выберите отрасль — по ней команды фильтруют каталог", fid="ind2")}
</div>
<div style="display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px solid {LINE};"><span style="font-size: 14px; color: {INK3};">Шаг 1 из 4</span><div style="display: flex; gap: 12px;">{btn("Отмена","ghost")}{btn("Проверить полноту","primary")}</div></div>''',32,24)
W('Create1Error.dc.html',page('Новая задача — ошибка ввода',1440,1060,f'<div style="padding: 40px 80px 0;">{ctop(1,"Опишите задачу","Начните с короткого описания. Карточку, рейтинг и публикацию соберём по шагам.")}</div>'+shell(form_e,aside),'business','Мои задачи'))

# ---- Step 2: questions
found = f'''<div style="display: flex; flex-direction: column; gap: 12px;">
<div style="display: flex; justify-content: space-between; align-items: center;">{eyebrow("Ваше описание")}<a href="#" style="display: inline-flex; gap: 6px; align-items: center; font-size: 14px; text-decoration: none;">{I["edit"]}Изменить</a></div>
<blockquote style="margin: 0; padding: 0; font-size: 16px; line-height: 1.55; color: {INK};">«{RAW}»</blockquote>
<div style="display: flex; flex-wrap: wrap; gap: 8px; padding-top: 4px;">
<span style="font-size: 13px; color: {INK3}; align-self: center; margin-right: 4px;">Найдено в тексте:</span>
<span style="display: inline-flex; align-items: center; gap: 4px; height: 26px; padding: 0 10px; border-radius: 13px; background: {OKS}; color: {OK}; font-size: 13px; font-weight: 600;">{I["check"]}Контекст</span>
<span style="display: inline-flex; align-items: center; gap: 4px; height: 26px; padding: 0 10px; border-radius: 13px; background: {OKS}; color: {OK}; font-size: 13px; font-weight: 600;">{I["check"]}Потребность</span>
<span style="display: inline-flex; align-items: center; height: 26px; padding: 0 10px; border-radius: 13px; background: {NEU}; color: {INK2}; font-size: 13px; font-weight: 600;">Пользователи — кратко</span>
</div></div>'''
def q(n,text,why,fieldname,pts,value='',focus=False,skipped=False):
    fid=f'q{n}'
    top=f'<div style="display: flex; justify-content: space-between; gap: 16px; align-items: flex-start;"><label for="{fid}" style="display: flex; gap: 12px; font-size: 17px; font-weight: 600; line-height: 1.4;"><span style="font-family: {MONO}; font-size: 14px; color: {INK3}; padding-top: 2px;">{n:02d}</span>{text}</label><span style="flex-shrink: 0; display: inline-flex; align-items: center; height: 26px; padding: 0 10px; border-radius: 6px; background: {ACCS}; color: {ACCD}; font-family: {MONO}; font-size: 12px; font-weight: 600;">{fieldname} · до +{pts}</span></div>'
    return f'''<div style="display: flex; flex-direction: column; gap: 10px; padding: 20px 0; border-top: 1px solid {LINE};">{top}
<div style="padding-left: 30px; display: flex; flex-direction: column; gap: 8px;"><div style="font-size: 13px; color: {INK3};">{why}</div>{ta(value,"Ваш ответ","" if False else fid,3,focus=focus)}
<div style="display: flex; justify-content: flex-end;"><button type="button" style="border: 0; background: transparent; padding: 6px 0; font: 500 13px {FONT}; color: {INK3};">Пропустить вопрос</button></div></div></div>'''
qs = panel(f'''<div style="display: flex; justify-content: space-between; align-items: center;"><h2 style="margin: 0; font-size: 22px; font-weight: 600;">4 уточняющих вопроса</h2><span style="display: inline-flex; gap: 6px; align-items: center; font-size: 13px; color: {INK3};">{I["spark"]}Составлено AI по вашему тексту</span></div>
<div>
{q(1,"Какие данные о записях вы можете передать команде?","Команде нужно понять, с чем работать: таблицы, выгрузки, примеры.","Данные",20,"Выгрузка из Google Таблицы за 4 месяца: дата, время, врач, пришёл ли пациент. Имена и телефоны уберём.")}
{q(2,"Что команда должна показать в конце работы?","Опишите конкретный результат: прототип, бот, отчёт.","Результат",15,"Рабочий прототип бота, который",focus=True)}
{q(3,"По какому показателю вы поймёте, что решение работает?","Измеримый признак: доля, время, количество.","Критерии",15)}
{q(4,"Есть ли ограничения по срокам, каналам или данным?","Например: срок, мессенджер, запрет хранить медданные.","Ограничения",10)}
</div>
<div style="display: flex; justify-content: space-between; align-items: center; padding-top: 16px; border-top: 1px solid {LINE};">{btn("Назад","ghost",I["back"])}<div style="display: flex; gap: 12px; align-items: center;"><span style="font-size: 14px; color: {INK3};">Отвечено 1 из 4</span>{btn("Собрать карточку","primary",'')}</div></div>''',32,16)
aside2 = panel(f'''{eyebrow("Прогноз рейтинга")}
<div style="display: flex; align-items: baseline; gap: 10px;"><span style="font-family: {MONO}; font-size: 40px; font-weight: 600; letter-spacing: -0.03em;">25</span><span style="font-family: {MONO}; font-size: 20px; color: {INK3};">→ до 95</span></div>
{meter(25,None,332,8)}
<p style="margin: 0; font-size: 14px; line-height: 1.5; color: {INK2};">Сейчас задача — черновик. Ответы на все вопросы поднимут её до уровня «Приоритетная» и в верх каталога.</p>''',24,14) + alert('info','AI только спрашивает','Карточка соберётся из вашего текста и ответов. Новых фактов AI не добавляет — всё можно отредактировать перед публикацией.')
W('Create2Questions.dc.html',page('Новая задача — уточнение',1440,1560,f'<div style="padding: 40px 80px 0;">{ctop(2,"Ответьте на вопросы","Мы нашли в описании контекст и потребность. Чтобы команды могли начать без созвонов, не хватает ещё нескольких сведений.")}</div>'+shell(panel(found,28,16)+qs,aside2),'business','Мои задачи'))

# ---- Step 3: editable card, low rating
LOW={'context':10,'need':10,'users':5,'data':0,'constraints':0,'expected_result':0,'success_criteria':0,'contact':10}
VALS={'context':'Клиника принимает около 60 пациентов в день. Запись ведётся в Google Таблице, администратор напоминает о визите по телефону.',
      'need':'Автоматически напоминать пациентам о визите и давать подтвердить или перенести запись без звонка.',
      'users':'Пациенты',
      'data':'','constraints':'','expected_result':'','success_criteria':'',
      'contact':'Главный администратор Айгерим. Консультации по вторникам в 15:00, ответ в Telegram в течение дня.'}
PH={'data':'Какие таблицы, выгрузки или примеры получит команда?','constraints':'Сроки, технологии, доступы, запреты','expected_result':'Что конкретно команда должна сдать','success_criteria':'Как измерить, что решение работает','users':'Для кого создаётся решение'}
def card_field(k,lab,mx,vals,texts,rows=2):
    e=vals[k]; v=texts[k]
    src = f'<span style="font-size: 12px; color: {INK3};">из вашего описания</span>' if k in ('context','need') else (f'<span style="font-size: 12px; color: {INK3};">из ответа</span>' if v and k!='contact' and k!='users' else '')
    meta=f'<span style="display: flex; gap: 12px; align-items: center;">{src}{state_tag(e,mx)}<span style="font-family: {MONO}; font-size: 12px; color: {INK3}; min-width: 40px; text-align: right;">{fmt(e)}/{mx}</span></span>'
    return field(lab, ta(v,PH.get(k,''),f'f_{k}',rows), meta=meta, fid=f'f_{k}')
def card_form(vals,texts,title):
    return panel(f'''{field("Название задачи", inp(title,"","f_title"), fid="f_title")}
{"".join(card_field(k,l,m,vals,texts) for k,l,m in FIELDS)}''',32,22)

aside3 = panel(f'''{eyebrow("Рейтинг готовности")}{score_block(35,332,48)}
{alert("draft","Задача будет отмечена как черновик","Её увидят в каталоге и смогут откликнуться, но командам придётся уточнять детали. Добавьте сведения — рейтинг пересчитается сразу.")}
<div style="display: flex; flex-direction: column; gap: 4px;"><div style="display: flex; justify-content: space-between; align-items: baseline;">{eyebrow("Что повысит рейтинг")}<span style="font-family: {MONO}; font-size: 12px; color: {INK3};">до +65</span></div>{missing(LOW)}</div>
<div style="display: flex; flex-direction: column; gap: 10px; padding-top: 4px;">{btn("Подтвердить карточку","primary",'',None,'md',True)}<span style="font-size: 13px; line-height: 1.45; color: {INK3}; text-align: center;">Публикация доступна при любом рейтинге</span></div>''',24,18)
W('Create3Card.dc.html',page('Новая задача — карточка, низкий рейтинг',1440,1780,f'<div style="padding: 40px 80px 0;">{ctop(3,"Проверьте карточку","Карточка собрана из вашего текста и ответов. Отредактируйте любое поле — баллы пересчитываются после сохранения.")}</div>'+shell(card_form(LOW,VALS,"Напоминания пациентам о записи"),aside3),'business','Мои задачи'))

# ---- Step 4: confirm
FULL={'context':10,'need':10,'users':10,'data':20,'constraints':5,'expected_result':15,'success_criteria':15,'contact':10}
FV=dict(VALS, users='Пациенты клиники и два администратора регистратуры.',
  data='Обезличенная выгрузка записей за 4 месяца из Google Таблицы: дата, время, врач, статус визита.',
  constraints='6 недель, Telegram.',
  expected_result='Рабочий прототип бота: за сутки до приёма присылает напоминание и принимает ответ «приду» или «перенести».',
  success_criteria='Доля неявок снижается с 12% до 6% за месяц пилота; обзвон занимает у администратора меньше 30 минут в день.')
def ro(lab,v,e,mx):
    return f'<div style="display: grid; grid-template-columns: 200px minmax(0, 1fr) 90px; gap: 20px; padding: 16px 0; border-top: 1px solid {LINE};"><span style="font-size: 14px; font-weight: 600;">{lab}</span><span style="font-size: 15px; line-height: 1.5; color: {INK2};">{v}</span><span style="display: flex; justify-content: flex-end;">{state_tag(e,mx)}</span></div>'
preview = panel(f'''<div style="display: flex; justify-content: space-between; align-items: center;">{eyebrow("Итоговая карточка")}<a href="#" style="display: inline-flex; gap: 6px; align-items: center; font-size: 14px; text-decoration: none;">{I["edit"]}Вернуться к редактированию</a></div>
<h2 style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.02em;">Напоминания пациентам о записи</h2>
<div style="font-size: 14px; color: {INK3};">Медицина и услуги · Клиника «Ақ Тіс»</div>
<div>{"".join(ro(l,FV[k],FULL[k],m) for k,l,m in FIELDS)}</div>''',32,14)
confirm = panel(f'''{checkbox("Я проверил карточку: все сведения указаны мной и могут быть переданы студентам")}
{checkbox("Решение о выборе команды я приму сам — система никого не назначает", on=True)}
<div style="font-size: 13px; color: {INK3}; padding-left: 28px;">Отметьте первый пункт, чтобы кнопка публикации стала активной.</div>
<div style="display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px solid {LINE};">{btn("Назад к карточке","ghost",I["back"])}<div style="display: flex; gap: 12px;">{btn("Сохранить черновик","secondary")}{btn("Опубликовать в каталоге","disabled")}</div></div>''',24,12)
growth = panel(f'''{eyebrow("Рост рейтинга")}
<div style="display: flex; align-items: center; gap: 16px;"><div style="display: flex; flex-direction: column; gap: 4px;"><span style="font-size: 12px; color: {INK3};">Было</span><span style="font-family: {MONO}; font-size: 28px; font-weight: 600; color: {INK3};">35</span></div><span style="color: {INK3};">{I["arrow"]}</span><div style="display: flex; flex-direction: column; gap: 4px;"><span style="font-size: 12px; color: {INK3};">Стало</span><span style="font-family: {MONO}; font-size: 28px; font-weight: 600;">95</span></div><span style="margin-left: auto; font-family: {MONO}; font-size: 16px; font-weight: 600; color: {OK};">+60</span></div>
{score_block(95,332,36)}
<div style="display: flex; flex-direction: column; gap: 6px; padding: 14px; border-radius: 10px; background: {BG};"><span style="font-size: 14px; font-weight: 600;">Позиция в каталоге: 1 из 8</span><span style="font-size: 13px; line-height: 1.45; color: {INK2};">Приоритетные задачи выделяются и стоят первыми.</span></div>
<div style="display: flex; justify-content: space-between; font-size: 14px; padding-top: 4px;"><span style="color: {INK2};">Ограничения описаны кратко</span><span style="font-family: {MONO}; font-weight: 600; color: {ACCD};">+5</span></div>''',24,16)
W('Create4Confirm.dc.html',page('Новая задача — подтверждение',1440,1500,f'<div style="padding: 40px 80px 0;">{ctop(4,"Подтвердите и опубликуйте","Опубликованную задачу увидят все студенческие команды. Её можно дополнить позже — рейтинг пересчитается.")}</div>'+shell(preview+confirm,growth),'business','Мои задачи'))

# ---- Published success
succ = f'''<div style="padding: 64px 80px; display: flex; justify-content: center;"><div style="width: 760px; display: flex; flex-direction: column; gap: 24px;">
<div style="display: flex; flex-direction: column; align-items: flex-start; gap: 20px; padding: 40px; background: {SURF}; border: 1px solid {LINE}; border-radius: 16px;">
<span style="width: 56px; height: 56px; border-radius: 28px; background: {OKS}; color: {OK}; display: flex; align-items: center; justify-content: center;">{I["checkL"]}</span>
<div style="display: flex; flex-direction: column; gap: 10px;"><h1 style="margin: 0; font-size: 36px; font-weight: 700; letter-spacing: -0.03em;">Задача опубликована</h1>
<p style="margin: 0; font-size: 17px; line-height: 1.55; color: {INK2};">«Напоминания пациентам о записи» уже в каталоге — на 1-м месте из 8. Команды пришлют предложения, а вы сравните их в кабинете и сами решите, с кем работать.</p></div>
<div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; width: 100%; background: {LINE}; border: 1px solid {LINE}; border-radius: 10px; overflow: hidden;">
<div style="background: {SURF}; padding: 16px; display: flex; flex-direction: column; gap: 6px;"><span style="font-size: 13px; color: {INK3};">Рейтинг</span><span style="display: flex; gap: 10px; align-items: center;"><span style="font-family: {MONO}; font-size: 24px; font-weight: 600;">95</span>{badge("priority")}</span></div>
<div style="background: {SURF}; padding: 16px; display: flex; flex-direction: column; gap: 6px;"><span style="font-size: 13px; color: {INK3};">Позиция</span><span style="font-family: {MONO}; font-size: 24px; font-weight: 600;">1 / 8</span></div>
<div style="background: {SURF}; padding: 16px; display: flex; flex-direction: column; gap: 6px;"><span style="font-size: 13px; color: {INK3};">Предложений</span><span style="font-family: {MONO}; font-size: 24px; font-weight: 600;">0</span></div></div>
<div style="display: flex; gap: 12px;">{btn("Открыть в каталоге","primary",'',"#")}{btn("Перейти в кабинет","secondary",'',"#")}</div>
</div></div></div>'''
W('Published.dc.html',page('Задача опубликована',1440,820,succ,'business','Мои задачи'))
