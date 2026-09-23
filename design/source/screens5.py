from ds import *
R='/tmp/claude-0/-home-claude/4fb9a2df-5978-53ad-9997-837627599b25/scratchpad/canvas/project/'
def W(name,html): open(R+name,'w').write(html)
def sw(name,var,hexv,dark=False,note=''):
    fg='#FFFFFF' if dark else INK
    return f'<div style="display: flex; flex-direction: column; border: 1px solid {LINE}; border-radius: 10px; overflow: hidden; background: {SURF};"><div style="height: 72px; background: {hexv}; color: {fg}; padding: 10px; font-family: {MONO}; font-size: 12px;">{"Aa" if not note else note}</div><div style="padding: 10px 12px; display: flex; flex-direction: column; gap: 2px;"><span style="font-size: 14px; font-weight: 600;">{name}</span><span style="font-family: {MONO}; font-size: 12px; color: {INK2};">{var}</span><span style="font-family: {MONO}; font-size: 12px; color: {INK3};">{hexv}</span></div></div>'
def sect(title,inner,sub=''):
    p = ('<p style="margin: 0; font-size: 15px; color: '+INK2+';">'+sub+'</p>') if sub else ''
    return f'<section style="display: flex; flex-direction: column; gap: 20px;"><div style="display: flex; flex-direction: column; gap: 6px;"><h2 style="margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.015em;">{title}</h2>{p}</div>{inner}</section>'
colors=f'''<div style="display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 16px;">
{sw("Фон","--c-bg",BG)}{sw("Поверхность","--c-surface",SURF)}{sw("Нейтральный","--c-neutral",NEU)}{sw("Линия","--c-line",LINE)}{sw("Линия сильная","--c-line-strong",LINE2)}{sw("Акцент","--c-accent",ACC,True)}
{sw("Графит","--c-ink",INK,True)}{sw("Текст 2","--c-ink-2",INK2,True)}{sw("Текст 3","--c-ink-3",INK3,True)}{sw("Акцент мягкий","--c-accent-soft",ACCS)}{sw("Акцент тёмный","--c-accent-dark",ACCD,True)}
<div style="display: grid; grid-template-rows: repeat(2, minmax(0, 1fr)); gap: 8px;"><div style="border-radius: 10px; background: {ERRS}; color: {ERR}; padding: 10px 12px; font-size: 13px; display: flex; flex-direction: column; justify-content: center;"><b style="font-weight: 600;">Ошибка</b><span style="font-family: {MONO}; font-size: 11px;">--c-error {ERR}</span></div><div style="border-radius: 10px; background: {OKS}; color: {OK}; padding: 10px 12px; font-size: 13px; display: flex; flex-direction: column; justify-content: center;"><b style="font-weight: 600;">Успех</b><span style="font-family: {MONO}; font-size: 11px;">--c-success {OK}</span></div></div>
</div>'''
def trow(tok,spec,sample,style):
    return f'<div style="display: grid; grid-template-columns: 180px 220px minmax(0, 1fr); gap: 24px; align-items: baseline; padding: 14px 0; border-top: 1px solid {LINE};"><span style="font-family: {MONO}; font-size: 12px; color: {INK2};">{tok}</span><span style="font-family: {MONO}; font-size: 12px; color: {INK3};">{spec}</span><span style="{style}">{sample}</span></div>'
