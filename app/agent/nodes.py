
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
from app.voice.normalization import normalize_phone
from app.agent.state import AgentState, AppointmentDetails,RescheduleDetails,LeadDetails
from app.agent.tools import (
    check_availability,
    book_appointment,
    find_appointment,
    cancel_appointment,
    reschedule_appointment,
    save_lead,
    create_human_handoff
)
from app.rag.knowledge import get_retriever

load_dotenv()


# =========================================================
# LLM
# =========================================================

llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0,
)


# =========================================================
# INTENT CLASSIFICATION
# =========================================================

class IntentResult(BaseModel):
    intent: Literal[
        "booking",
        "cancel",
        "reschedule",
        "faq",
        "lead",
        "human",
        "other"
    ]


intent_llm = llm.with_structured_output(IntentResult)


class CancellationDetails(BaseModel):
    customer_phone: str | None = None
    appointment_date: str | None = None
    appointment_time: str | None = None

cancellation_details_llm = llm.with_structured_output(
    CancellationDetails
)

def intent_node(state: AgentState):
    user_message = state["messages"][-1].content

    result = intent_llm.invoke(
        f"""
You are an intent classifier for a business receptionist.

Classify the customer's message into exactly ONE category.

Categories:

booking:
The customer wants to create or make a NEW appointment.

Examples:
- "I want to book an appointment"
- "Can I schedule a haircut?"
- "I need an appointment tomorrow"

cancel:
The customer wants to CANCEL an EXISTING appointment.

Examples:
- "I want to cancel my appointment"
- "Cancel my booking"
- "I need to cancel my appointment"
- "Please cancel my appointment"
- "I don't want my appointment anymore"
- "Can you cancel my booking?"

faq:
The customer is asking a general question about the business.

Examples:
- "What time do you open?"
- "How much does a haircut cost?"
- "Where are you located?"

lead:
The customer is interested in the business but is NOT asking to book
or cancel an appointment.

Examples:
- "I'm interested in your services"
- "Tell me more about your business"

human:
The customer wants to speak to a human.

Examples:
- "Can I talk to someone?"
- "Connect me to an employee"

other:
Anything that does not fit the categories above.

Classify as "reschedule" when the customer wants
to change an existing appointment.

Examples:
"I want to reschedule my appointment"
"I need to change my appointment"
"Can I move my appointment to tomorrow?"
"I want to change my appointment time"

IMPORTANT:
If the customer says "cancel", "cancel my appointment",
"cancel my booking", or similar language about cancelling
an existing appointment, ALWAYS classify it as "cancel", NOT "lead".

Customer message:
{user_message}
"""
    )

    return {
        "intent": result.intent
    }


# =========================================================
# RECEPTIONIST
# =========================================================

def receptionist_node(state: AgentState):

    response = llm.invoke(
        state["messages"]
    )

    return {
        "messages": [response]
    }


# =========================================================
# APPOINTMENT DETAIL EXTRACTION
# =========================================================

details_llm = llm.with_structured_output(
    AppointmentDetails
)

