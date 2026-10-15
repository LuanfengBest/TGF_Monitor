"""Thin vLLM wrappers. Mirrors how MonitorBench itself loads models
(pipeline/generation/run.py), so whatever ran in the smoke test runs here."""

import gc
import json
import os
import re


# ------------------------------------------------------------ monitor (Qwen) --

class ChatModel:
    """Offline vLLM chat model (Qwen3 etc.). generate() returns, per prompt,
    a list of n dicts {text, prompt_tokens, completion_tokens}."""

    def __init__(self, model, max_model_len=32768, rope_factor=2.0, gpu_util=0.90, tp=1, dry_run=False):
        self.dry_run = dry_run
        self.model_name = model
        if dry_run:
            self.max_len = int(max_model_len * (rope_factor or 1))
            self.tok = None
            return
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        from vllm import LLM
        kw = {"model": model, "gpu_memory_utilization": gpu_util, "tensor_parallel_size": tp}
        if rope_factor and rope_factor > 1:
            kw["hf_overrides"] = {"rope_parameters": {
                "rope_type": "yarn", "factor": rope_factor,
                "original_max_position_embeddings": max_model_len}}
            self.max_len = int(max_model_len * rope_factor)
        else:
            self.max_len = max_model_len
        kw["max_model_len"] = self.max_len
        self.llm = LLM(**kw)
        self.tok = self.llm.get_tokenizer()

    def count(self, text):
        if self.tok is None:
            return len(text) // 4
        return len(self.tok.encode(text))

    def format(self, user_text):
        if self.tok is None:
            return user_text
        return self.tok.apply_chat_template([{"role": "user", "content": user_text}],
                                            tokenize=False, add_generation_prompt=True)

    def generate(self, user_texts, n=1, max_tokens=8192, temperature=0.6, top_p=0.95, seed=42, fake=None):
        if self.dry_run:
            return [[{"text": fake(t) if fake else "<score>50</score>",
                      "prompt_tokens": len(t) // 4, "completion_tokens": 50} for _ in range(n)]
                    for t in user_texts]
        from vllm import SamplingParams
        sp = SamplingParams(n=n, max_tokens=max_tokens, temperature=temperature, top_p=top_p, seed=seed)
        prompts = [self.format(t) for t in user_texts]
        outs = self.llm.generate(prompts, sp, use_tqdm=True)
        res = []
        for o in outs:
            pt = len(o.prompt_token_ids)
            res.append([{"text": c.text, "prompt_tokens": pt, "completion_tokens": len(c.token_ids)}
                        for c in o.outputs])
        return res

    def close(self):
        if not self.dry_run:
            del self.llm
            gc.collect()
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass


def after_think(text):
    return text.split("</think>")[-1] if "</think>" in text else text


def parse_score(text):
    body = after_think(text)
    m = re.findall(r"<score>\s*(-?\d+(?:\.\d+)?)\s*</score>", body)
    if not m:
        m = re.findall(r"<score>\s*(-?\d+(?:\.\d+)?)\s*</score>", text)
    if not m:
        m = re.findall(r"[Ss]core\D{0,15}(\d{1,3}(?:\.\d+)?)", body)
    if not m:
        return None
    return max(0.0, min(100.0, float(m[-1])))


def parse_json_obj(text):
    body = after_think(text)
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end <= start:
        return None
    chunk = body[start:end + 1]
    for cand in (chunk, re.sub(r",\s*([}\]])", r"\1", chunk)):
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    return None


# --------------------------------------------------------- agent (gpt-oss) --

def _extract_harmony_cot(raw_text):
    m = re.search(r"assistant(?:commentary|final|analysis)", raw_text)
    cot = raw_text[: m.start()] if m else raw_text
    if cot.startswith("analysis"):
        cot = cot[len("analysis"):]
    return cot.strip()


class HarmonyAgent:
    """Re-opens a frozen gpt-oss conversation and asks one more user question
    with no tools available. Conversation -> Harmony conversion copies
    MonitorBench's llms/vllm_llm.py::_messages_to_harmony_conversation."""

    def __init__(self, model, max_model_len=65536, gpu_util=0.90, dry_run=False):
        self.dry_run = dry_run
        if dry_run:
            self.max_len = max_model_len
            return
        from openai_harmony import HarmonyEncodingName, load_harmony_encoding
        from vllm import LLM
        self.enc = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
        self.llm = LLM(model=model, gpu_memory_utilization=gpu_util, tensor_parallel_size=1,
                       max_model_len=max_model_len)
        self.max_len = max_model_len

    def _conversation(self, conv, question):
        from openai_harmony import (Author, Conversation, DeveloperContent, Message,
                                    ReasoningEffort, Role, SystemContent)
        sys_content = SystemContent.new().with_reasoning_effort(ReasoningEffort.HIGH)
        dev_parts = [m["content"] for m in conv if m["role"] in ("system", "monitor")]
        dev = DeveloperContent.new()
        if dev_parts:
            dev = dev.with_instructions("\n\n".join(dev_parts))
        msgs = [Message.from_role_and_content(Role.SYSTEM, sys_content),
                Message.from_role_and_content(Role.DEVELOPER, dev)]
        for m in conv:
            r = m["role"]
            if r in ("system", "monitor"):
                continue
            if r == "user":
                msgs.append(Message.from_role_and_content(Role.USER, m["content"]))
            elif r == "assistant":
                msgs.append(Message.from_role_and_content(
                    Role.ASSISTANT, _extract_harmony_cot(m["content"] or "")).with_channel("analysis"))
                for tc in m.get("tool_calls") or []:
                    msgs.append(Message.from_role_and_content(Role.ASSISTANT, json.dumps(tc["args"]))
                                .with_channel("commentary")
                                .with_recipient(f"functions.{tc['function']}")
                                .with_content_type("<|constrain|> json"))
            elif r == "tool":
                name = (m.get("tool_call") or {}).get("function", "unknown")
                msgs.append(Message.from_author_and_content(
                    Author.new(Role.TOOL, f"functions.{name}"), m.get("error") or m["content"] or ""
                ).with_channel("commentary"))
        msgs.append(Message.from_role_and_content(Role.USER, question))
        return Conversation.from_messages(msgs)

    def answer(self, items, max_tokens=4096, temperature=0.6, top_p=0.9, seed=42):
        """items: list of (conversation, question). Returns list of dicts."""
        if self.dry_run:
            return [{"cot": "dry-run reasoning", "answer": "dry-run answer", "tried_tool_call": False,
                     "prompt_tokens": 1000, "completion_tokens": 50, "skipped": False} for _ in items]
        from openai_harmony import Role
        from vllm import SamplingParams
        prompts, keep = [], []
        for i, (conv, q) in enumerate(items):
            ids = self.enc.render_conversation_for_completion(self._conversation(conv, q), Role.ASSISTANT)
            if len(ids) + max_tokens > self.max_len:
                keep.append(None)
                continue
            keep.append(len(prompts))
            prompts.append({"prompt_token_ids": ids})
        sp = SamplingParams(max_tokens=max_tokens, temperature=temperature, top_p=top_p, seed=seed,
                            stop_token_ids=self.enc.stop_tokens_for_assistant_actions())
        outs = self.llm.generate(prompts, sp, use_tqdm=True) if prompts else []
        res = []
        for k in keep:
            if k is None:
                res.append({"cot": "", "answer": "", "tried_tool_call": False, "prompt_tokens": 0,
                            "completion_tokens": 0, "skipped": True})
                continue
            o = outs[k]
            c = o.outputs[0]
            cot, ans, tool = self._parse(list(c.token_ids), c.text)
            res.append({"cot": cot, "answer": ans, "tried_tool_call": tool,
                        "prompt_tokens": len(o.prompt_token_ids), "completion_tokens": len(c.token_ids),
                        "skipped": False})
        return res

    def _parse(self, token_ids, raw):
        from openai_harmony import Role
        try:
            msgs = self.enc.parse_messages_from_completion_tokens(token_ids, Role.ASSISTANT)
            cot, ans, tool = [], [], False
            for m in msgs:
                d = m.to_dict()
                text = "".join(p.get("text", "") for p in d.get("content", []) if isinstance(p, dict))
                ch, rcpt = d.get("channel"), d.get("recipient")
                if rcpt and str(rcpt).startswith("functions."):
                    tool = True
                    ans.append(f"[attempted tool call {rcpt}: {text}]")
                elif ch == "analysis":
                    cot.append(text)
                else:
                    ans.append(text)
            return "\n".join(cot).strip(), "\n".join(ans).strip(), tool
        except Exception:
            cot = _extract_harmony_cot(raw)
            m = re.search(r"assistantfinal(.*)$", raw, re.DOTALL)
            ans = m.group(1) if m else raw[len(cot):]
            return cot, ans.strip(), "to=functions" in raw

    def close(self):
        if not self.dry_run:
            del self.llm
            gc.collect()
