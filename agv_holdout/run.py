import json,random,sys
from pathlib import Path
from agv_v0.run import core,request_for,start_qwen,states,split_timing_state

def main():
    folder=Path(sys.argv[1])
    cases=json.loads((folder/"public.json").read_text())
    jobs=[(cid,arm) for cid in sorted(cases) for arm in ("raw","agv","agv_split")]
    random.Random(5880).shuffle(jobs)
    with (folder/"qwen.jsonl").open("x") as out:
        backend=start_qwen()
        try:
            for cid,arm in jobs:
                record=cases[cid]
                state=split_timing_state(record) if arm=="agv_split" else states(record)[arm]
                req=request_for("qwen",state)
                raw=backend.generate(req,240)
                row=dict(case_id=cid,arm=arm,input_hash=core.digest(req),**core.parse_response("qwen",raw))
                print(core.canonical(row),file=out,flush=True)
        finally:
            backend.close()

if __name__=="__main__":
    main()
