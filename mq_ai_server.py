#!/usr/bin/env python3
import json
import re
import httpx
import torch
import time
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor

QUESTION = "List all queues on QM1"

MODEL_PATH = "/Users/suchi/projects/IBM-MQ/qwen-mcp-server/Qwen3-VL-8B-Thinking"

MQ_SERVERS = {
    "QM1": {
        "url": "https://localhost:9443/ibmmq/rest/v3/admin/",
        "username": "admin",
        "password": "passw0rd"
    }
}

SYSTEM_PROMPT = (
    "You are an IBM MQ administrator assistant. Keep responses brief and factual. "
    "For MQ queries, immediately call the appropriate tool without explanation."
)

processor = AutoProcessor.from_pretrained(MODEL_PATH, trust_remote_code=True)

model = Qwen3VLForConditionalGeneration.from_pretrained(
    MODEL_PATH,
    torch_dtype=torch.float16,
    device_map="auto",
    trust_remote_code=True
)
model.eval()

def mq_dspmq() -> str:
    headers = {"ibm-mq-rest-csrf-token": "token"}
    results = []
    for qm_name, cfg in MQ_SERVERS.items():
        auth = (cfg["username"], cfg["password"])
        response = httpx.get(cfg["url"] + "qmgr/", headers=headers, auth=auth, verify=False, timeout=30.0)
        data = response.json()
        for qm in data.get("qmgr", []):
            results.append(f"name={qm['name']}, state={qm['state']}")
    return "\n".join(results)

def mq_runmqsc(qmgr_name: str, mqsc_command: str) -> str:
    cfg = MQ_SERVERS[qmgr_name]
    headers = {"ibm-mq-rest-csrf-token": "a"}
    auth = (cfg["username"], cfg["password"])
    url = cfg["url"] + f"action/qmgr/{qmgr_name}/mqsc"
    payload = {"type": "runCommand", "parameters": {"command": mqsc_command}}
    response = httpx.post(url, json=payload, headers=headers, auth=auth, verify=False, timeout=30.0)
    data = response.json()
    lines = [t for item in data.get("commandResponse", []) for t in item.get("text", [])]
    return "\n".join(lines)

def execute_tool(name: str, arguments: dict) -> str:
    if name == "dspmq":
        return mq_dspmq()
    return mq_runmqsc(arguments["qmgr_name"], arguments["mqsc_command"])

def generate(messages: list) -> str:
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=1024)
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=128,
            do_sample=False,
            num_beams=1,
            pad_token_id=processor.tokenizer.pad_token_id,
            eos_token_id=processor.tokenizer.eos_token_id,
            use_cache=True,
        )
    return processor.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()

def parse_tool_call(text: str):
    match = re.search(r'<tool_call>(.*?)</tool_call>', text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            return data.get("name"), data.get("arguments", {})
        except:
            pass
    json_match = re.search(r'\{[^{}]*"name"[^{}]*\}', text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return data.get("name"), data.get("arguments", {})
        except:
            pass
    return None, None

if __name__ == "__main__":
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": QUESTION}
    ]

    response_text = generate(messages)
    tool_name, tool_args = parse_tool_call(response_text)

    if tool_name:
        tool_result = execute_tool(tool_name, tool_args or {})
        messages.append({"role": "assistant", "content": response_text})
        messages.append({"role": "tool", "name": tool_name, "content": tool_result})
        final = generate(messages)
        final = re.sub(r'<tool_call>.*?</tool_call>', '', final, flags=re.DOTALL).strip()
    else:
        final = response_text

    print(final)
