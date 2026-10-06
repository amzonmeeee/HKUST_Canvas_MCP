"""Synthetic fixtures only. Browser and HTTP access remain blocked by conftest."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import StringIO
import json
from threading import Barrier
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from rich.console import Console
from typer.testing import CliRunner

from auth import CanvasAPIError
from client import CanvasClient
from cli import app, bootstrap
from cli.output import _Pretty, _render
from specs.registry import dispatch_tool_call
from tools import activity, interactions, write_confirmation


def batch(items=(), truncated=False):
    return {"items": list(items), "truncated": truncated}


@pytest.fixture
def activity_client(mock_client, monkeypatch, tmp_path):
    monkeypatch.setenv("CANVASMCP_CONFIRMATION_DIR", str(tmp_path / "confirmations"))
    mock_client.base_url = "https://canvas.ust.hk"
    mock_client.profile_path = "/synthetic/chrome-profile"
    mock_client.activity_get.return_value = {"id": 42, "name": "Synthetic Student"}
    mock_client.activity_list.return_value = batch()
    mock_client.activity_write.return_value = {"id": 100}
    return mock_client


NOW = datetime(2026, 1, 10, tzinfo=timezone.utc)


@pytest.mark.parametrize("assignment, expected", [
    ({"submission": {"excused": True, "missing": True}}, "excused"),
    ({"submission_types": ["external_tool"], "submission": {"workflow_state": "unsubmitted", "missing": True}}, "external_tool"),
    ({"submission_types": ["external_tool"], "submission": {"workflow_state": "graded"}}, "graded"),
    ({"submission_types": ["external_tool"], "submission": {"workflow_state": "submitted"}}, "submitted"),
    ({"submission": {"missing": True, "workflow_state": "graded"}}, "missing"),
    ({"submission": {"workflow_state": "graded", "submitted_at": None}}, "graded"),
    ({"submission": {"workflow_state": "pending_review"}}, "submitted"),
    ({"submission": {"submitted_at": "2026-01-01T00:00:00Z"}}, "submitted"),
    ({"submission_types": ["on_paper"], "submission": {"workflow_state": "unsubmitted"}}, "not_required"),
    ({"submission_types": ["none"]}, "not_required"),
    ({"published": False}, "unpublished"),
    ({"submission": None}, "unknown"),
    ({"due_at": "2026-01-01T00:00:00Z", "submission": {"workflow_state": "unsubmitted"}}, "overdue"),
    ({"due_at": "2026-01-01T00:00:00Z", "submission": {"cached_due_date": "2026-02-01T00:00:00Z"}}, "unsubmitted"),
    ({"due_at": "2026-01-01T00:00:00Z", "submission": {"cached_due_date": None}}, "unsubmitted"),
    ({"due_at": "not a date", "submission": {"workflow_state": "unsubmitted"}}, "unsubmitted"),
    ({"due_at": "2026-01-01", "submission": {"workflow_state": "unsubmitted"}}, "unsubmitted"),
])
def test_submission_classification(assignment, expected):
    assert activity.submission_state(assignment, NOW) == expected


def test_submission_scan_filters_and_discloses_limits(activity_client):
    def listing(endpoint, **kwargs):
        if endpoint == "courses":
            assert kwargs["params"]["enrollment_type"] == "student"
            return batch([{"id": 1}, {"id": 2}], truncated=True)
        if endpoint == "courses/2/assignments":
            raise CanvasAPIError("Restricted", status_code=403)
        assert kwargs["params"] == {"include": ["submission"]}
        return batch([
            {"id": 10, "submission": {"missing": True}},
            {"id": 11, "submission_types": ["external_tool"]},
            {"id": 12, "submission": {"missing": True}},
        ], truncated=True)
    activity_client.activity_list.side_effect = listing
    result = dispatch_tool_call("get_my_submission_status", {"missing_only": True, "limit": 1})
    assert result["partial"] and result["truncated"]
    assert result["count"] == 1 and result["matched_count"] == 2
    assert result["scanned_count"] == 3
    assert result["status_counts"] == {"missing": 2, "external_tool": 1}
    assert len(result["warnings"]) == 3
    assert result["assignments"][0]["assignment_id"] == "10"


def test_submission_single_course_no_course_discovery(activity_client):
    activity_client.activity_list.return_value = batch([{"id": 67890, "submission": {"workflow_state": "graded"}}])
    result = dispatch_tool_call("get_my_submission_status", {"course_id": "12345", "status": "graded"})
    assert result["assignments"][0]["status"] == "graded"
    activity_client.activity_list.assert_called_once_with("courses/12345/assignments", params={"include": ["submission"]}, limit=100)


def test_peer_review_merges_planner_and_filters_assessor(activity_client):
    def listing(endpoint, **kwargs):
        if endpoint.endswith("/assignments"):
            return batch([{"id": 67890, "name": "Synthetic Essay", "peer_reviews": True}])
        if endpoint.endswith("/peer_reviews"):
            return batch([
                {"id": 7, "assessor_id": "42", "workflow_state": "assigned", "asset_id": 55, "user": {"name": "Must stay anonymous"}},
                {"id": 8, "assessor_id": 99, "workflow_state": "assigned"},
                {"id": 9, "assessor_id": 42, "workflow_state": "completed"},
            ])
        assert endpoint == "planner/items"
        assert "start_date" not in kwargs["params"]
        assert kwargs["params"]["context_codes"] == ["course_12345"]
        return batch([
            {"course_id": 12345, "plannable_type": "assessment_request", "plannable": {"id": "7", "title": "Synthetic Essay", "workflow_state": "assigned"}, "html_url": "/courses/12345/assignments/67890/submissions/55"},
            {"course_id": 12345, "plannable_type": "assessment_request", "plannable_id": 10, "plannable": {"title": "Planner-only Review"}},
            {"course_id": 99999, "plannable_type": "assessment_request", "plannable": {"id": 11}},
            {"course_id": 12345, "plannable_type": "assessment_request", "plannable": {"id": 12, "workflow_state": "completed"}},
            {"course_id": 12345, "plannable_type": "assessment_request", "plannable": {"id": 13, "assessor_id": 99}},
            {"course_id": 12345, "plannable_type": "assignment", "plannable": {"id": 14}},
        ])
    activity_client.activity_list.side_effect = listing
    result = dispatch_tool_call("get_my_peer_reviews_todo", {"course_id": "12345"})
    assert result["count"] == 2 and not result["partial"]
    assert result["peer_reviews"][0]["sources"] == ["assignment", "planner"]
    assert result["peer_reviews"][1]["assignment_id"] is None
    assert "Must stay anonymous" not in json.dumps(result)


def test_peer_review_permission_failure_keeps_planner_findings(activity_client):
    def listing(endpoint, **kwargs):
        if endpoint.endswith("/assignments"):
            return batch([{"id": 67890, "peer_reviews": True}])
        if endpoint.endswith("/peer_reviews"):
            raise CanvasAPIError("Forbidden", status_code=403)
        return batch([{"course_id": 12345, "plannable_type": "assessment_request", "plannable": {"id": 1}}], truncated=True)
    activity_client.activity_list.side_effect = listing
    result = dispatch_tool_call("get_my_peer_reviews_todo", {"course_id": "12345"})
    assert result["partial"] and result["count"] == 1
    assert len(result["warnings"]) == 2


def test_peer_review_empty_is_partial_on_planner_failure(activity_client):
    activity_client.activity_list.side_effect = [batch(), CanvasAPIError("Unavailable")]
    result = dispatch_tool_call("get_my_peer_reviews_todo", {"course_id": "12345"})
    assert result["count"] == 0 and result["partial"]


def test_direct_peer_review_checks_assignment_even_flag_missing(activity_client):
    activity_client.activity_get.side_effect = [{"id": 42}, {"id": 67890, "name": "Direct Assignment"}]
    activity_client.activity_list.side_effect = [batch([{"id": 1, "assessor_id": 42}]), batch([
        {"course_id": 12345, "plannable_type": "assessment_request", "plannable": {"id": 2}, "html_url": "/courses/12345/assignments/98765/submissions/44"},
        {"course_id": 12345, "plannable_type": "assessment_request", "plannable": {"id": 3}},
    ])]
    result = dispatch_tool_call("get_my_peer_reviews_todo", {"course_id": "12345", "assignment_id": "67890"})
    assert [row["id"] for row in result["peer_reviews"]] == ["1"]
    activity_client.activity_get.assert_any_call("courses/12345/assignments/67890")


def test_peer_assignment_requires_course(activity_client):
    result = dispatch_tool_call("get_my_peer_reviews_todo", {"assignment_id": "67890"})
    assert result["error"] == "invalid_argument"
    activity_client.activity_get.assert_not_called()


def test_conversation_read_never_marks_as_read(activity_client):
    activity_client.activity_get.return_value = {"id": 20, "messages": [{"id": 1}, {"id": 2}], "workflow_state": "unread"}
    result = dispatch_tool_call("get_conversation_details", {"conversation_id": "20", "limit": 1})
    activity_client.activity_get.assert_called_once_with("conversations/20", params={"auto_mark_as_read": False})
    assert result["truncated"] and result["conversation"]["workflow_state"] == "unread"
    assert len(result["conversation"]["messages"]) == 1
    activity_client.activity_write.assert_not_called()


def test_structure_uses_canonical_items_and_reports_partial(activity_client):
    activity_client.activity_get.return_value = {"id": 12345, "name": "Synthetic Course"}
    def listing(endpoint, **kwargs):
        if endpoint.endswith("/modules"):
            return batch([
                {"id": 1, "name": "Week 1", "items": [{"id": 99}], "prerequisite_module_ids": [5]},
                {"id": 2, "name": "Week 2"}, {"id": 3, "published": False},
            ])
        if endpoint.endswith("/2/items"):
            raise CanvasAPIError("Forbidden", status_code=403)
        return batch([{"id": 10, "type": "Page", "completion_requirement": {"type": "must_mark_done", "completed": False}}, {"id": 11, "type": "Assignment"}], truncated=True)
    activity_client.activity_list.side_effect = listing
    result = dispatch_tool_call("get_course_structure", {"course_id": "12345", "include_unpublished": False})
    assert result["partial"] and result["module_count"] == 2
    assert result["item_type_counts"] == {"Page": 1, "Assignment": 1}
    assert result["modules"][0]["items"][0]["id"] == 10
    assert result["modules"][0]["prerequisite_module_ids"] == [5]
    assert "items_error" in result["modules"][1]


WRITE_CASES = [
    ("post_discussion_entry", {"course_id": "12345", "topic_id": "30", "message": "<p>Synthetic post</p>"}, "POST", "courses/12345/discussion_topics/30/entries", {"message": "<p>Synthetic post</p>"}),
    ("reply_to_discussion_entry", {"course_id": "12345", "topic_id": "30", "entry_id": "31", "message": "Synthetic reply"}, "POST", "courses/12345/discussion_topics/30/entries/31/replies", {"message": "Synthetic reply"}),
    ("add_submission_comment", {"course_id": "12345", "assignment_id": "67890", "comment": "Synthetic comment", "attempt": 2}, "PUT", "courses/12345/assignments/67890/submissions/self", {"comment": {"text_comment": "Synthetic comment", "attempt": 2}}),
    ("send_conversation", {"recipients": ["50", "51"], "subject": "Synthetic subject", "body": "Synthetic message", "course_id": "12345"}, "POST", "conversations", {"recipients": ["50", "51"], "subject": "Synthetic subject", "body": "Synthetic message", "group_conversation": False, "context_code": "course_12345"}),
    ("reply_to_conversation", {"conversation_id": "20", "body": "Synthetic reply"}, "POST", "conversations/20/add_message", {"body": "Synthetic reply", "recipients": ["50"]}),
    ("update_conversation", {"conversation_id": "20", "workflow_state": "archived"}, "PUT", "conversations/20", {"conversation": {"workflow_state": "archived"}}),
    ("mark_module_item_done", {"course_id": "12345", "module_id": "60", "item_id": "61"}, "PUT", "courses/12345/modules/60/items/61/done", {}),
    ("mark_module_item_done", {"course_id": "12345", "module_id": "60", "item_id": "61", "done": False}, "DELETE", "courses/12345/modules/60/items/61/done", {}),
]


def preflight(client, *, done=False):
    def fetch(endpoint, **kwargs):
        if endpoint == "users/self":
            return {"id": 42, "name": "Synthetic Student"}
        if "/items/" in endpoint:
            return {"id": 61, "title": "Synthetic page", "completion_requirement": {"type": "must_mark_done", "completed": done}}
        if endpoint.startswith("conversations/"):
            assert kwargs["params"]["auto_mark_as_read"] is False
            return {"id": 20, "subject": "Synthetic subject", "workflow_state": "unread", "audience": [50], "participants": [{"id": 42}, {"id": 50}, {"id": 99, "name": "Forwarded author"}]}
        return {"id": 60, "name": "Synthetic target", "title": "Synthetic discussion", "published": True}
    client.activity_get.side_effect = fetch


@pytest.mark.parametrize("name,args,method,endpoint,payload", WRITE_CASES)
def test_preview_confirm_and_one_use(activity_client, name, args, method, endpoint, payload):
    preflight(activity_client, done=args.get("done") is False)
    preview = dispatch_tool_call(name, args)
    assert preview["status"] == "preview" and preview["written"] is False
    assert preview["payload"] == payload
    activity_client.activity_write.assert_not_called()
    confirmed = {**args, "confirmation_token": preview["confirmation_token"]}
    result = dispatch_tool_call(name, confirmed)
    assert result["status"] == "accepted"
    activity_client.activity_write.assert_called_once_with(method, endpoint, payload)
    retry = dispatch_tool_call(name, confirmed)
    assert retry["error"] == "invalid_confirmation"
    assert activity_client.activity_write.call_count == 1


@pytest.mark.parametrize("change", ["body", "recipients", "subject", "group", "account", "profile"])
def test_confirmation_binds_exact_intent_and_identity(activity_client, change):
    args = {"recipients": ["50"], "subject": "Synthetic", "body": "Original"}
    preview = dispatch_tool_call("send_conversation", args)
    confirmed = {**args, "confirmation_token": preview["confirmation_token"]}
    if change in {"body", "subject"}:
        confirmed[change] = "Changed"
    elif change == "recipients":
        confirmed["recipients"] = ["51"]
    elif change == "group":
        confirmed["group_conversation"] = True
    elif change == "account":
        activity_client.activity_get.return_value = {"id": 99}
    else:
        activity_client.profile_path = "/synthetic/other-profile"
    result = dispatch_tool_call("send_conversation", confirmed)
    assert result["error"] == "invalid_confirmation"
    activity_client.activity_write.assert_not_called()


def test_confirmation_expiration(activity_client, monkeypatch):
    args = {"recipients": ["50"], "subject": "Synthetic", "body": "Text"}
    monkeypatch.setattr(write_confirmation.time, "time", lambda: 1000)
    preview = dispatch_tool_call("send_conversation", args)
    monkeypatch.setattr(write_confirmation.time, "time", lambda: 1601)
    result = dispatch_tool_call("send_conversation", {**args, "confirmation_token": preview["confirmation_token"]})
    assert "expired" in result["message"]
    activity_client.activity_write.assert_not_called()


def test_inbox_reply_excludes_forwarded_authors(activity_client):
    preflight(activity_client)
    preview = dispatch_tool_call("reply_to_conversation", {"conversation_id": "20", "body": "Text"})
    assert preview["payload"]["recipients"] == ["50"]
    assert preview["target"]["participants"] == [{"id": 50, "name": None}]
    assert "Forwarded author" not in json.dumps(preview)


def test_inbox_reply_requires_authoritative_audience(activity_client):
    activity_client.activity_get.return_value = {"id": 42, "participants": [{"id": 99}]}
    result = dispatch_tool_call("reply_to_conversation", {"conversation_id": "20", "body": "Text"})
    assert result["error"] == "invalid_argument"
    activity_client.activity_write.assert_not_called()


def test_confirmation_consumed_when_target_becomes_done(activity_client):
    preflight(activity_client)
    args = {"course_id": "1", "module_id": "2", "item_id": "3"}
    preview = dispatch_tool_call("mark_module_item_done", args)
    confirmed = {**args, "confirmation_token": preview["confirmation_token"]}
    preflight(activity_client, done=True)
    result = dispatch_tool_call("mark_module_item_done", confirmed)
    assert result["status"] == "already_in_requested_state"
    assert result["confirmation_consumed"]
    preflight(activity_client, done=False)
    assert dispatch_tool_call("mark_module_item_done", confirmed)["error"] == "invalid_confirmation"
    activity_client.activity_write.assert_not_called()


def test_ambiguous_write_failure_consumes_confirmation(activity_client):
    args = {"recipients": ["50"], "subject": "Synthetic", "body": "Text"}
    preview = dispatch_tool_call("send_conversation", args)
    activity_client.activity_write.side_effect = TimeoutError("Synthetic timeout")
    confirmed = {**args, "confirmation_token": preview["confirmation_token"]}
    result = dispatch_tool_call("send_conversation", confirmed)
    assert result["error"] == "write_failed" and result["confirmation_consumed"]
    assert dispatch_tool_call("send_conversation", confirmed)["error"] == "invalid_confirmation"
    assert activity_client.activity_write.call_count == 1


def test_store_saves_hashes_only(activity_client, tmp_path):
    args = {"recipients": ["50"], "subject": "Private Subject", "body": "Private Content"}
    preview = dispatch_tool_call("send_conversation", args)
    root = tmp_path / "confirmations"
    path = next(root.glob("*.json"))
    content = path.read_text()
    assert set(json.loads(content)) == {"fingerprint", "expires_at"}
    for secret in ("Private Subject", "Private Content", activity_client.profile_path, preview["confirmation_token"]):
        assert secret not in content
    assert path.stat().st_mode & 0o777 == 0o600
    assert root.stat().st_mode & 0o777 == 0o700


def test_concurrent_confirmation_claim_is_atomic(activity_client, monkeypatch):
    token, _ = write_confirmation.issue_confirmation({"synthetic": "intent"})
    barrier = Barrier(2)
    original_load = write_confirmation.json.load
    def synchronized_load(stream):
        result = original_load(stream)
        barrier.wait(timeout=5)
        return result
    monkeypatch.setattr(write_confirmation.json, "load", synchronized_load)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: write_confirmation.claim_confirmation(token, {"synthetic": "intent"}), range(2)))
    assert results.count(None) == 1


@pytest.mark.parametrize("requirement", [None, {"type": "must_submit"}, {"type": "must_view"}, {"type": "min_score"}])
def test_module_rejects_unsupported_completion(activity_client, requirement):
    activity_client.activity_get.return_value = {"id": 42, "completion_requirement": requirement}
    result = dispatch_tool_call("mark_module_item_done", {"course_id": "1", "module_id": "2", "item_id": "3"})
    assert result["error"] == "invalid_argument"
    activity_client.activity_write.assert_not_called()


def test_module_already_done_does_not_write(activity_client):
    preflight(activity_client, done=True)
    result = dispatch_tool_call("mark_module_item_done", {"course_id": "1", "module_id": "2", "item_id": "3"})
    assert result["status"] == "already_in_requested_state"
    activity_client.activity_write.assert_not_called()


def test_module_verifies_state_after_write(activity_client):
    preflight(activity_client)
    args = {"course_id": "1", "module_id": "2", "item_id": "3"}
    preview = dispatch_tool_call("mark_module_item_done", args)
    def write(*args):
        preflight(activity_client, done=True)
        return {}
    activity_client.activity_write.side_effect = write
    result = dispatch_tool_call("mark_module_item_done", {**args, "confirmation_token": preview["confirmation_token"]})
    assert result["verified"] is True


def test_locked_discussion_never_previews_or_posts(activity_client):
    activity_client.activity_get.return_value = {"id": 42, "locked": True}
    result = dispatch_tool_call("post_discussion_entry", {"course_id": "1", "topic_id": "2", "message": "Text"})
    assert result["error"] == "invalid_argument"
    activity_client.activity_write.assert_not_called()


@pytest.mark.parametrize("restriction", ["locked", "locked_for_user", "unpublished"])
@pytest.mark.parametrize("action", ["post_discussion_entry", "reply_to_discussion_entry"])
def test_discussion_explicit_reply_permission_overrides_publication_state(activity_client, restriction, action):
    topic = {"id": 42, "permissions": {"reply": True}}
    topic["published" if restriction == "unpublished" else restriction] = False if restriction == "unpublished" else True
    activity_client.activity_get.return_value = topic
    args = {"course_id": "1", "topic_id": "2", "message": "Synthetic test post"}
    if action == "reply_to_discussion_entry":
        args["entry_id"] = "3"
    result = dispatch_tool_call(action, args)
    assert result["status"] == "preview" and result["written"] is False
    activity_client.activity_write.assert_not_called()


def test_discussion_explicit_reply_denial_blocks_published_topic(activity_client):
    activity_client.activity_get.return_value = {"id": 42, "published": True, "locked": False, "permissions": {"reply": False}}
    result = dispatch_tool_call("post_discussion_entry", {"course_id": "1", "topic_id": "2", "message": "Synthetic test post"})
    assert result["error"] == "invalid_argument"
    activity_client.activity_write.assert_not_called()


@pytest.mark.parametrize("permission", [None, "true", 1])
def test_unpublished_discussion_requires_explicit_boolean_reply_permission(activity_client, permission):
    activity_client.activity_get.return_value = {"id": 42, "published": False, "permissions": {"reply": permission}}
    result = dispatch_tool_call("post_discussion_entry", {"course_id": "1", "topic_id": "2", "message": "Synthetic test post"})
    assert result["error"] == "invalid_argument"
    activity_client.activity_write.assert_not_called()


@pytest.mark.parametrize("name,args", [
    ("post_discussion_entry", {"course_id": "../private", "topic_id": "2", "message": "Text"}),
    ("send_conversation", {"recipients": ["50", "50"], "subject": "Text", "body": "Text"}),
    ("send_conversation", {"recipients": [], "subject": "Text", "body": "Text"}),
    ("send_conversation", {"recipients": ["50"], "subject": "Text", "body": "   "}),
    ("get_my_submission_status", {"limit": 301}),
    ("add_submission_comment", {"course_id": "1", "assignment_id": "2", "comment": "Text", "student_id": "99"}),
])
def test_invalid_arguments_never_write(activity_client, name, args):
    result = dispatch_tool_call(name, args)
    assert result["error"] == "invalid_argument"
    activity_client.activity_write.assert_not_called()


def _response(request, value, *, status=200, link=None):
    response = requests.Response()
    response.status_code = status
    response.url = request.url
    response.request = request
    response._content = b"" if status == 204 else json.dumps(value).encode()
    if link:
        response.headers["Link"] = link
    return response


def test_real_sdk_paginated_limit_and_cookie_session(monkeypatch):
    requests_seen = []
    def send(session, request, **kwargs):
        requests_seen.append(request)
        if len(requests_seen) == 1:
            return _response(request, [{"id": 1}], link='<https://canvas.ust.hk/api/v1/conversations?page=2>; rel="next"')
        return _response(request, [{"id": 2}, {"id": 3}])
    monkeypatch.setattr(requests.sessions.Session, "send", send)
    client = CanvasClient(cookie_provider=lambda: ("synthetic-session", "synthetic-csrf"))
    result = client.activity_list("conversations", limit=2)
    assert result == batch([{"id": 1}, {"id": 2}], truncated=True)
    assert len(requests_seen) == 2
    assert "canvas_session=synthetic-session" in requests_seen[0].headers["Cookie"]
    assert requests_seen[0].headers["X-CSRF-Token"] == "synthetic-csrf"


@pytest.mark.parametrize("method, endpoint, payload, form", [
    ("PUT", "courses/1/assignments/2/submissions/self", {"comment": {"text_comment": "Synthetic comment", "attempt": 2}}, {"comment[text_comment]": ["Synthetic comment"], "comment[attempt]": ["2"]}),
    ("POST", "conversations", {"recipients": ["50", "51"], "body": "Synthetic", "group_conversation": False}, {"recipients[]": ["50", "51"], "body": ["Synthetic"], "group_conversation": ["false"]}),
    ("POST", "courses/1/discussion_topics/2/entries", {"message": "<p>Synthetic</p>"}, {"message": ["<p>Synthetic</p>"]}),
    ("PUT", "conversations/2", {"conversation": {"workflow_state": "archived"}}, {"conversation[workflow_state]": ["archived"]}),
    ("DELETE", "courses/1/modules/2/items/3/done", {}, {}),
])
def test_real_sdk_writes_correct_form_without_bearer_auth(monkeypatch, method, endpoint, payload, form):
    seen = []
    def send(session, request, **kwargs):
        seen.append(request)
        return _response(request, {}, status=204)
    monkeypatch.setattr(requests.sessions.Session, "send", send)
    client = CanvasClient(cookie_provider=lambda: ("synthetic-session", "synthetic-csrf"))
    assert client.activity_write(method, endpoint, payload) == {}
    assert seen[0].method == method
    assert urlparse(seen[0].url).path == "/api/v1/" + endpoint
    assert parse_qs(seen[0].body or "") == form
    assert "Authorization" not in seen[0].headers


def test_real_sdk_conversation_read_false_query(monkeypatch):
    def send(session, request, **kwargs):
        assert parse_qs(urlparse(request.url).query)["auto_mark_as_read"] == ["false"]
        return _response(request, {"id": 20})
    monkeypatch.setattr(requests.sessions.Session, "send", send)
    assert CanvasClient(cookie_provider=lambda: ("synthetic-session", "synthetic-csrf")).activity_get("conversations/20", params={"auto_mark_as_read": False}) == {"id": 20}


CLI_CASES = [
    (["submissions", "--course", "12345", "--missing"], "get_my_submission_status"),
    (["peer-reviews", "todo", "--course", "12345", "--assignment", "67890"], "get_my_peer_reviews_todo"),
    (["inbox", "list", "--scope", "unread"], "list_conversations"),
    (["inbox", "show", "20"], "get_conversation_details"),
    (["inbox", "send", "--to", "50", "--to", "51", "--subject", "Synthetic", "--body", "Text"], "send_conversation"),
    (["inbox", "reply", "20", "--body", "Text"], "reply_to_conversation"),
    (["inbox", "update", "20", "--state", "archived"], "update_conversation"),
    (["discussion", "post", "12345", "30", "--message", "Text"], "post_discussion_entry"),
    (["discussion", "reply", "12345", "30", "31", "--message", "Text"], "reply_to_discussion_entry"),
    (["assignments", "submissions", "comment", "12345", "67890", "--comment", "Text"], "add_submission_comment"),
    (["course", "structure", "12345"], "get_course_structure"),
    (["course", "module-items", "12345", "60"], "list_module_items"),
    (["course", "module-done", "12345", "60", "61", "--undo"], "mark_module_item_done"),
]


@pytest.mark.parametrize("args,name", CLI_CASES)
def test_first_class_cli_routes_to_shared_tools(monkeypatch, args, name):
    monkeypatch.setattr(bootstrap, "_ensure_auth", lambda: None)
    monkeypatch.setattr(bootstrap, "dispatch_tool_call", lambda called, payload: {"name": called, "args": payload})
    result = CliRunner().invoke(app, ["--output", "json", *args])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["name"] == name


def test_cli_preview_and_confirm_across_invocations(activity_client, monkeypatch):
    monkeypatch.setattr(bootstrap, "_ensure_auth", lambda: None)
    args = ["--output", "json", "inbox", "send", "--to", "50", "--subject", "Synthetic", "--body", "Text"]
    preview = CliRunner().invoke(app, args)
    assert preview.exit_code == 0
    token = json.loads(preview.stdout)["confirmation_token"]
    activity_client.activity_write.assert_not_called()
    confirmed = CliRunner().invoke(app, [*args, "--confirm", token])
    assert confirmed.exit_code == 0
    assert json.loads(confirmed.stdout)["written"] is True
    activity_client.activity_write.assert_called_once()


def test_pretty_write_preview_preserves_raw_html_and_token():
    stream = StringIO()
    payload = {"status": "preview", "confirmation_token": "x" * 80,
               "payload": {"message": "<script>hidden()</script><p>Exact content</p>"}}
    _render(_Pretty(Console(file=stream, width=30, force_terminal=False)), payload, "post_discussion_entry")
    assert "<script>hidden()</script><p>Exact content</p>" in stream.getvalue()
    assert "x" * 80 in stream.getvalue()


def test_mcp_exposes_new_tools_and_confirms_shared_read_behavior(activity_client):
    from fastmcp import Client
    from canvas_mcp.server import mcp
    async def run():
        async with Client(mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert tools["get_course_structure"].annotations.readOnlyHint is True
            assert tools["send_conversation"].annotations.readOnlyHint is False
            assert "confirmation_token" in tools["send_conversation"].inputSchema["properties"]
            result = await client.call_tool("list_conversations", {"limit": 5})
            assert result.data["count"] == 0
    asyncio.run(run())
    activity_client.activity_list.assert_called_once_with("conversations", params={}, limit=5)
