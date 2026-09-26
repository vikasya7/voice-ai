from app.agent.nodes import extract_lead_details

state = {
    "messages": [
        type("Message", (), {
            "content": "I'm interested in hair spa. My name is Vikas."
        })()
    ]
}

result = extract_lead_details(state)

print(result)