type_=f'''<div style="display: flex; flex-direction: column;">
{trow("--fs-display","Onest 700 · 44 / 1.08 · −3%","Прогноз загрузки столовой",f"font-size: 44px; font-weight: 700; letter-spacing: -0.03em; line-height: 1.08;")}
{trow("--fs-h1","Onest 700 · 40 / 1.1 · −3%","Каталог задач",f"font-size: 40px; font-weight: 700; letter-spacing: -0.03em; line-height: 1.1;")}
{trow("--fs-h2","Onest 600 · 22","Расшифровка рейтинга",f"font-size: 22px; font-weight: 600;")}
{trow("--fs-title","Onest 600 · 21 / 1.25","Единая панель заявок на ремонт",f"font-size: 21px; font-weight: 600; letter-spacing: -0.01em;")}
{trow("--fs-lead","Onest 400 · 17 / 1.5","Чем полнее описание, тем выше задача в каталоге.",f"font-size: 17px; color: {INK2};")}
{trow("--fs-body","Onest 400 · 15 / 1.5","Реестр обращений жителей с фильтрами и сменой статуса.",f"font-size: 15px;")}
{trow("--fs-caption","Onest 400 · 13","Образование · Колледж цифровых технологий",f"font-size: 13px; color: {INK3};")}
{trow("score","JetBrains Mono 600 · 26–48","95 / 100",f"font-family: {MONO}; font-size: 40px; font-weight: 600; letter-spacing: -0.03em;")}
{trow("--fs-eyebrow","JetBrains Mono 600 · 11 · caps","Ожидаемый результат",f"font-family: {MONO}; font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: {INK3};")}
</div>'''
spaces=''.join(f'<div style="display: flex; flex-direction: column; gap: 8px; align-items: flex-start;"><div style="width: {v}px; height: 24px; background: {ACC}; border-radius: 2px;"></div><span style="font-family: {MONO}; font-size: 12px; color: {INK2};">--s-{k} · {v}</span></div>' for k,v in [(1,4),(2,8),(3,12),(4,16),(5,20),(6,24),(8,32),(10,40),(20,80)])
radii=''.join(f'<div style="display: flex; flex-direction: column; gap: 8px;"><div style="width: 72px; height: 48px; border: 1.5px solid {INK}; border-radius: {v}px; background: {SURF};"></div><span style="font-family: {MONO}; font-size: 12px; color: {INK2};">{n} · {v}</span></div>' for n,v in [('--r-sm',6),('--r-md',8),('--r-lg',12)])
levels=''.join(f'<div style="display: flex; flex-direction: column; gap: 12px; padding: 16px; background: {SURF}; border: 1px solid {LINE}; border-radius: 10px;"><span style="font-family: {MONO}; font-size: 12px; color: {INK3};">{r}</span>{badge(l)}{meter(s,l,200)}<span style="font-size: 13px; line-height: 1.45; color: {INK2};">{d}</span></div>' for l,r,s,d in [('priority','90–100',95,'Полностью готова. Заливка акцентом, полоса сверху карточки.'),('ready','70–89',80,'Повышенная позиция. Мягкий акцент.'),('working','40–69',55,'Можно откликаться, AI может рекомендовать.'),('draft','0–39',30,'Видна и открыта для отклика. Пунктир + «Требует уточнения».')])
body=f'''<div style="padding: 56px 64px; display: flex; flex-direction: column; gap: 56px;">
<div style="display: flex; flex-direction: column; gap: 10px;">{eyebrow("AI Sana · design tokens v1")}<h1 style="margin: 0; font-size: 56px; font-weight: 700; letter-spacing: -0.035em; line-height: 1;">Токены</h1><p style="margin: 0; font-size: 17px; line-height: 1.5; color: {INK2}; max-width: 760px;">Файлы для разработки: design/tokens.css, design/components.css, design/ui.js в репозитории. Светлый нейтральный фон, графит и один акцент. Красный и зелёный — только для ошибок и успеха.</p></div>
{sect("Цвет",colors)}
{sect("Типографика",type_,"Onest — интерфейс с полной поддержкой кириллицы. JetBrains Mono — баллы, счётчики и служебные метки.")}
<div style="display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); gap: 56px;">{sect("Отступы · шаг 4",f'<div style="display: flex; gap: 20px; align-items: flex-end; flex-wrap: wrap;">{spaces}</div>')}{sect("Радиусы",f'<div style="display: flex; gap: 24px;">{radii}</div>')}</div>
{sect("Уровни готовности",f'<div style="display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px;">{levels}</div>',"Засечки на шкале — пороги 40, 70 и 90. Уровень описывает полноту задачи, а не компанию.")}
</div>'''
W('Tokens.dc.html',page('Токены',1440,1900,body,nohead=True))

# Components
def spec(name,cls,inner,w='auto'):
    return f'<div style="display: flex; flex-direction: column; gap: 14px; padding: 24px; background: {SURF}; border: 1px solid {LINE}; border-radius: 12px;"><div style="display: flex; justify-content: space-between; gap: 12px; align-items: baseline;"><span style="font-size: 16px; font-weight: 600;">{name}</span><code style="font-family: {MONO}; font-size: 12px; color: {INK3};">{cls}</code></div>{inner}</div>'