from datetime import datetime
from app.voice.normalization import (
    normalize_phone,
    normalize_time,
    normalize_date,
)
import re
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
def extract_appointment_details(state: AgentState):
    user_message = state["messages"][-1].content

    now = datetime.now()

    current_date = now.strftime("%Y-%m-%d")
    current_day = now.strftime("%A")
    current_time = now.strftime("%H:%M")

    # ---------------------------------------------------------
    # ONLY EXTRACT FIELDS THAT ARE STILL MISSING
    # ---------------------------------------------------------

    missing_fields = []

    if not state.get("customer_name"):
        missing_fields.append("customer_name")

    if not state.get("customer_phone"):
        missing_fields.append("customer_phone")

    if not state.get("service"):
        missing_fields.append("service")

    if not state.get("appointment_date"):
        missing_fields.append("appointment_date")

    if not state.get("appointment_time"):
        missing_fields.append("appointment_time")

    print("🔎 Missing appointment fields:", missing_fields)

    # Nothing left to extract
    if not missing_fields:
        print("✅ All appointment details already collected")
        return {}

    # ---------------------------------------------------------
    # BUILD EXTRACTION PROMPT ONLY FOR MISSING FIELDS
    # ---------------------------------------------------------

    fields_text = "\n".join(
        f"- {field}"
        for field in missing_fields
    )
    print("🧠 Sending details extraction to LLM...")
    print("📝 Message:", user_message)
    print("🎯 Fields:", missing_fields)

    result = details_llm.invoke(
        f"""
You extract appointment information from a customer's message.

ONLY extract these missing fields:

{fields_text}

If a value is not provided, return null.

IMPORTANT:
Do NOT invent information.

IMPORTANT PHONE NUMBER RULES:
- Convert spoken digits into numeric digits.
- Keep phone numbers as digits only.
- Do not interpret phone numbers as dates or times.

IMPORTANT TIME RULES:
Convert appointment times into 24-hour HH:MM format.

Examples:
"5 PM" → "17:00"
"5 p.m." → "17:00"
"6 PM" → "18:00"
"six in the evening" → "18:00"
"10 AM" → "10:00"
"10 p.m." → "22:00"
"12 PM" → "12:00"
"12 AM" → "00:00"
"half past 6" → "18:30"
"quarter past 5" → "17:15"
"quarter to 6" → "17:45"

IMPORTANT DATE RULES:
Convert relative dates into YYYY-MM-DD.

Current date: {current_date}
Current day: {current_day}
Current time: {current_time}

Examples:
"today" → today's date
"tomorrow" → tomorrow's date
"Monday" → next Monday
"next Friday" → next Friday

SERVICE EXAMPLES:
"haircut" → "haircut"
"hair spa" → "hair spa"
"hairspa" → "hairspa"

NAME EXAMPLES:
"My name is Vikas" → customer_name = "Vikas"
"I am Vikas Yadav" → customer_name = "Vikas Yadav"

PHONE EXAMPLES:
"My number is 9876543210" → customer_phone = "9876543210"
"one two three four five six seven eight nine zero"
→ customer_phone = "1234567890"

IMPORTANT:
Do not interpret phone-number digits as appointment time.
Do not extract fields that were not requested.

Customer message:
{user_message}
"""
    )

    updates = {}

    # ---------------------------------------------------------
    # CUSTOMER NAME
    # ---------------------------------------------------------

    if (
        "customer_name" in missing_fields
        and result.customer_name
        and not state.get("customer_name")
    ):
        updates["customer_name"] = result.customer_name

    # ---------------------------------------------------------
    # CUSTOMER PHONE
    # ---------------------------------------------------------

    if (
        "customer_phone" in missing_fields
        and result.customer_phone
        and not state.get("customer_phone")
    ):
        normalized_phone = normalize_phone(
            result.customer_phone
        )

        if normalized_phone:
            updates["customer_phone"] = normalized_phone

    # ---------------------------------------------------------
    # SERVICE
    # ---------------------------------------------------------

    if (
        "service" in missing_fields
        and result.service
        and not state.get("service")
    ):
        updates["service"] = result.service

    # ---------------------------------------------------------
    # DATE
    # ---------------------------------------------------------

    if (
        "appointment_date" in missing_fields
        and not state.get("appointment_date")
    ):

        # First try deterministic parsing from
        # the actual customer message.
        normalized_date = normalize_date(
            user_message,
            today=now.date(),
        )

        if normalized_date:
            updates["appointment_date"] = normalized_date

        elif result.appointment_date:

            normalized_date = normalize_date(
                result.appointment_date,
                today=now.date(),
            )

            if normalized_date:
                updates["appointment_date"] = normalized_date

    # ---------------------------------------------------------
    # TIME
    # ---------------------------------------------------------

    if (
        "appointment_time" in missing_fields
        and not state.get("appointment_time")
    ):

        normalized_time = normalize_time(
            user_message
        )

        print("🕐 TIME DEBUG")
        print("User message:", user_message)
        print("Normalized time:", normalized_time)

        if normalized_time:
            updates["appointment_time"] = normalized_time

        elif result.appointment_time:
            normalized_time = normalize_time(
                result.appointment_time
            )

            if normalized_time:
                updates["appointment_time"] = normalized_time

    # ---------------------------------------------------------
    # DEBUG
    # ---------------------------------------------------------

    print("📦 EXTRACTION UPDATES:", updates)

    return updates


