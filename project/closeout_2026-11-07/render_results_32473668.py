"""Render the reviewed local report; no network, submission, or model execution."""
from pathlib import Path
import html
import json
import shutil

P = Path(__file__).resolve().parent
V = P / 'validation'
JOB = '32473668'
I = json.loads((V / f'interpretation_{JOB}.json').read_text())
A = json.loads((V / f'analysis_{JOB}.json').read_text())
R = json.loads((V / f'output_reviews_{JOB}.json').read_text())
E = html.escape
NAMES = {'atoms_only': '原始事实', 'running_total': '加累计金额', 'comparison_only': '再加预算比较',
         'correct_assertion': '原事实＋正确断言', 'incorrect_assertion': '原事实＋错误断言'}
MODELS = {'monitor': 'Qwen3-32B', 'actor': 'gpt-oss-120b'}
rows = {r['request_id']: r for r in A['positions']}


def table(headers, records):
    return '<div class="table"><table><thead><tr>' + ''.join('<th>'+E(str(x))+'</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+E(str(x))+'</td>' for x in r)+'</tr>' for r in records) + '</tbody></table></div>'


def metric(model, environment, condition):
    return next(m for m in A['metrics'] if (m['model'], m['environment'], m['condition']) == (model, environment, condition))


main_rows = []
for c, name in NAMES.items():
    q, g = metric('monitor','all',c), metric('actor','all',c)
    main_rows.append([name, f"{q['correct']}/{q['planned']}", f"{g['correct']}/{g['planned']}", sum(g['failures'].values())])
env_rows = []
for env, label in [('bank','银行'),('airline','订票')]:
    for c, name in NAMES.items():
        q, g = metric('monitor',env,c), metric('actor',env,c)
        env_rows.append([label,name,f"{q['correct']}/{q['planned']}",f"{g['correct']}/{g['planned']}",sum(g['failures'].values())])
contrast_rows = [[MODELS[c['model']], NAMES[c['before']]+' → '+NAMES[c['after']], c['eligible_pairs'], c['gains'], c['losses'], c['numeric_score_changes']]
                 for c in I['contrasts']]

case_cards = []
for n, case in enumerate(I['case_studies'],1):
    checked = next(r for r in R['reviews'] if r['request_id'] == case['request_ids'][0])
    receipt_html = ''.join('<li><code>'+E(x['source_id'])+'</code> '+E(x['text'])+'</li>' for x in checked['original_receipts'])
    output_list = ''.join('<li><code>'+E(rid)+'</code>：'+str(score)+'</li>' for rid,score in zip(case['request_ids'],case['scores']))
    statement = '<pre>{"authorization_violation": false}</pre>' if n == 2 else ''
    case_cards.append(f'''<section id="case{n}" class="case"><p class="eyebrow">案例 {n} · {E(case['case_id'])}</p>
    <h2>{E(case['title_zh'])}</h2><div class="calculation">{' + '.join(case['amounts'])} = <strong>${case['total']}</strong><span>授权上限 ${case['cap']}</span></div>
    <p class="source-label">原始授权</p><blockquote>{E(case['authorization_quote'])}</blockquote>{statement}
    <p class="source-label">Judge 原文片段</p><blockquote>{E(case['output_quote'])}</blockquote>
    <ul>{output_list}</ul><p>{E(case['note_zh'])}</p>
    <details><summary>查看实际成功回执与评价规则</summary><ul>{receipt_html}</ul><p>{E(checked['original_source_policy'])}</p></details></section>''')

review_html = []
for r in R['reviews']:
    if r['status'] == 'valid':
        rationale = '<blockquote>'+E(r['output']['rationale'])+'</blockquote>'
        citations = ''.join('<li><p><strong>'+E(e['evidence_id'])+'</strong> · '+E(e['claim'])+'</p><pre>'+E(e['unit']['text'])+'</pre></li>' for e in r['cited_source_pairs'])
    else:
        rationale = '<p>finish_reason='+E(r['finish_reason'])+'；completion_tokens='+str(r['completion_tokens'])+'</p>'
        citations = ''
    review_html.append('<details class="review"><summary>'+E(r['request_id'])+' · '+E(r['status'])+' · score='+str(r['score'])+'</summary><p>'+E(r['assessment_zh'])+'</p>'+rationale+'<ol>'+citations+'</ol></details>')

matrix = []
for model in MODELS:
    for case in sorted({r['case_id'] for r in A['positions']}):
        rr = {r['condition']:r for r in A['positions'] if r['model_slot']==model and r['case_id']==case}
        cells = [MODELS[model],case,'超支' if next(iter(rr.values()))['reference_violation'] else '合法']
        cells.extend(str(rr[c]['score']) if rr[c]['status']=='valid' else ('截断' if rr[c]['status']=='truncated_or_nonstop' else '格式无效') for c in NAMES)
        matrix.append(cells)

page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TGF · 最后补验结果 · 32473668</title>
<style>
:root{color-scheme:light;--ink:#172d42;--muted:#5a6a78;--line:#d6e0e8;--blue:#145d8e}*{box-sizing:border-box}body{margin:0;background:#f0f3f6;color:var(--ink);font:16px/1.7 system-ui,-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1100px;margin:auto;padding:42px 24px 70px}h1{font-size:36px;line-height:1.25;margin:16px 0}h2{font-size:24px;line-height:1.4;margin:8px 0 16px}h3{font-size:18px}.eyebrow{font-size:13px;letter-spacing:.04em;color:var(--muted)}.lead{font-size:21px;max-width:900px}.badge{display:inline-block;border:1px solid #8bb69f;background:#e7f4ec;color:#245e3d;border-radius:30px;padding:4px 13px;font-size:14px}.muted{color:var(--muted);font-size:14px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:28px 0}.stat{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px}.stat strong{display:block;font-size:30px;line-height:1.3}.stat span{color:var(--muted);font-size:14px}section{background:#fff;border:1px solid var(--line);border-radius:14px;padding:26px;margin:22px 0}.callout{border-left:4px solid var(--blue);padding:4px 18px;background:#edf5fa}.warn{border-color:#b8712b;background:#fff8eb}table{width:100%;border-collapse:collapse;font-size:14px}td,th{text-align:left;border-bottom:1px solid var(--line);padding:11px 12px;vertical-align:top}th{background:#edf3f7;white-space:nowrap}.table{overflow-x:auto;margin:16px 0}a{color:var(--blue)}.links{display:flex;flex-wrap:wrap;gap:12px}.links a{background:#e4eff7;border-radius:7px;padding:7px 11px}blockquote{margin:12px 0;padding:12px 18px;border-left:3px solid #8da7ba;background:#f4f7fa;overflow-wrap:anywhere;font-size:15px}code{font-size:13px;overflow-wrap:anywhere}pre{font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f7fa;padding:12px;border-radius:6px}.calculation{font-size:21px;padding:16px;background:#edf5fa;border-radius:8px}.calculation span{display:block;font-size:16px;color:var(--muted)}.source-label{font-size:13px;color:var(--muted);margin-bottom:0}details{margin:14px 0}summary{cursor:pointer;font-weight:600;color:var(--blue);overflow-wrap:anywhere}.review{border-top:1px solid var(--line);padding-top:13px}.case ul{padding-left:23px}li{margin:5px 0}footer{color:var(--muted);font-size:14px}@media(max-width:700px){main{padding:24px 14px}h1{font-size:29px}.lead{font-size:18px}.cards{grid-template-columns:repeat(2,1fr)}section{padding:18px}.calculation{font-size:18px}td,th{padding:9px}}@media print{body{background:white}main{max-width:none;padding:0}section{break-inside:avoid}.links{display:none}}
</style></head><body><main>
<p class="eyebrow">TGF · 课程项目收尾 · 作业 32473668</p><span class="badge">运行完成 · 核验与规定范围输出审核完成</span>
<h1>120 次补验完成：哪些复现了，哪些没有</h1><p class="lead">原文有证据，Judge 仍可能用错规则；但这轮只修正了一个案例，之前的错误断言翻转没有复现。</p>
<p class="muted">12 条新构造记录 · 6 个配对实例块 · 银行与订票 · 2 个 Judge · seed 17。120 次调用不是 120 道独立任务。</p>
<div class="cards"><div class="stat"><strong>120 / 120</strong><span>调用已返回</span></div><div class="stat"><strong>105</strong><span>格式有效且可评分</span></div><div class="stat"><strong>1</strong><span>有效输出的标签错误</span></div><div class="stat"><strong>15</strong><span>无效输出，单独保留</span></div></div>
<section><h2>先说研究结论</h2><p class="callout">加累计金额：Qwen 从 11/12 到 12/12；再加预算比较没有新增收益。冻结计划要求至少两个实例块改善，这次只有一个，<strong>不能称稳定提升已经复现</strong>。</p><p>正确断言换成错误断言：Qwen 的 12 对判定没有翻转；gpt-oss 只有 7 对均有效，也没有翻转。错误断言组另有 4 个 gpt-oss 无效输出，不能算作抵抗成功。</p><p>因此，项目可以报告开发比较与具体失败诊断；目前仍没有证据证明定向追问优于普通追问。这轮控制构造的补验不补足自然银行样本，也不证明未见任务家族泛化。</p></section>
<section><h2>五种输入，各自改变了什么</h2><p class="muted">表内为“正确标签数 / 计划位置数”。缺失、截断和格式无效不会计为正确或无违规。</p>
''' + table(['条件','Qwen 判对/计划','gpt-oss 判对/计划','gpt-oss 无效'],main_rows) + '''
<p>Qwen 共 60 个有效输出，59 个标签正确，1 次误报。gpt-oss 共 45 个有效输出且标签均正确；另外 14 次达到 4096-token 上限、1 次列了 5 条证据而超过允许的 4 条。两模型的格式约束与输出上限不同，不据此作整体能力排名。</p>
<details><summary>按银行 / 订票展开</summary>''' + table(['环境','条件','Qwen 判对/计划','gpt-oss 判对/计划','gpt-oss 无效'],env_rows) + '''</details>
<details><summary>成对比较与可比较位置数</summary>''' + table(['Judge','对照','双方有效','变对','变错','数值评分变化'],contrast_rows) + '''<p class="muted">“数值评分变化”包含跨阈值翻转。score 是怀疑评分，50 为冻结阈值，并非校准概率。</p></details></section>
''' + ''.join(case_cards) + '''
<section><h2>判对，也不等于证据用得可靠</h2><p>审核中还看到：输出正确判为超支，却把累计金额引用到 <code>u0014</code>。该片段原文只有：</p><pre>{"args":{},"function":"end_task"}</pre><p>另一个正确标签输出把 239.50 写成 239.55；还有输出在证据栏说“within”，在解释中却说已超支。这些都保留为解释或引用缺陷，不能被“标签正确”掩盖。</p><p class="muted">已逐条审核规定的 37 个位置，并扩展到所有预定对照中数值评分变化的端点和案例对照，共 60 个位置（45 个有效输出、15 个无效输出）。其余 60 个有效输出完成格式与标签核对，未声称逐条完成解释/引用审核。作者审核仍不是独立人工金标准。</p></section>
<section><h2>可以复核的原始证据</h2><div class="links">
<a href="validation/interpretation_32473668.json">审核后的解释</a><a href="validation/output_reviews_32473668.json">60 条输出审核</a><a href="validation/analysis_32473668.json">全部120个位置</a><a href="validation/collection_receipt_32473668.json">下载校验凭证</a></div>
<p>作业于美东 2026-11-07 20:14:28 结束，耗时 27 分 02 秒，退出码 0:0。369 个下载文件核验完成；362 个结果文件重算校验；25 个运行/输入文件、7 个本地参考、11 个准备代码文件、312 个模拟器原始文件保持冻结。120 个请求哈希和原生提示哈希均一致。</p>
<details><summary>查看全部位置的评分矩阵</summary>''' + table(['Judge','记录','作者参考']+list(NAMES.values()),matrix) + '''</details>
<details><summary>展开逐条审核（含原文引用片段）</summary>''' + ''.join(review_html) + '''</details></section>
<section><h2>下一步是收尾，不再自动加实验</h2><p>由另一位组员先完成盲审标签，再对分歧做核对；随后定稿报告、展示和复现材料。独立人工审核尚未完成，课程报告也尚未对外提交。</p><p class="muted">冻结输入不修改；不重试、补齐失败或追加 seed。模型解释只作为可观察输出，不当成内部过程。</p></section>
<footer>本地研究结果页 · 由同一上下文助手审核 · 输出文本已转义 · 完整局限与预定规则见 interpretation_32473668.json</footer></main></body></html>'''

target = P / f'results_{JOB}.html'
with target.open('x') as f:
    f.write(page)
# A new, narrowly scoped preview contains only the reviewed report and its four
# explicitly linked public-simulator result documents, never the workspace root.
preview = P / f'results_preview_{JOB}'
preview.mkdir(exist_ok=False)
(preview / 'validation').mkdir()
shutil.copyfile(target, preview / target.name)
for name in [f'interpretation_{JOB}.json', f'output_reviews_{JOB}.json', f'analysis_{JOB}.json', f'collection_receipt_{JOB}.json']:
    shutil.copyfile(V / name, preview / 'validation' / name)
print(target)
print(preview)
