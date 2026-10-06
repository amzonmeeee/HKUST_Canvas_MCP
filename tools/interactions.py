from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from auth import CanvasAPIError
from tools.activity import resource_id
from tools.common import canvas_client, tool_error
from tools.write_confirmation import claim_confirmation, issue_confirmation


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must contain non-whitespace text")
    return value


def _course_target(args, *names):
    cid = resource_id(args["course_id"])
    return [cid, *(resource_id(args[name], course_id=cid) for name in names)]


def _operation(client, name, args, actor):
    """Build a complete preview using reads; never mutate during preflight."""
    if name in {"post_discussion_entry", "reply_to_discussion_entry"}:
        cid, tid = _course_target(args, "topic_id")
        endpoint = f"courses/{cid}/discussion_topics/{tid}"
        topic = client.activity_get(endpoint)
        if topic.get("locked") or topic.get("locked_for_user") or topic.get("published") is False:
            raise ValueError("This discussion is locked or unpublished.")
        target = {"course_id": cid, "topic_id": tid, "title": topic.get("title")}
        endpoint += "/entries"
        if name == "reply_to_discussion_entry":
            eid = resource_id(args["entry_id"], course_id=cid)
            endpoint += f"/{eid}/replies"
            target["entry_id"] = eid
        payload = {"message": _text(args["message"], "message")}
        return "POST", endpoint, payload, target, False
    if name == "add_submission_comment":
        cid, aid = _course_target(args, "assignment_id")
        assignment = client.activity_get(f"courses/{cid}/assignments/{aid}")
        endpoint = f"courses/{cid}/assignments/{aid}/submissions/self"
        submission = client.activity_get(endpoint)
        payload = {"comment": {"text_comment": _text(args["comment"], "comment")}}
        if args.get("attempt") is not None:
            payload["comment"]["attempt"] = args["attempt"]
        return "PUT", endpoint, payload, {"course_id": cid, "assignment_id": aid,
            "assignment_name": assignment.get("name"), "user_id": "self",
            "submission_id": submission.get("id")}, False
    if name == "send_conversation":
        recipients = [resource_id(value) for value in args["recipients"]]
        if not recipients or len(set(recipients)) != len(recipients):
            raise ValueError("recipients must be a non-empty list of distinct Canvas user IDs")
        payload = {"recipients": recipients, "subject": _text(args["subject"], "subject"),
                   "body": _text(args["body"], "body"), "group_conversation": args.get("group_conversation", False)}
        if args.get("course_id"):
            payload["context_code"] = f"course_{resource_id(args['course_id'])}"
        return "POST", "conversations", payload, {"recipient_ids": recipients,
            "context_code": payload.get("context_code")}, False
    if name in {"reply_to_conversation", "update_conversation"}:
        cid = resource_id(args["conversation_id"])
        endpoint = f"conversations/{cid}"
        conversation = client.activity_get(endpoint, params={"auto_mark_as_read": False})
        target = {"conversation_id": cid, "subject": conversation.get("subject"),
                  "participants": [{"id": person.get("id"), "name": person.get("name")}
                                   for person in conversation.get("participants", [])]}
        if name == "reply_to_conversation":
            audience = conversation.get("audience")
            if not isinstance(audience, list):
                raise ValueError("Canvas did not return this conversation's audience; recipients cannot be verified.")
            recipients = [resource_id(value) for value in audience]
            # A forwarded message's author can appear in participants without
            # being a recipient. Use the authoritative audience, and pin it in
            # the POST rather than allowing Canvas's recipient default to drift.
            if not recipients:
                recipients = [resource_id(actor["id"])]
            target["recipient_ids"] = recipients
            target["participants"] = [person for person in target["participants"]
                                      if str(person["id"]) in recipients]
            return "POST", endpoint + "/add_message", {
                "body": _text(args["body"], "body"), "recipients": recipients,
            }, target, False
        state = args["workflow_state"]
        if state not in {"read", "unread", "archived"}:
            raise ValueError("workflow_state must be read, unread or archived")
        return "PUT", endpoint, {"conversation": {"workflow_state": state}}, target, conversation.get("workflow_state") == state
    if name == "mark_module_item_done":
        cid, mid, iid = _course_target(args, "module_id", "item_id")
        module_endpoint = f"courses/{cid}/modules/{mid}"
        module = client.activity_get(module_endpoint)
        endpoint = f"{module_endpoint}/items/{iid}"
        item = client.activity_get(endpoint, params={"include": ["content_details"]})
        requirement = item.get("completion_requirement") or {}
        if requirement.get("type") != "must_mark_done":
            raise ValueError("This item does not have a must_mark_done completion requirement.")
        if module.get("state") == "locked" or module.get("published") is False or item.get("published") is False or (item.get("content_details") or {}).get("locked_for_user"):
            raise ValueError("This module item is locked or unpublished.")
        done = args.get("done", True)
        return "PUT" if done else "DELETE", endpoint + "/done", {}, {
            "course_id": cid, "module_id": mid, "item_id": iid,
            "module_name": module.get("name"), "title": item.get("title"), "done": done,
        }, requirement.get("completed") is done
    raise ValueError("Unknown interaction")


