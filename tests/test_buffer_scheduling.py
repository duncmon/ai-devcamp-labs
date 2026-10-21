import datetime
from backend.social_poster.agent import _delay_buffer_post, _track_stage_before_tool

class FakeTool:
    def __init__(self, name="create_post"):
        self.name = name

class FakeContext:
    def __init__(self, state=None):
        self.state = state or {}

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

def test_buffer_auto_attaches_image_asset():
    args = {"channelId": "123", "text": "Testing image asset injection"}
    ctx = FakeContext(state={"current_image_url": "https://storage.googleapis.com/test-bucket/image.png"})
    _delay_buffer_post(FakeTool("create_post"), args, ctx)
    assert args.get("assets") == [{"image": {"url": "https://storage.googleapis.com/test-bucket/image.png"}}]

def test_linkedin_auto_attaches_image_path(tmp_path):
    img_file = tmp_path / "test.png"
    img_file.write_bytes(b"fake png")
    args = {"text": "Testing linkedin image attachment"}
    ctx = FakeContext(state={"current_image_path": str(img_file)})
    _delay_buffer_post(FakeTool("linkedin_create_post"), args, ctx)
    assert args.get("image_path") == str(img_file)

def test_track_stage_before_tool():
    ctx = FakeContext(state={"pipeline_stage": "idea"})
    _track_stage_before_tool(FakeTool("research_agent"), {}, ctx)
    assert ctx.state["pipeline_stage"] == "researching"

    _track_stage_before_tool(FakeTool("draft_agent"), {}, ctx)
    assert ctx.state["pipeline_stage"] == "drafting"

