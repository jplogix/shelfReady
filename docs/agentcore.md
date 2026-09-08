# Amazon Bedrock AgentCore (optional later milestone)

Deploying with AgentCore can strengthen the hackathon **Technical Implementation** score but is **not required**.

**Do not run these steps against a paid AWS account without explicit authorization.**

## Approaches (from current Strands docs)

1. **SDK integration** — `bedrock-agentcore` + `BedrockAgentCoreApp` entrypoint wrapping a Strands `Agent`.
2. **Custom FastAPI** — expose required `/invocations` (POST) and `/ping` (GET), containerize **linux/arm64**, push to ECR, `CreateAgentRuntime`.

Reference: [Deploy Python agents to AgentCore](https://strandsagents.com/docs/user-guide/deploy/deploy_to_bedrock_agentcore/python/)

## Suggested mapping for ShelfReady

ShelfReady’s long-running import/decision workflow is primarily the **FastAPI + worker + Postgres** path. AgentCore is a better fit for a thin **invoke** surface that:

- Accepts `{ "input": { "prompt": "..." } }` or batch_id
- Calls the same tool functions / `execute_job`
- Returns outcomes + decision summaries

A sketch entrypoint (not deployed):

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

app = BedrockAgentCoreApp()
# Wire ShelfReady tools the same way as app.agent.runner._build_strands_agent

@app.entrypoint
def invoke(payload):
    prompt = payload.get("prompt") or payload.get("input", {}).get("prompt")
    # run agent or enqueue job — do not invent a silent replay fallback
    return {"status": "not_deployed_in_mvp"}
```

## Blocked without authorization

- Creating ECR repositories, IAM roles, or AgentCore runtimes
- Spending AWS credits / promotional credits
- Publishing a public demo URL