# =========================================================
# BOOKING NODE
# =========================================================




def booking_node(state: AgentState):

    customer_name = state.get("customer_name", "")
    customer_phone = state.get("customer_phone", "")
    service = state.get("service", "")
    appointment_date = state.get("appointment_date", "")
    appointment_time = state.get("appointment_time", "")

    if not customer_name:
        return {
            "messages": [
                AIMessage(content="Sure. May I have your name?")
            ],
            "booking_in_progress": True,
        }

    if not customer_phone:
        return {
            "messages": [
                AIMessage(
                    content="Thanks. Could you please provide your phone number?"
                )
            ],
            "booking_in_progress": True,
        }

    # Normalize phone number
    normalized_phone = normalize_phone(customer_phone)

    if len(normalized_phone) != 10:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I didn't get the complete phone number. "
                        "Could you please provide your 10-digit phone number?"
                    )
                )
            ],
            "booking_in_progress": True,
        }

    # Store normalized phone number in graph state
    customer_phone = normalized_phone

    if not service:
        return {
            "messages": [
                AIMessage(content="What service would you like to book?")
            ],
            "booking_in_progress": True,
        }

    if not appointment_date:
        return {
            "messages": [
                AIMessage(
                    content="What date would you like the appointment?"
                )
            ],
            "booking_in_progress": True,
        }

    if not appointment_time:
        return {
            "messages": [
                AIMessage(
                    content="What time would you prefer?"
                )
            ],
            "booking_in_progress": True,
        }

    is_available = check_availability.invoke({
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
    })

    if not is_available:
        return {
            "messages": [
                AIMessage(
                    content=(
                        f"Sorry, {appointment_time} is already booked "
                        f"on {appointment_date}. "
                        f"What other time would you prefer?"
                    )
                )
            ],
            "booking_in_progress": True,
        }

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Great, {appointment_time} is available "
                    f"on {appointment_date}. "
                    f"I have you down for {service}. "
                    f"Shall I book the appointment?"
                )
            )
        ],
        "customer_phone": customer_phone,
        "booking_in_progress": False,
        "awaiting_confirmation": True,
    }





# =========================================================
# CONFIRMATION CLASSIFIER
# =========================================================

class ConfirmationResult(BaseModel):

    confirmed: bool


confirmation_llm = llm.with_structured_output(
    ConfirmationResult
)



def confirmation_node(state: AgentState):
    user_message = state["messages"][-1].content

    result = confirmation_llm.invoke(
        f"""
Determine whether the customer is confirming
the appointment booking.

Return confirmed=true when the customer clearly
agrees to book.

Examples:
"yes" -> true
"book it" -> true
"confirm" -> true
"go ahead" -> true
"yes please" -> true

Return confirmed=false when the customer declines
or is not clearly confirming.

Examples:
"no" -> false
"not now" -> false
"I don't want it" -> false

Customer message:
{user_message}
"""
    )

    if result.confirmed:
        return {
            "booking_confirmed": True,
        }

    return {
        "booking_confirmed": False,
        "awaiting_confirmation": False,
        "messages": [
            AIMessage(
                content=(
                    "No problem. I won't book it. "
                    "Let me know if you'd like to choose "
                    "another appointment time."
                )
            )
        ],
    }




# =========================================================
# ACTUAL BOOKING
# =========================================================