buttons=spec("Кнопки",".btn .btn--primary|secondary|dark|ghost|danger .btn--sm",f'<div style="display: flex; gap: 12px; flex-wrap: wrap; align-items: center;">{btn("Опубликовать","primary")}{btn("Сохранить черновик","secondary")}{btn("Подтвердить этап","dark")}{btn("Назад","ghost",I["back"])}{btn("Отклонить","danger")}{btn("Опубликовать","disabled")}{btn("Выбрать","primary",I["check"],None,"sm")}</div>')
fields=spec("Поля ввода",".field .input .textarea .select · .is-invalid",f'''<div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px;">
{field("Обычное",inp("","https://","c1"),hint="Подсказка под полем",fid="c1")}
{field("В фокусе",ta("Рабочий прототип бота","","c2",1,focus=True),fid="c2")}
{field("Ошибка",inp("culturelab","","c3",invalid=True),error="Ссылка должна начинаться с https://",fid="c3")}
</div>''')
readiness=spec("Готовность",".badge--{level} .meter .score",f'''<div style="display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 32px; align-items: start;">
<div style="display: flex; flex-direction: column; gap: 14px;"><div style="display: flex; gap: 8px; flex-wrap: wrap;">{badge("priority")}{badge("ready")}{badge("working")}{badge("draft")}</div>
<div style="display: flex; align-items: center; gap: 10px;">{badge("ready")}<span style="font-family: {MONO}; font-size: 26px; font-weight: 600;">80</span></div>{meter(80,None,160)}
<span style="align-self: flex-start; padding: 4px 10px; border-radius: 6px; border: 1px dashed {LINE2}; font-size: 13px; color: {INK2};">Требует уточнения · отклик открыт</span></div>
<div>{score_block(35,300,48)}</div></div>''')
bd=spec("Расшифровка рейтинга",".breakdown__row .missing .state--*",f'<div style="display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 32px;"><div>{breakdown({"context":10,"need":10,"users":5,"data":10,"constraints":0,"expected_result":15,"success_criteria":0,"contact":10})}</div><div style="display: flex; flex-direction: column; gap: 10px;">{missing({"context":10,"need":10,"users":5,"data":10,"constraints":0,"expected_result":15,"success_criteria":0,"contact":10})}<div style="display: flex; gap: 16px;">{state_tag(10,10)}{state_tag(5,10)}{state_tag(0,15)}</div></div></div>')
alerts=spec("Сообщения",".alert--info|error|success|draft",f'<div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px;">{alert("info","AI только спрашивает","Новых фактов AI не добавляет.")}{alert("error","Проверьте 3 поля","Исправьте отмеченные поля.")}{alert("ok","Предложение отправлено","Решение примет бизнес.")}{alert("draft","Описание черновое","Отклик всё равно открыт.")}</div>')
nav=spec("Навигация",".stepper .tabs .chip .status--*",f'''<div style="display: flex; flex-direction: column; gap: 20px;">{stepper(2)}
<div role="tablist" style="display: flex; gap: 28px; border-bottom: 1px solid {LINE};"><button type="button" role="tab" aria-selected="true" style="height: 44px; padding: 0 4px; border: 0; border-bottom: 2px solid {INK}; background: transparent; font: 600 15px {FONT}; color: {INK};">Все <span style="font-family: {MONO}; font-size: 12px; color: {INK3};">4</span></button><button type="button" role="tab" aria-selected="false" style="height: 44px; padding: 0 4px; border: 0; border-bottom: 2px solid transparent; background: transparent; font: 500 15px {FONT}; color: {INK2};">На рассмотрении <span style="font-family: {MONO}; font-size: 12px; color: {INK3};">2</span></button></div>
<div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;"><span style="display: inline-flex; align-items: center; height: 32px; padding: 0 12px; border-radius: 16px; background: {INK}; color: #FFFFFF; font-size: 14px;">Культура ×</span>
<span style="display: inline-flex; align-items: center; height: 24px; padding: 0 10px; border-radius: 6px; background: {NEU}; font-size: 13px; font-weight: 600;">На рассмотрении</span>
<span style="display: inline-flex; align-items: center; gap: 4px; height: 24px; padding: 0 10px; border-radius: 6px; background: {OKS}; color: {OK}; font-size: 13px; font-weight: 600;">{I["check"]}Выбрана</span>
<span style="display: inline-flex; align-items: center; height: 24px; padding: 0 10px; border-radius: 6px; border: 1px solid {LINE2}; color: {INK3}; font-size: 13px; font-weight: 600;">Отклонена</span>
{checkbox("Чекбокс",2,True)}</div></div>''')
empty=spec("Пустое состояние",".empty",f'<div style="display: flex; flex-direction: column; align-items: center; text-align: center; gap: 12px; padding: 36px; border: 1px dashed {LINE2}; border-radius: 12px;"><span style="width: 48px; height: 48px; border-radius: 24px; background: {NEU}; color: {INK2}; display: flex; align-items: center; justify-content: center;">{I["inbox"]}</span><span style="font-size: 18px; font-weight: 600;">Предложений пока нет</span><span style="font-size: 14px; color: {INK2}; max-width: 320px;">Одна фраза о причине и одно действие.</span>{btn("Дополнить карточку","primary","",None,"sm")}</div>')
body=f'''<div style="padding: 56px 64px; display: flex; flex-direction: column; gap: 32px;">
<div style="display: flex; flex-direction: column; gap: 10px;">{eyebrow("AI Sana · components v1")}<h1 style="margin: 0; font-size: 56px; font-weight: 700; letter-spacing: -0.035em; line-height: 1;">Компоненты</h1><p style="margin: 0; font-size: 17px; line-height: 1.5; color: {INK2}; max-width: 820px;">Каждый блок — класс из design/components.css; строки каталога, шкалу и расшифровку рисуют функции из design/ui.js. Новый экран собирается из этих деталей без новых цветов.</p></div>
{buttons}{fields}
<div style="display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 24px;">{readiness}{nav}</div>
{bd}
<div style="display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); gap: 24px;">{alerts}{empty}</div>
</div>'''
W('Components.dc.html',page('Компоненты',1440,1900,body,nohead=True))
