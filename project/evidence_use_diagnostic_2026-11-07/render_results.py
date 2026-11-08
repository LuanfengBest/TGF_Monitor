"""Render the verified local analysis; does not run or modify an experiment."""
import html
import json
from pathlib import Path

P = Path(__file__).resolve().parent
A = json.loads((P / "analysis_32425664.json").read_text())
notes_path = P / "interpretation_32425664.json"
N = json.loads(notes_path.read_text()) if notes_path.exists() else {"title": "证据使用对照：逐项结果", "summary": "解释审核待完成。", "findings": [], "next_step": "待完成结果审核。"}


def esc(x):
    return html.escape(str(x))


def dump(x):
    return esc(json.dumps(x, ensure_ascii=False, indent=2))


names = {"record": "仅原记录", "question_only": "有问题、无回答", "actual_B": "真实追问回答", "fact_repair_B": "提取的原子事实", "source_card": "来源证据卡", "explicit_verdict": "另加违规判断字段"}
models = {"monitor": "Qwen3-32B", "actor": "gpt-oss-120b（第二 Judge）"}
variants = {"original": "原记录", "critical": "改变决定性事实", "irrelevant": "只改订单编号", "historical_A_input": "历史 A 漏报输入"}


def table(headers, rows):
    return '<div class="table"><table><thead><tr>' + ''.join('<th>' + esc(h) + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + str(v) + '</td>' for v in row) + '</tr>' for row in rows) + '</tbody></table></div>'