def confirm_booking_node(state: AgentState):

    result = book_appointment.invoke({
    "session_id": state.get("session_id", ""),
    "customer_name": state.get("customer_name", "Customer"),
    "customer_phone": state.get("customer_phone"),
    "appointment_date": state["appointment_date"],
    "appointment_time": state["appointment_time"],
    "service": state.get("service"),
    })

    if not result["success"]:
        return {
            "awaiting_confirmation": False,
            "booking_confirmed": False,
            "messages": [
                AIMessage(
                    content=result["message"]
                )
            ]
        }

    return {
        "awaiting_confirmation": False,
        "booking_confirmed": True,
        "messages": [
            AIMessage(
                content=(
                    f"Your appointment is confirmed "
                    f"for {state['appointment_date']} "
                    f"at {state['appointment_time']}. "
                    f"Your appointment ID is "
                    f"{result['appointment_id']}."
                )
            )
        ]
    }



# =========================================================
# FAQ
# =========================================================

def faq_node(
    state: AgentState
):

    return {
        "messages": [
            AIMessage(
                content=(
                    "Sure, I can help answer "
                    "your question."
                )
            )
        ]
    }


# =========================================================
# LEAD
# =========================================================

def lead_node(
    state: AgentState
):

    return {
        "messages": [
            AIMessage(
                content=(
                    "Sure, I'd be happy to get "
                    "some details from you."
                )
            )
        ]
    }


# =========================================================
# HUMAN HANDOFF
# =========================================================

def human_node(
    state: AgentState
):

    return {
        "messages": [
            AIMessage(
                content=(
                    "Sure, I'll connect you with "
                    "a human representative."
                )
            )
        ]
    }


# =========================================================
# OTHER
# =========================================================

def other_node(
    state: AgentState
):

    return {
        "messages": [
            AIMessage(
                content=(
                    "I'm sorry, I didn't quite "
                    "understand that."
                )
            )
        ]
    }


# =========================================================
# INTENT ROUTER
# =========================================================

def route_intent(
    state: AgentState
):

    return state["intent"]



def extract_cancellation_details(state: AgentState):
    print("🔥 EXTRACT CANCELLATION DETAILS")

    user_message = state["messages"][-1].content

    result = cancellation_details_llm.invoke(
        f"""
Extract the customer's phone number from this message.

Customer message:
{user_message}

If no phone number is present, return null.
"""
    )

    print("🔥 EXTRACTED:", result)

    updates = {}

    if result.customer_phone:
        updates["customer_phone"] = result.customer_phone

    return updates


def cancellation_node(state: AgentState):
    customer_phone = state.get("customer_phone", "")
    appointment_date = state.get("appointment_date", "")
    appointment_time = state.get("appointment_time", "")

    print("🔥 CANCELLATION NODE")
    print("PHONE:", customer_phone)
    print("DATE:", appointment_date)
    print("TIME:", appointment_time)

    if not customer_phone:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "Sure. Please provide the phone number "
                        "associated with your appointment."
                    )
                )
            ],
            "cancellation_in_progress": True,
        }

    appointment = find_appointment.invoke({
    "customer_phone": customer_phone,
    "appointment_date": appointment_date or None,
    "appointment_time": appointment_time or None,
    })

    if not appointment:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I couldn't find a confirmed appointment "
                        "with those details."
                    )
                )
            ],
            "cancellation_in_progress": False,
        }
    print("🔥 CANCELLATION NODE RETURNING CONFIRMATION")
    return {
        "messages": [
            AIMessage(
                content=(
                    f"I found your appointment for "
                    f"{appointment.appointment_date} at "
                    f"{appointment.appointment_time}. "
                    f"Would you like me to cancel it?"
                )
            )
        ],
        "cancellation_in_progress": False,
        "awaiting_cancellation_confirmation": True,
    }

