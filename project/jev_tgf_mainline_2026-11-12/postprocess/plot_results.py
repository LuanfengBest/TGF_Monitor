"""Render the unchanged frozen primary outputs, without recomputing endpoints."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

B = Path(__file__).resolve().parents[1]
r = json.loads((B/'RESULTS.json').read_text())
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                     'axes.spines.top': False, 'axes.spines.right': False})
fig, axes = plt.subplots(2, 2, figsize=(13, 8.2), gridspec_kw={'width_ratios': [1.3, 1]})
arms = ['P', 'C', 'F', 'T']
colors = {'qwen': '#8797AC', 'jev': '#3859C7'}
for i, env in enumerate(('airline', 'bank')):
    d = r['environments'][env]
    ax = axes[i, 0]
    for j, model in enumerate(('qwen', 'jev')):
        values = [d['table'][model+'.'+a]['G'] for a in arms]
        bars = ax.bar(np.arange(4)+(j-.5)*.34, [v or 0 for v in values],
                      .32, color=colors[model], label='Qwen' if model=='qwen' else 'Jev')
        for bar, value in zip(bars, values):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+.018,
                    'N/A' if value is None else f'{value:.3f}', ha='center', fontsize=9)
    ax.set_xticks(np.arange(4), arms)
    ax.set_ylim(0, 1.14)
    ax.set_ylabel('G = sensitivity × authorized pass rate')
    coverage = min(d['positive_blocks'], d['negative_blocks']) >= 8
    title = 'Airline: primary environment' if env=='airline' else 'Bank: replication environment'
    ax.set_title(title, loc='left', fontsize=13, fontweight='bold')
    ax.text(0, -.20, f"{d['eligible']} trajectories; {d['instance_blocks']} instance blocks; "
            f"{d['positive_blocks']} positive blocks" + ('' if coverage else ' — coverage insufficient'),
            transform=ax.transAxes, fontsize=9)
    ax.grid(axis='y', alpha=.15)
    ax.set_axisbelow(True)
    if i==0:
        ax.legend(loc='upper center', ncol=2, frameon=False)
    ax = axes[i, 1]
    effects = [d['comparisons']['jev.T-F']['G'], d['comparisons']['qwen.T-F']['G'], d['interaction']['G']]
    for k, (effect, color) in enumerate(zip(effects, [colors['jev'], colors['qwen'], '#202A3D'])):
        estimate, ci = effect['estimate'], effect['ci95']
        if estimate is None or ci is None:
            ax.text(0, k, 'undefined', va='center')
            continue
        ax.plot(ci, [k, k], color=color, lw=2)
        ax.plot(estimate, k, 'o', color=color, ms=7)
        clean = lambda x: 0.0 if abs(x)<1e-12 else x
        ax.annotate(f"{clean(estimate):+.4f} [{clean(ci[0]):+.4f}, {clean(ci[1]):+.4f}]", (estimate, k),
                    xytext=(0, 13), textcoords='offset points', ha='center', fontsize=9)
    ax.axvline(0, color='#94A3B8', ls=':', lw=1)
    ax.set_yticks([0, 1, 2], ['Jev T − F', 'Qwen T − F', 'Judge interaction'])
    ax.set_ylim(2.6, -.65)
    limits = [x for e in effects for x in (e['ci95'] or [])]
    span = max([abs(x) for x in limits]+[.1])*1.6
    ax.set_xlim(-span, span)
    ax.set_xlabel('Paired difference in G (95% block-bootstrap interval)')
    ax.set_title('Prespecified contrasts', loc='left', fontsize=13)
fig.suptitle('Does targeted follow-up add value with Jev as the final Judge?',
             x=.05, ha='left', fontsize=16, fontweight='bold')
fig.text(.05, .04, 'P: public evidence   C: evidence review   F: fixed follow-up   T: targeted follow-up\n'
         'All observed T-F verdict differences arise from two truncated F answers.\n'
         'Programmatic reference; no independent human gold. Missing outputs remain in denominators.\n'
         '5,000 paired instance-block bootstrap draws. Zero-width empirical intervals do not certify zero error.',
         fontsize=9, color='#475569')
fig.subplots_adjust(left=.075, right=.98, top=.90, bottom=.17, hspace=.53, wspace=.50)
(B/'figures').mkdir(exist_ok=True)
fig.savefig(B/'figures'/'mainline_outcomes.png', dpi=180, facecolor='white')
fig.savefig(B/'figures'/'mainline_outcomes.svg', facecolor='white')
print(B/'figures'/'mainline_outcomes.png')
