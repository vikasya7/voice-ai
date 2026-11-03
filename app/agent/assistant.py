
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List
from app.agent.assistant_tools import calculate,search_web

llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0,
)




class AssistantResponse(BaseModel):
    response: str = Field(
        description="Complete written answer for the API response."
    )
    spoken_response: str = Field(
        description="A concise, natural answer suitable for text-to-speech. "
                    "Do not include URLs, headings, or bullet points."
    )
    sources: List[str] = Field(
        default_factory=list,
        description="Source URLs actually returned by the search tool."
    )


tools = [calculate,search_web]

assistant_agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt=(
        "You are a helpful AI personal assistant and voice receptionist. "

        "Keep responses short, ideally 1–3 sentences and under 40 words. "
        "Use natural, friendly language suitable for phone conversations. "
        "Avoid long explanations, bullet points, and unnecessary details. "
        "Ask only one question at a time. "


        "LANGUAGE ADAPTATION: "
"You are bilingual in Hindi and English. "
"Automatically detect the language used by the customer and respond in the same language. "
"If the customer speaks English, respond in natural English. "
"If the customer speaks Hindi, respond in natural conversational Hindi using Devanagari script. "
"If the customer speaks Hinglish, respond in natural Hinglish, using Devanagari for Hindi words and Latin script for English words. "
"If the customer switches languages during the conversation, switch your response language accordingly. "
"Do not unnecessarily mix languages when the customer speaks entirely in one language. "
"Avoid overly formal or literary Hindi. "
"Do not let language adaptation change names, dates, times, phone numbers, or tool arguments. "

        "Use the calculate tool for arithmetic. "
        "Use search_web for current information, recent news, "
        "latest updates, and explicit web research. "
        "Prefer official sources and never invent facts, versions, "
        "release dates, or URLs. "

        "Follow the existing booking, cancellation, rescheduling, "
        "FAQ, and lead-handling workflows. "
        "Ask only for the next missing appointment detail. "
        "Never claim an appointment is confirmed unless the workflow "
        "or relevant tool confirms it. "

        "Keep written responses informative and include source URLs "
        "when available. For voice output, use a separate concise "
        "spoken_response of 1–3 natural sentences without headings, "
        "bullet points, URLs, or source lists. "

        "For software version questions, identify the specific package, "
        "check official registries and release notes when available, "
        "and distinguish latest published, latest stable, and installed "
        "versions when relevant. Explain uncertainty or source "
        "disagreements instead of making unsupported claims."
    ),
)



def assistant_node(state):
    

    result = assistant_agent.invoke({
        "messages": state['messages']
    })

    # Log actual tool calls and results.
    for message in result["messages"]:
        tool_calls = getattr(message, "tool_calls", None)

        if tool_calls:
            for call in tool_calls:
                print(
                    "TOOL CALL:",
                    call.get("name"),
                    call.get("args"),
                )

        if getattr(message, "type", None) == "tool":
            print(
                "TOOL RESULT:",
                message.name,
                message.content,
            )

    # The agent's final answer.
    final_message = result["messages"][-1]
    written_answer = final_message.content

    # Collect URLs from the actual search tool results.
    sources = []
    for message in result["messages"]:
        if (
            getattr(message, "type", None) == "tool"
            and "search" in getattr(message, "name", "").lower()
        ):
            content = message.content
            if isinstance(content, str):
                import re
                urls = re.findall(
                    r"https?://[^\s<>\"']+",
                    content,
                )
                sources.extend(urls)

    sources = list(dict.fromkeys(sources))

    # Generate a separate voice-friendly answer.
    formatted = llm.with_structured_output(
        AssistantResponse
    ).invoke(
        [
            (
                "system",
                "Create a structured response for a voice assistant. "
                "Preserve the factual meaning of the written answer. "
                "The spoken_response must be 1-2 short natural sentences, "
"Aim for 20-30 words maximum. "
                "with no URLs, headings, or bullet points. "
                "Keep the written response informative. "
                "Use only the supplied source URLs; never invent URLs. "
                "Do not claim a release is the latest unless supported."
            ),
            (
                "human",
                f"User question: {state['messages'][-1].content}\n\n"
                f"Written answer: {written_answer}\n\n"
                f"Source URLs returned by tools: {sources}"
            ),
        ]
    )

    # Do not let the formatting model invent additional sources.
    verified_sources = [
        url for url in formatted.sources if url in sources
    ]

    # Keep the original agent message in the graph state.
    # Store the additional fields for the API route.
    return {
        "messages": [final_message],
        "assistant_response": formatted.response,
        "spoken_response": formatted.spoken_response,
        "sources": verified_sources,
    }
