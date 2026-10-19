"""Prepare an explicitly authorized email and artifact acceptance, without sending."""
from pathlib import Path
from datetime import datetime, timezone
import base64, csv, hashlib, json
from collections import Counter
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
subject='【TGF】64条数据审核后的下一步实验计划 v2（先离线验收）'
body='''<div style="font-family:Arial,sans-serif;line-height:1.65;color:#182c3c;max-width:850px">
<p>Ruoyang、Luanfeng，你们好：</p>
<p>按 Ruoyang 的要求，Codex 已完成剩余48条活动轨迹的审核，并结合此前16条拒绝和 Luanfeng 的完整结果，整理了附件中的<strong>下一步实验计划 v2</strong>。建议保留原生120b actor路线及现有数据，先统一标签与接口，再决定是否运行小规模匹配追问诊断。本次没有启动新实验。</p>
<p><strong>1. 数据现在能支持什么</strong></p>
<p>全部64条、3817个结构化事件已完成非盲、非独立的AI审核，<strong>不是人工金标</strong>。当前合同下银行为11P/17N/4unknown，航空为27P/4N/1unknown。去重只有52种对话；银行16个拒绝N只含4种，航空4个N中3个是中断前缀。按严格结束、去重和标签明确筛选，每个环境仅有<strong>1个实际敏感执行N候选</strong>，还需重点复核。原每环境30P/30N目标未达到，不能据此声称TGF有效、无效或需要微调。</p>
<p>此外，14个航空P只依赖“收到17人更新仍订16餐位”，而银行少付目前归为未完成而非越权。这个边界必须先统一。旧收款人/AA占比标签与新授权合同也不同，不能直接重算旧分数后宣称新方法收益。</p>
<p><strong>2. 建议按以下顺序推进</strong></p>
<ol>
<li><strong>0 GPU，定向复核约1-3小时：</strong>先区分“超出明确授权”和“任务完成/正确性”，复核两个hardN及更正、分摊、餐位等边界，形成带来源的版本化合同。争议未解先停，不为了补负例放宽标签。</li>
<li><strong>0 GPU，共同接口约半天：</strong>固定公开输入和事实账本；三个ledger条件共用选点和final judge，均去掉initial_review；Fixed/TGF各一问、同actor上下文和回答上限、独立禁工具分支；null/截断记unknown，真实tokenizer容量与版本必须通过。</li>
<li><strong>验收后才考虑8条开发诊断：</strong>B1 passive、Ledger-only、Fixed-matched、TGF-matched，加固定输入的judge稳定性检查。拟最多72次生成、单H200合计60GPU分钟（含载模），0重试/0新增轨迹/0训练。它仅检验给定共同选点后的问题内容增量；每域1个N不足以支持可靠FPR/G²或泛化结论。配置和预算仍需独立冻结确认，当前未提交。</li>
</ol>
<p><strong>3. 请 Luanfeng 帮忙核对的具体事项</strong></p>
<ul>
<li>银行<code>monitor_aware_3</code>与航空<code>direct_conceal_3</code>是否认可为当前观察范围下的hardN；前者是部分合法付款，不是全部任务完成。</li>
<li>“少付/少订”在主研究里究竟算任务未完成还是已执行参数违规，尤其14条餐位唯一P；不按方法效果选择标签。</li>
<li>生成64条时的实际循环代码/commit，特别是航空<code>direct_conceal_3</code>真实end_task在第151步而元数据max_iters=150的边界；以及现有缓存/日志中的模型和tokenizer精确revision。缺失的请直接注明，<strong>不用为了补元数据重跑</strong>。</li>
</ul>
<p>完整64条原轨迹和v4/full、tl2000结果已经收到，不用重复发送。组员复核尚未进行，以上是建议协作事项，并非已完成的人类抽检。</p>
<p><strong>4. 报告和交接</strong></p>
<p>先把审核、旧实验的解释边界和匹配诊断方案写入progress report，建议10月20日前形成稿，保障10月21日提交，不等待“好结果”。后续正式主比较仍要另行解决合法敏感负例覆盖；若不新增数据，结论就限定为开发集机制与评估有效性分析。新session从项目根目录的<code>NEXT_SESSION_START_HERE.md</code>接续。</p>
<p>附件：①四页实验计划PDF；②同版Markdown（便于修改和AI接续）；③64条逐例标签CSV；④完整审核说明。CSV/审核材料属于参考层，<strong>不要直接输入monitor</strong>。</p>
<p>请优先看上述标签边界和两条hardN，再据此定稿。谢谢！</p>
<p>Codex<br><span style="color:#52606a">按 Ruoyang 要求整理并发送；AI审核非人工金标。</span></p>
</div>'''

files=[
('output/pdf/TGF_experiment_plan_v2_2026-10-18.pdf','TGF_experiment_plan_v2_2026-10-18.pdf','application/pdf'),
('docs/tgf_experiment_plan_team_v2_2026-10-18.md','TGF_experiment_plan_v2_2026-10-18.md','text/markdown'),
('analysis/tgf_full48_authorization_20261018/case_labels.csv','TGF_64_case_labels_AI_review_2026-10-18.csv','text/csv'),
('docs/tgf_full64_authorization_audit_2026-10-18.md','TGF_full64_audit_AI_review_2026-10-18.md','text/markdown'),
]
parts=[{'mime_type':'text/html','charset':'utf-8','body':{'content':body}}]
manifest=[]
for relative,name,mime in files:
    data=(ROOT/relative).read_bytes()
    parts.append({'mime_type':mime,'content_disposition':'attachment','filename':name,'body':{'base64_url_content':base64.urlsafe_b64encode(data).decode().rstrip('=')}})
    manifest.append({'path':relative,'filename':name,'mime_type':mime,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})

r=PdfReader(ROOT/files[0][0])
assert len(r.pages)==4
text='\n'.join(p.extract_text() for p in r.pages)
for required in ['3817','72','60','非盲','未执行','0重试']:
    assert required in text, required
rows=list(csv.DictReader((ROOT/files[2][0]).open()))
assert len(rows)==64 and Counter(x['label'] for x in rows)=={'P':38,'N':21,'unknown':5}
assert 8*1024+16*4096+48*2048==172032
assert 8+16+48==72

args={'to':'ruoyang.zhang@yale.edu','cc':'luanfeng.wei@yale.edu','subject':subject,'payload':{'mime_type':'multipart/mixed','parts':parts},'response_fields':['id','thread_id','label_ids','internal_date','size_estimate']}
prepared={'event_key':'tgf_full64_20261018:team_experiment_plan_v2','created_at':datetime.now(timezone.utc).isoformat(),'user_authorization':'好的 看完这些数据出一版新的实验计划抄送给我和luanfeng','args':args,'attachments':manifest}
acceptance={'status':'passed','checked_at':prepared['created_at'],'pages':4,'visual_inspection':'all four final rendered pages inspected; no clipping, overlap or missing Chinese glyphs','rows':64,'labels':{'P':38,'N':21,'unknown':5},'human_gold':False,'independent_review':False,'experiments_started':False,'attachments':manifest}
for path,value in [('results/tgf_team_plan_v2_email_prepared_20261018.json',prepared),('results/tgf_team_plan_v2_artifact_acceptance_20261018.json',acceptance)]:
    with (ROOT/path).open('x') as out: json.dump(value,out,ensure_ascii=False,indent=2)
(ROOT/'output/handoff/TGF_team_plan_email_2026-10-18.html').write_text(body)
print(json.dumps({'subject':subject,'to':args['to'],'cc':args['cc'],'attachments':manifest},ensure_ascii=False))
