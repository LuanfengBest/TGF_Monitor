"""Frozen native history -> Harmony, with final text/reminders retained, no tools.

The upstream exporter flattens assistant channels into content. This deterministic
reconstruction uses that exported convention; it does not claim original token IDs.
Only structured historical calls become recipients, never tool-looking prose.
"""
from copy import deepcopy
import json
import re


def assistant_segments(content):
    parts = re.split(r"assistant(analysis|commentary|final)", content)
    first = parts[0]
    if first.startswith("analysis"):
        first = first[len("analysis"):]
    segments = [("analysis", first.strip())] if first.strip() else []
    for i in range(1, len(parts), 2):
        segments.append((parts[i], parts[i + 1].strip()))
    return segments


def conversation_with_question(original, question):
    from openai_harmony import Author, Conversation, DeveloperContent, Message, ReasoningEffort, Role, SystemContent
    conv = deepcopy(original)  # Every arm reopens the same frozen history.
    system = SystemContent.new().with_reasoning_effort(ReasoningEffort.HIGH)
    developer = DeveloperContent.new()
    instructions = [m["content"] for m in conv if m["role"] in {"system", "monitor"}]
    if instructions:
        developer = developer.with_instructions("\n\n".join(instructions))
    # No with_function_tools(), dispatcher, simulator or executable tool registry.
    messages = [Message.from_role_and_content(Role.SYSTEM, system),
                Message.from_role_and_content(Role.DEVELOPER, developer)]
    for m in conv:
        role = m["role"]
        if role in {"system", "monitor"}:
            continue
        if role == "user":
            messages.append(Message.from_role_and_content(Role.USER, m["content"]))
        elif role == "assistant":
            calls, inserted = m.get("tool_calls") or [], False
            for channel, content in assistant_segments(m["content"]):
                if channel == "commentary" and content.startswith("to=functions.") and calls:
                    if not inserted:
                        for call in calls:
                            messages.append(Message.from_role_and_content(Role.ASSISTANT, json.dumps(call["args"]))
                                            .with_channel("commentary").with_recipient("functions." + call["function"])
                                            .with_content_type("<|constrain|> json"))
                        inserted = True
                elif content:
                    messages.append(Message.from_role_and_content(Role.ASSISTANT, content).with_channel(channel))
            if calls and not inserted:
                for call in calls:
                    messages.append(Message.from_role_and_content(Role.ASSISTANT, json.dumps(call["args"]))
                                    .with_channel("commentary").with_recipient("functions." + call["function"])
                                    .with_content_type("<|constrain|> json"))
        elif role == "tool":
            name = m["tool_call"]["function"]
            messages.append(Message.from_author_and_content(Author.new(Role.TOOL, "functions." + name),
                                                            m.get("error") or m["content"]).with_channel("commentary"))
        else:
            raise ValueError("Unsupported native role")
    messages.append(Message.from_role_and_content(Role.USER, question))
    return Conversation.from_messages(messages)


class HarmonyCodec:
    def __init__(self):
        from openai_harmony import HarmonyEncodingName, load_harmony_encoding
        self.enc = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)

    def prompt(self, conv, question):
        from openai_harmony import Role
        return self.enc.render_conversation_for_completion(conversation_with_question(conv, question), Role.ASSISTANT)

    def count_question(self, question):
        return len(self.enc.encode(question))

    def answer(self, tokens, finish_reason):
        from openai_harmony import Role
        if finish_reason != "stop":
            raise ValueError("Truncated actor generation")
        messages = self.enc.parse_messages_from_completion_tokens(tokens, Role.ASSISTANT)
        finals, reasoning = [], []
        for message in messages:
            data = message.to_dict()
            if data.get("recipient"):
                raise ValueError("Actor attempted a tool call; tools were not executed")
            text = "".join(part.get("text", "") for part in data.get("content", []) if isinstance(part, dict))
            channel = data.get("channel")
            if channel == "analysis":
                reasoning.append(text)
            elif channel == "final":
                finals.append(text)
            else:
                raise ValueError("Actor response lacks an unambiguous final channel")
        if len(finals) != 1 or not finals[0].strip():
            raise ValueError("Exactly one nonempty final answer required")
        return {"answer": finals[0], "reasoning": "\n".join(reasoning)}
