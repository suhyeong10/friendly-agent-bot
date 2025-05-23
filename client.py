import os
import json
import base64
import asyncio
import logging
import requests
from dotenv import load_dotenv
from contextlib import suppress
from typing import Optional, List

import discord

from langchain_ollama import ChatOllama
from langchain.agents import AgentExecutor, create_structured_chat_agent
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory

from mcp_manager import cleanup_mcp_client, init_mcp_client

load_dotenv()
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

client = discord.Client(intents=intents)

system_prompt = """
## Instructions
너는 사용자랑 동갑내기 친구처럼 자연스럽게 얘기하는 챗봇이야. 말투는 반말이고, AI 같지 않게 친근하게 대화해줘.

1. 사용자는 공감을 바라는 사람이야. 도구 호출이 먼저가 아닌 대화를 하고나서 사용자에게 공감하며 대화를 먼저해줘.
2. **사용자가 먼저 추천을 요청하거나**, 대화 중 분위기에 진짜 자연스럽게 맞을 때만 가볍게 추천해줘.
3. 만약 추천을 해줄거라면 너가 직접 너의 지식을 믿고 링크나 노래를 만들어내지 말고 **반드시 도구를 사용해서 추천해.**
4. 사용자가 추천을 요청하지 않았는데, 너가 먼저 추천하는 건 **절대 금지야.**
5. 사용자에게 추천을 해준경우, 해당 추천 내용을 계속 지속적으로로 언급하는 행동은 **절대 금지야.**
6. 바로 추천부터 하지 말고, "나도 그래~" / "나도 그런 기분 느껴본 적 있어" 같은 식으로 먼저 공감하고, 사용자의 감정에 맞춰 대화를 살짝 이어나간 다음 추천해줘.
7. 정보 검색의 경우 너의 지식이 아닌 검색 도구를 사용해.
8. 추천할 때는 너가 직접 추천하지 말고, **반드시 도구를 사용해서 추천해**.
9. 강요하거나 명령하지 말고, "한번 해보는 거 어때?", "괜찮으면 해봐~"처럼 부드럽게 제안해.
10. 'ㅋㅋㅋㅋㅋ'와 'ㅠㅠ' 같은 표현이나 이모티콘을 적극적으로 사용해.
11. 노래 추천 시 마크다운의 임베디드 문법으로 **[노래 이름](링크) 형식**으로 써줘. (단, 추천할 정보를 받지 않는 경우는 해당 문법을 쓰지마)
12. 추천은 목록처럼 나열하지 말고, 하나의 문장처럼 자연스럽게 이야기해줘. (예: "요즘 [노래 제목](링크) 이런 노래 있는데, 너 스타일일지도 몰라!")
13. 장소랑 노래를 같이 추천할 땐 루틴처럼 제안해줘. (예: "[카페 이름] 가서 [행동]하면서 [노래 제목](링크) 듣는 건 어때?")
14. 사용자가 감정에 맞게 추천을 요청할 경우, 감정에 어울리는 걸 추천해줘. (예: "슬플 때 들으면 위로될 노래야" / "기분 좋을 때 들으면 더 신나는 노래야")
15. 모든 응답은 **256토큰** 이내로 해줘.

## Tool 사용 규칙
도구 호출이 먼저가 아닌 대화를 하고나서 사용자에게 공감하며 대화를 먼저해줘.
도구를 호출할 시 사람에게 최대한 도움이 되고 정확하게 응답해줘. 다음 도구들을 사용할 수 있어.

{tools}

도구를 사용할때는, action key (도구 이름)와  action_input (도구 입력값)를 포함한 JSON 객체 형식으로 작성해야해.

사용할 수 있는 유효한 "action"값: Final Answer 또는 {tool_names}

⚠️ 중요:
대부분의 도구는 단순 문자열이 아닌 JSON 객체 형태의 입력값을 필요로 해.
예를 들어, 아래와 같은 형식은 ❌ 잘못된 예시야:
```
{{
    "action": "get_naver_place_tool",
    "action_input": "카페"
}}
```
반드시 아래와 같이 작성해야해:
```
{{
    "action": "get_naver_place_tool",
    "action_input": {{ "query": "카페" }}
}}
```
도구가 여러 입력값을 요구하는 경우, 필드 이름이 해당 도구의 스키마와 일치하도록 JSON 객체를 구성해야해.
그리고 반드시 한 번에 하나의 도구만 사용해야 하며, 아래 형식을 따라야 해:
```
{{
    "action": $TOOL_NAME,
    "action_input": $INPUT_OBJECT
}}
```

### 사용 포맷
Question: 사용자의 입력 질문을 답변해. 원하는 대로 만들지 말고, 그대로 반영해.  
Thought: 이전과 후속 단계를 고려해.  
Action:
```
$JSON_BLOB
```
Observation: 도구 결과  
... (repeat Thought/Action/Observation N times)  
Thought: 응답할 것을 알았어.  
Action:
```
{{
    "action": "Final Answer",
    "action_input": "사용자에게 응답"
}}
```

시작작! 반드시 유효한 JSON 블롭 하나의 도구 행동을 응답해. 필요한 경우 도구를 사용해. 적절한 경우 직접 응답해. 형식은 Action:```$JSON_BLOB``` then Observation
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{input}"),
    ("ai", "{agent_scratchpad}"),
])

llm = ChatOllama(
    model="PetrosStav/gemma3-tools:12b", 
    base_url="http://localhost:11434",
    temperature=0.2,
    top_p=0.95,
    top_k=64,
    num_predict=256,
    repeat_penalty=1.2,
    num_gpu=1,
    num_ctx=2048,
    num_thread=8
)

store = {}
def get_session_history(session_ids: str) -> BaseChatMessageHistory:
    if session_ids not in store:
        store[session_ids] = ChatMessageHistory()
    return store[session_ids]

agent = None
mcp_client = None
def get_agent(
        tools: Optional[List] = None
    ) -> RunnableWithMessageHistory:

    agent = create_structured_chat_agent(
        tools=tools,
        llm=llm,
        prompt=prompt
    )

    agent_executor = AgentExecutor(
        agent=agent, 
        tools=tools,
        handle_parsing_errors=True,
        verbose=True
    )

    agent_with_chat_history = RunnableWithMessageHistory(
        agent_executor,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    return agent_with_chat_history

def chat_log(session_id: str, user_input: str, ai_output: str):
    file_path = os.path.join("training_logs", f"{session_id}.json")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    log_entry = {
        "user": user_input,
        "ai": ai_output
    }

    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
    else:
        logs = []

    logs.append(log_entry)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

async def show_typing(channel, stop_event: asyncio.Event):
    while not stop_event.is_set():
        async with channel.typing():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                continue

@client.event
async def on_ready():
    global agent, mcp_client
    print(f'Logged in as {client.user.name}')

    try:
        mcp_client, mcp_tools = await init_mcp_client()
        if mcp_client is None or mcp_tools is None:
            logger.error("❗ MCP 클라이언트 초기화 실패")
            return

        agent = get_agent(mcp_tools)
        for tool in mcp_tools:
            logger.info(f"Tool: {tool.name}")
            logger.info(f"Description: {tool.description}")
        logger.info("✅ MCP 클라이언트 초기화 성공")

    except Exception as e:
        logger.exception(f"🚨 MCP 초기화 중 오류 발생: {e}")
        if mcp_client:
            await cleanup_mcp_client(mcp_client)
        mcp_client = None
        agent = None

@client.event
async def on_message(message):
    global agent, mcp_client
    if message.author == client.user:
        return

    if agent is None or mcp_client is None:
        await message.channel.send("⚠️ 아직 준비 중이야. 잠시만 기다려줘~")
        return

    session_id = str(message.author.id)

    if message.content.startswith("!clear"):
        if session_id in store:
            del store[session_id]

        if isinstance(message.channel, discord.TextChannel):
            await message.channel.purge(limit=100)
            await message.channel.send("🧹 대화 기록과 채널 메시지를 정리했어!")
        else:
            await message.channel.send("⚠️ 텍스트 채널에서만 정리할 수 있어!")
        return

    is_chat_channel = message.channel.name == "chatbot"
    is_chat_command = message.content.startswith("!채팅")
    config = {"configurable": {"session_id": session_id}}

    if not is_chat_channel and not is_chat_command:
        return

    content = message.content[len("!채팅"):].strip() if is_chat_command else message.content.strip()

    if not content:
        await message.channel.send("❗ 대화 내용이 비어있어!")
        return

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(show_typing(message.channel, stop_typing))

    try:
        if message.attachments:
            attachment = message.attachments[0]
            if attachment.content_type and attachment.content_type.startswith("image/"):
                ext = attachment.content_type.split("/")[1]
                if ext not in ["png", "jpeg", "webp", "gif"]:
                    await message.channel.send("나는 png, jpeg, webp, gif 같은 이미지 파일만 받을 수 있어 🙏")
                    return

                response = requests.get(attachment.url)
                image_bytes = response.content
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                mime_type = attachment.content_type 
                image_data_url = f"data:{mime_type};base64,{image_base64}"

                user_msg = [
                    {"type": "text", "text": content},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]

                response = await llm.ainvoke(
                    [
                        {"role": "system", "content": system_prompt.strip()},
                        {"role": "user", "content": user_msg}
                    ],
                    config={
                        "configurable": {"session_id": session_id},
                        "get_session_history": get_session_history
                    }
                )

                if session_id not in store:
                    store[session_id] = ChatMessageHistory()

                store[session_id].add_user_message(HumanMessage(content=content))
                store[session_id].add_ai_message(AIMessage(content=response.content))

                await message.channel.send(response.content)

                chat_log(session_id, content, response.content)
            else:
                await message.channel.send("⚠️ 지금은 이미지 파일만 분석할 수 있어!")
                return
        else:
            result = await agent.ainvoke(
                {"input": [
                    {"role": "user", "content": content},
                ]},
                config=config,
            )

            output = result.get("output", str(result)) if isinstance(result, dict) else str(result)
            await message.channel.send(output)

            chat_log(session_id, content, output)

    finally:
        stop_typing.set()
        with suppress(asyncio.CancelledError):
            await typing_task

client.run(os.getenv('DISCORD_TOKEN'))
