from app.agent.tools import cancel_appointment

def test_cannot_cancel_appointment_twice():
    result=cancel_appointment.invoke({
        "appointment_id":23
    })
    assert result["success"] is False
    assert result["message"] == "Appointment is already cancelled."