def _interaction(name: str, args: dict[str, Any]) -> dict[str, Any]:
    client = canvas_client()
    try:
        actor = client.activity_get("users/self")
        method, endpoint, payload, target, noop = _operation(client, name, args, actor)
    except ValueError as exc:
        return tool_error("invalid_argument", str(exc))
    identity = {"user_id": resource_id(actor["id"]), "base_url": client.base_url,
                "profile_path": client.profile_path}
    intent = {"action": name, "identity": identity, "method": method,
              "endpoint": endpoint, "payload": payload, "target": target}
    token = args.get("confirmation_token")
    if noop and not token:
        return {"status": "already_in_requested_state", "action": name, "target": target, "written": False}
    if not token:
        token, expires = issue_confirmation(intent)
        preview = {"status": "preview", "action": name, "target": target, "payload": payload,
                "account": {"user_id": identity["user_id"], "name": actor.get("name")},
                "confirmation_token": token, "expires_at": datetime.fromtimestamp(expires, timezone.utc).isoformat(),
                "written": False,
                "instructions": "Show this exact target and content to the user. Only after explicit approval, repeat the same operation and arguments with confirmation_token. The token expires in 10 minutes and can be used once."}
        if name == "send_conversation":
            preview["warning"] = "Canvas may reuse an existing private conversation with these recipients, in which case it ignores the proposed subject."
        return preview
    error = claim_confirmation(token, intent)
    if error:
        return tool_error("invalid_confirmation", error)
    if noop:
        return {"status": "already_in_requested_state", "action": name, "target": target,
                "written": False, "confirmation_consumed": True}
    try:
        result = client.activity_write(method, endpoint, payload)
    except Exception as exc:
        # Never expose a still-usable token or silently retry an ambiguous send.
        return tool_error("write_failed", str(exc), confirmation_consumed=True,
                          mutation_may_have_succeeded=True,
                          recovery="Check Canvas before previewing a new operation; this confirmation cannot be retried.")
    response = {"status": "accepted", "action": name, "target": target,
                "written": True, "confirmation_consumed": True, "result": result}
    if name == "mark_module_item_done":
        try:
            after = client.activity_get(endpoint.removesuffix("/done"))
            response["verified"] = (after.get("completion_requirement") or {}).get("completed") is target["done"]
        except CanvasAPIError:
            response["verified"] = False
        if not response["verified"]:
            response["warning"] = "Canvas accepted the request, but the completion state could not be verified. Check the module before retrying."
    return response


def post_discussion_entry(args):
    return _interaction("post_discussion_entry", args)


def reply_to_discussion_entry(args):
    return _interaction("reply_to_discussion_entry", args)


def add_submission_comment(args):
    return _interaction("add_submission_comment", args)


def send_conversation(args):
    return _interaction("send_conversation", args)


def reply_to_conversation(args):
    return _interaction("reply_to_conversation", args)


def update_conversation(args):
    return _interaction("update_conversation", args)


def mark_module_item_done(args):
    return _interaction("mark_module_item_done", args)
