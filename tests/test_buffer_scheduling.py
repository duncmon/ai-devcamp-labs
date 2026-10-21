import datetime
from backend.social_poster.agent import _delay_buffer_post

class FakeTool:
    name = "create_post"

def test_buffer_preserves_future_schedule():
    future_due = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    args = {"channelId": "123", "dueAt": future_due, "text": "Testing future schedule"}
    _delay_buffer_post(FakeTool(), args, None)
    assert args["dueAt"] == future_due
    assert args["mode"] == "customScheduled"
    assert args["schedulingType"] == "automatic"

def test_buffer_enforces_minimum_delay_when_missing():
    args = {"channelId": "123", "text": "Testing immediate post"}
    _delay_buffer_post(FakeTool(), args, None)
    assert args["mode"] == "customScheduled"
    assert args["schedulingType"] == "automatic"
    assert "dueAt" in args