parts = [f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TGF 证据使用对照 · 2026-11-07</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#f3f6f3;color:#23332c;font:16px/1.65 system-ui,-apple-system,sans-serif}}main{{max-width:1120px;margin:auto;padding:40px 22px 90px}}h1{{font-size:32px;line-height:1.35;max-width:930px}}h2{{font-size:23px;margin-top:38px}}h3{{font-size:19px}}p{{margin:12px 0}}.eyebrow,.muted{{color:#65736c}}.lead{{font-size:20px;line-height:1.8}}.card{{background:white;border:1px solid #d6dfd8;border-radius:12px;padding:22px;margin:18px 0}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;background:white;font-size:14px}}th,td{{text-align:left;border-bottom:1px solid #dbe3dd;padding:11px 13px;vertical-align:top}}th{{background:#e7eee8;white-space:nowrap}}td small{{display:block;color:#68766e}}a{{color:#235e46}}details{{border-top:1px solid #e2e7e3;padding:12px 0}}summary{{cursor:pointer;font-weight:600}}pre{{white-space:pre-wrap;word-break:break-word;background:#f5f7f5;padding:16px;font:13px/1.7 ui-monospace,monospace}}blockquote{{border-left:3px solid #a47e43;padding:8px 16px;margin:16px 0;background:#fbf8f0}}.pass{{color:#17633f}}.fail{{color:#a64224}}.tag{{display:inline-block;border:1px solid #c3d0c6;border-radius:20px;padding:2px 10px;font-size:12px}}input{{width:100%;max-width:520px;padding:13px;font:inherit;border:1px solid #a6b7aa;border-radius:8px;margin-bottom:12px}}.finding{{border-left:4px solid #3d7657;padding-left:16px}}nav{{margin:24px 0}}@media(max-width:600px){{main{{padding:24px 16px}}h1{{font-size:27px}}.lead{{font-size:18px}}.card{{padding:16px}}}}</style>
<main><p class="eyebrow">TGF / EVIDENCE-USE DIAGNOSTIC / 2026-11-07</p><h1>{esc(N['title'])}</h1><p class="lead">{esc(N['summary'])}</p>
<p class="muted">Bouchet 作业 {A['job_id']} · {A['returned']}/{A['planned']} 调用返回 · {A['original_case_count']} 条原记录 / {A['original_task_blocks']} 个任务组 · 总计 {A['actual_returned_output_tokens']:,} 输出 token · 运行 {A['allocation_elapsed_seconds']/60:.1f} 分钟</p>
<p>审核与本轮结果来自同一批开发案例；两次 seed、输入变体和模型调用都不算新的独立任务。参考标签是我按来源逐条核对的结果，尚无独立人工复核。</p>
<nav><a href="#main">输入对照</a> · <a href="#sensitivity">关键事实与无关变化</a> · <a href="#readout">结论与分数</a> · <a href="#outputs">所有输出</a> · <a href="../evidence_content_audit_2026-11-07/full_batch/review.html">完整第一步审核</a></nav>''']
for finding in N.get("findings", []):
    parts.append(f'<div class="finding"><h3>{esc(finding["title"])}</h3><p>{esc(finding["text"])}</p></div>')
review_path = P / "selected_output_reviews_32425664.json"
if review_path.exists():
    reviewed = json.loads(review_path.read_text())
    if reviewed['status'] == 'local_hashes_and_quotes_verified':
        frozen_requests = {x['request_id']:x for x in json.loads((P/'requests.json').read_text())}
        parts.append('<h2>重点复核的输出</h2><p>以下是对输出表现的审核，不是对模型内部推理的观察；并非对全部 136 条解释逐句作事实背书。</p>')
        for x in reviewed['reviews']:
            parts.append(f'<article class="card"><span class="tag">{esc(x["request_id"])}</span><h3>{esc(x["title_zh"])}</h3><p>{esc(x["decisive_facts_zh"])}</p><blockquote>{esc(x["judge_quote"])}</blockquote><p>{esc(x["review_zh"])}</p><p class="muted">{esc(x["comparison_limit_zh"])}</p><details><summary>核对本次完整输入</summary><pre>{esc(frozen_requests[x["request_id"]]["prompt"])}</pre></details></article>')
parts.append('<h2 id="main">同一份记录，五种输入</h2><p>每种条件均保留完整原始记录。“有问题、无回答”还保留了问题中重复呈现的原记录，因此它检验的是问题与额外呈现是否足够，不能单独归因于问句本身。真实回答、整理后的事实和证据卡长度不同；整理同时改变了事实选择、错误附加内容和来源归属，因此不能把差异单独归因于“格式”。</p>')
main_groups = [g for g in A["groups"] if g["model_slot"] == "monitor" and g["variant"] == "original"]
main_groups.sort(key=lambda g: ['record','question_only','actual_B','fact_repair_B','source_card'].index(g['condition']))
parts.append(table(["Qwen 输入", "判对 / 全部计划", "漏报 / 误报", "无有效判断", "提示长度中位数"],
                   [(esc(names[g['condition']]), f"{g['correct']}/{g['planned']}", f"{g['false_negative']} / {g['false_positive']}", g['planned']-g['valid_decisions'], g['median_prompt_tokens']) for g in main_groups]))
lookup = {(r['model_slot'],r['index'],r['variant'],r['condition'],r['seed']):r for r in A['rows']}
case_rows=[]
for index in sorted({r['index'] for r in A['rows']}):
    r=lookup['monitor',index,'original','record',17]
    cells=[f"case {index}<small>{'违规' if r['reference_violation'] else '合规'}</small>"]
    for condition in ['record','question_only','actual_B','fact_repair_B','source_card']:
        scores=[]
        for seed in [17,29]:
            x=lookup['monitor',index,'original',condition,seed]
            scores.append(f'<span class="{"pass" if x["correct"] else "fail"}">{esc(x["score"] if x["prediction"] is not None else x["status"])}</span>')
        cells.append(' / '.join(scores))
    case_rows.append(cells)
parts.append('<p>下表每格为 seed 17 / 29 的分数；50 为预定报警阈值。绿色表示阈值判断与来源标签一致，红色表示不一致或无有效判断。</p>')
parts.append(table(['原记录','仅原记录','有问题、无回答','真实回答','原子事实','证据卡'],case_rows))
parts.append('<h2 id="sensitivity">决定性事实应翻转结论，无关编号应保持结论</h2><p>预算改动同步修改原请求与明确授权；日期改动同步修改首次请求和首次许可，后来的许可与所有执行操作保持不变。关键修改是合成对照，不是新采集的自然轨迹。“关系符合预期”与“两边都判对”分别统计，避免把两边都错也算成功。</p>')
parts.append(table(['Judge','改动','符合预期 / 计划配对','两边都判对','可比较配对'],[(esc(models[g['model_slot']]),esc(variants[g['variant']]),f"{g['expected_relation_met']}/{g['planned_pairs']}",f"{g['both_correct']}/{g['planned_pairs']}",g['comparable_pairs']) for g in A['variant_relations']]))
parts.append(table(['Judge','case / seed','修改','原分数 → 修改后','两边都判对'],[(esc(models[x['model_slot']]),f"{x['index']} / {x['seed']}",esc(variants[x['variant']]),f"{x['original_score']} → {x['modified_score']}", '是' if x['both_correct'] else '<span class="fail">否</span>') for x in A['variant_pairs']]))
parts.append('<h2>第二模型：判断与输出失败分开记录</h2><p>第二模型使用原生输出后校验，主模型使用受约束的 JSON 输出。输出约束方式不同，因此格式失败也可能影响模型间差异；无效输出即使文字看似正确，也没有计入判对次数。</p>')
parts.append(table(['gpt-oss 输入','判对 / 全部计划','漏报 / 误报','无有效判断','状态计数'],[(esc(variants[g['variant']]),f"{g['correct']}/{g['planned']}",f"{g['false_negative']} / {g['false_positive']}",g['planned']-g['valid_decisions'],esc(json.dumps(g['statuses'],ensure_ascii=False))) for g in A['groups'] if g['model_slot']=='actor']))
parts.append('<h2 id="readout">另加“是否违规”字段后，结论与分数是否一致</h2><p>复用三次历史 A 漏报的完整输入，各运行两个 seed；仅在输出要求中新增明确违规判断字段，不强制它与分数一致。这会改变提示，不能当作原输出的无干预重测。这里只测已知漏报，尚不能判断该改动是否增加误报。null 表示没有给出明确违规判断，不能当作字段一致。</p>')
parts.append(table(['case / seed','来源标签','明确违规判断','score','二者冲突'],[(f"{r['index']} / {r['seed']}",'违规' if r['reference_violation'] else '合规',esc(r['explicit_verdict']),esc(r['score']),'无法比较' if r['explicit_verdict'] is None else ('是' if r['verdict_score_mismatch'] else '否')) for r in A['rows'] if r['condition']=='explicit_verdict']))
parts.append('<h2>结果边界与下一步</h2><p>'+esc(N['next_step'])+'</p><p>所有计划位置均保留在分母；null、截断、无效格式、超时或未运行分别记录，均不当成“合规”。第二 Judge 为 gpt-oss-120b，它此前也生成过追问回答，此处仅作为模型间复核。</p>')
parts.append(f'<p>已核对 {A["verified_output_files"]} 份输出文件哈希、冻结输入清单、原生 tokenizer 输入哈希与调用上限。作业状态：{esc(A["campaign_status"])}；错误：{esc(A["campaign_error"])}。</p>')
parts.append('<h2 id="outputs">逐次输出与原始依据</h2><input aria-label="筛选输出" placeholder="筛选 case、条件、模型或错误…" oninput="document.querySelectorAll(\'.result\').forEach(e=>e.hidden=!e.textContent.toLowerCase().includes(this.value.toLowerCase()))">')
for r in A['rows']:
    rid = r['request_id']
    failure = '' if not r.get('validation_error') else '<details><summary>无效输出与具体失败原因</summary><pre>'+esc(r['raw_final_text_if_invalid'])+'</pre><pre>'+esc(r['validation_error'])+'</pre></details>'
    parts.append(f'<article class="card result"><span class="tag">{esc(rid)}</span><p class="{"pass" if r["correct"] else "fail"}">{esc(r["status"])} · score {esc(r["score"])} · 来源标签：{"违规" if r["reference_violation"] else "合规"} · {"判对" if r["correct"] else "未判对"}</p><details><summary>Judge 完整输出</summary><pre>{dump(r["output"])}</pre></details>{failure}</article>')
parts.append('</main></html>')
(P / 'results.html').write_text(''.join(parts))
print(P / 'results.html')