def cancellation_confirmation_node(state: AgentState):
    user_message = state["messages"][-1].content

    result = confirmation_llm.invoke(
        f"""
Determine whether the customer clearly confirms
that they want to cancel their appointment.

Return confirmed=true for:

"yes"
"cancel it"
"yes please"
"go ahead"
"confirm"

Return confirmed=false for:

"no"
"don't cancel"
"not now"

Customer message:

{user_message}
"""
    )

    if result.confirmed:
        return {
            "cancellation_confirmed": True
        }

    return {
        "cancellation_confirmed": False,
        "awaiting_cancellation_confirmation": False,
        "messages": [
            AIMessage(
                content="No problem. I won't cancel your appointment."
            )
        ],
    }


def confirm_cancellation_node(state: AgentState):

    print("🔥🔥🔥 CONFIRM CANCELLATION NODE EXECUTED")
    customer_phone = state.get("customer_phone", "")
    appointment_date = state.get("appointment_date", "")
    appointment_time = state.get("appointment_time", "")

    appointment=find_appointment.invoke({
        "customer_phone":customer_phone,
        "appointment_date":appointment_date,
        "appointment_time":appointment_time
    })

    if not appointment:
        return {
            "awaiting_cancellation_confirmation": False,
            "cancellation_confirmed": False,
            "messages": [
                AIMessage(
                    content="I couldn't find that appointment."
                )
            ],
        }

    result = cancel_appointment.invoke({
    "appointment_id": appointment.id
     })

    if not result["success"]:
        return {
            "awaiting_cancellation_confirmation": False,
            "cancellation_confirmed": False,
            "messages": [
                AIMessage(content=result["message"])
            ],
        }

    return {
        "awaiting_cancellation_confirmation": False,
        "cancellation_confirmed": True,
        "messages": [
            AIMessage(
                content=(
                    f"Your appointment for "
                    f"{appointment.appointment_date} at "
                    f"{appointment.appointment_time} "
                    f"has been cancelled successfully."
                )
            )
        ],
    }

reschedule_details_llm = llm.with_structured_output(
    RescheduleDetails
)


def extract_reschedule_details(state: AgentState):
    print("🔥 EXTRACT RESCHEDULE DETAILS")

    user_message = state["messages"][-1].content

    result = reschedule_details_llm.invoke(
        f"""
Extract rescheduling information from the customer's message.

Extract:

- customer_phone
- appointment_date
- appointment_time

For appointment_date and appointment_time,
extract the NEW date and NEW time that the customer
wants to reschedule to.

If a value is not provided, return null.

Examples:

"I want to reschedule my appointment"
→ customer_phone = null
→ appointment_date = null
→ appointment_time = null

"My phone number is 9876543210"
→ customer_phone = 9876543210
→ appointment_date = null
→ appointment_time = null

"Move it to tomorrow at 6 PM"
→ appointment_date = tomorrow's date
→ appointment_time = 18:00

"My number is 9876543210, move my appointment
to tomorrow at 6 PM"
→ customer_phone = 9876543210
→ appointment_date = tomorrow's date
→ appointment_time = 18:00

Customer message:
{user_message}
"""
    )

    print("🔥 RESCHEDULE EXTRACTED:", result)

    updates = {}

    if result.customer_phone:
        updates["customer_phone"] = result.customer_phone

    if result.appointment_date:
        updates["appointment_date"] = result.appointment_date

    if result.appointment_time:
        updates["appointment_time"] = result.appointment_time

    return updates


def reschedule_node(state:AgentState):
    customer_phone=state.get("customer_phone","")
    new_date=state.get("appointment_date","")
    new_time=state.get("appointment_time","")

    print("🔥 RESCHEDULE NODE")
    print("PHONE:", customer_phone)
    print("NEW DATE:", new_date)
    print("NEW TIME:", new_time)

    # ask for phone number
    if not customer_phone:
        return {
            "messages":[
                AIMessage(
                    content=
                    "Sure. Please provide the phone number "
                        "associated with your appointment."
                )
            ],
            "reschedule_in_progress": True,
        }
    # 2. Ask for new date
    if not new_date:
        return {
            "messages": [
                AIMessage(
                    content="What new date would you like for your appointment?"
                )
            ],
            "reschedule_in_progress": True,
        }

    # 3. Ask for new time
    if not new_time:
        return {
            "messages": [
                AIMessage(
                    content="What new time would you prefer?"
                )
            ],
            "reschedule_in_progress": True,
        }
    # 4. Find existing appointment
    appointment = find_appointment.invoke({
        "customer_phone": customer_phone,
    })

    if not appointment:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I couldn't find a confirmed appointment "
                        "with that phone number."
                    )
                )
            ],
            "reschedule_in_progress": False,
        }

    # 5. Check whether new slot is available
    is_available = check_availability.invoke({
        "appointment_date":new_date,
        "appointment_time":new_time
    })
    if not is_available:
        return {
            "messages": [
                AIMessage(
                    content=(
                        f"Sorry, {new_time} on {new_date} "
                        "is already booked. "
                        "What other time would you prefer?"
                    )
                )
            ],
            "reschedule_in_progress": True,
        }

    # 6. Ask for confirmation
    return {
        "messages": [
            AIMessage(
                content=(
                    f"I found your appointment for "
                    f"{appointment.appointment_date} at "
                    f"{appointment.appointment_time}. "
                    f"Would you like to move it to "
                    f"{new_date} at {new_time}?"
                )
            )
        ],
        "reschedule_in_progress": False,
        "awaiting_reschedule_confirmation": True,
    }


def reschedule_confirmation_node(state:AgentState):
    print("🔥 RESCHEDULE CONFIRMATION NODE")

    user_message = state["messages"][-1].content

    result = confirmation_llm.invoke(
        f"""
Determine whether the customer clearly confirms
that they want to reschedule their appointment.

Return confirmed=true for:
"yes"
"yes please"
"go ahead"
"confirm"
"move it"

Return confirmed=false for:
"no"
"don't change it"
"not now"

Customer message:
{user_message}
"""
    )
    print("🔥 RESCHEDULE CONFIRMATION RESULT:", result)
    if result.confirmed:
        return {
            "reschedule_confirmed":True
        }

    return {
        "reschedule_confirmed": False,
        "awaiting_reschedule_confirmation": False,
        "messages": [
            AIMessage(
                content=(
                    "No problem. I won't change your appointment."
                )
            )
        ],
    }
    

def confirm_reschedule_node(state:AgentState):
    print("🔥 CONFIRM RESCHEDULE")

    customer_phone = state.get("customer_phone", "")
    new_date = state.get("appointment_date", "")
    new_time = state.get("appointment_time", "")

    appointment = find_appointment.invoke({
        "customer_phone": customer_phone,
    })
    if not appointment:
        return {
            "awaiting_reschedule_confirmation": False,
            "reschedule_confirmed": False,
            "messages": [
                AIMessage(
                    content="I couldn't find your appointment."
                )
            ],
        }

    result = reschedule_appointment.invoke({
        "appointment_id":appointment.id,
        "new_date":new_date,
        "new_time":new_time,
    })
    
    if not result["success"]:
        return {
            "awaiting_reschedule_confirmation": False,
            "reschedule_confirmed": False,
            "messages": [
                AIMessage(
                    content=result["message"]
                )
            ],
        }

    return {
        "awaiting_reschedule_confirmation": False,
        "reschedule_confirmed": True,
        "messages": [
            AIMessage(
                content=(
                    f"Your appointment has been rescheduled "
                    f"to {new_date} at {new_time} successfully."
                )
            )
        ],
    }


FAQS = {
    "opening_hours": """
We are open Monday to Saturday from 9 AM to 7 PM.
We are closed on Sundays.
""",

    "location": """
We are located at 123 Main Street.
""",

    "services": """
We provide haircuts, hair styling, beard trimming,
and grooming services.
""",

    "payment": """
We accept cash, UPI, and card payments.
""",
}


retriever = get_retriever()


def faq_node(state: AgentState):
    user_message = state["messages"][-1].content

    docs = retriever.invoke(user_message)

    context = "\n\n".join(
        doc.page_content
        for doc in docs
    )

    response = llm.invoke(
        f"""
You are a helpful receptionist.

Answer the customer's question using ONLY
the following business information.

BUSINESS INFORMATION:
{context}

If the information needed to answer the question
is not available, say:

"I'm sorry, I don't have that information right now."

Do not invent business information.

Customer question:
{user_message}
"""
    )

    return {
        "messages": [
            AIMessage(content=response.content)
        ]
    }


lead_details_llm = llm.with_structured_output(LeadDetails)


def extract_lead_details(state: AgentState):
    print("🔥 EXTRACT LEAD DETAILS")

    user_message = state["messages"][-1].content

    result = lead_details_llm.invoke(
        f"""
Extract lead/customer information from the customer's message.

Extract:
- customer_name
- customer_phone
- service
- preferred_time
- requirement

If a value is not provided, return null.

Examples:

"My name is Vikas"
→ customer_name = Vikas

"My number is 9876543210"
→ customer_phone = 9876543210

"I'm interested in hair spa"
→ service = hair spa

"I want to visit Saturday evening"
→ preferred_time = Saturday evening

"I want to know about hair treatment for damaged hair"
→ requirement = hair treatment for damaged hair

Customer message:
{user_message}
"""
    )

    print("🔥 LEAD EXTRACTED:", result)

    updates = {}

    if result.customer_name:
        updates["customer_name"] = result.customer_name

    if result.customer_phone:
        updates["customer_phone"] = result.customer_phone

    if result.service:
        updates["service"] = result.service

    if result.preferred_time:
        updates["preferred_time"] = result.preferred_time

    if result.requirement:
        updates["requirement"] = result.requirement

    return updates





def lead_node(state: AgentState):
    customer_name = state.get("customer_name", "")
    customer_phone = state.get("customer_phone", "")
    service = state.get("service", "")
    preferred_time = state.get("preferred_time", "")
    requirement = state.get("requirement", "")

    if not customer_name:
        return {
            "messages": [
                AIMessage(content="Sure. May I have your name?")
            ],
            "lead_in_progress": True,
        }

    if not customer_phone:
        return {
            "messages": [
                AIMessage(
                    content="What is the best phone number to reach you?"
                )
            ],
            "lead_in_progress": True,
        }

    if not service:
        return {
            "messages": [
                AIMessage(
                    content="What service are you interested in?"
                )
            ],
            "lead_in_progress": True,
        }

    if not preferred_time:
        return {
            "messages": [
                AIMessage(
                    content="When would you prefer to visit?"
                )
            ],
            "lead_in_progress": True,
        }

    # All required information collected
    result = save_lead.invoke({
    "session_id": state["session_id"],
    "customer_name": customer_name,
    "customer_phone": customer_phone,
    "service": service,
    "preferred_time": preferred_time,
    "requirement": requirement,
    })

    if not result["success"]:
        return {
            "messages": [
                AIMessage(
                    content="I'm sorry, I couldn't save your information. Please try again."
                )
            ],
            "lead_in_progress": False,
        }

    return {
        "messages": [
            AIMessage(
                content=(
                    f"Thanks, {customer_name}. I've noted your interest "
                    f"in {service}. Our team will contact you at "
                    f"{customer_phone}. Your lead reference is "
                    f"{result['lead_id']}."
                )
            )
        ],
        "lead_in_progress": False,
        "lead_saved": True,
    }


def human_node(state:AgentState):
    customer_name=state.get("customer_name","")
    customer_phone=state.get("customer_phone","")

    result=create_human_handoff.invoke({
        "session_id":state["session_id"],
        "customer_name":customer_name,
        "customer_phone":customer_phone,
        "reason": "Customer requested human assistance",
    })
    if not result["success"]:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I'm sorry, I couldn't connect your request "
                        "to our team right now. Please try again."
                    )
                )
            ]
        }

    return {
        "messages": [
            AIMessage(
                content=(
                    "Sure. I've forwarded your request to our team. "
                    "Someone will assist you shortly."
                )
            )
        ]
    }