# Command table

See the [README](../README.md) for install, auth, and the usual flow. `canvas --help` is the source of truth for flags.

## Commands

| Command | Tool |
|---|---|
| `canvas today` | `get_today` |
| `canvas courses` | `list_courses` |
| `canvas resolve QUERY` | `resolve_course` |
| `canvas course overview ID` | `get_course_overview` |
| `canvas course syllabus ID` | `get_course_syllabus` |
| `canvas course context ID` | `get_course_context_snapshot` |
| `canvas assignments list ID` | `list_course_assignments` |
| `canvas assignments show COURSE ASSIGNMENT` | `get_assignment_details` |
| `canvas assignments rubric COURSE ASSIGNMENT` | `get_assignment_rubric` |
| `canvas assignments groups ID` | `list_assignment_groups` |
| `canvas course submissions ID` | `list_course_submissions` |
| `canvas assignments submissions install COURSE ASSIGNMENT` | `install_assignment_submission_files` |
| `canvas assignments submissions preview COURSE ASSIGNMENT` | `preview_assignment_submission` |
| `canvas assignments submissions confirm TOKEN` | `confirm_assignment_submission` |
| `canvas assignments submissions scheduled` | `list_scheduled_submissions` |
| `canvas assignments submissions status JOB` | `get_scheduled_submission` |
| `canvas assignments submissions cancel JOB` | `cancel_scheduled_submission` |
| `canvas course grades ID` | `get_course_grade_summary` |
| `canvas course modules ID` | `list_modules` |
| `canvas discussion list ID` | `list_discussion_topics` |
| `canvas discussion show COURSE TOPIC` | `get_discussion_entries` |
| `canvas course pages ID` | `list_course_pages` |
| `canvas course page COURSE SLUG_OR_ID` | `canvas_get_page` |
| `canvas course tabs ID` | `list_course_tabs` |
| `canvas course tab COURSE TAB` | `get_course_tab` |
| `canvas files list ID` | `list_course_files` |
| `canvas files download COURSE FILE` | `download_course_file` |
| `canvas files folders ID` | `list_course_folders` |
| `canvas announcements --course ID` | `list_announcements` |
| `canvas todo` | `list_todo_items` |
| `canvas submissions [--course ID] [--missing] [--status STATUS]` | `get_my_submission_status` |
| `canvas peer-reviews todo [--course ID] [--assignment ID]` | `get_my_peer_reviews_todo` |
| `canvas inbox list [--scope unread]` | `list_conversations` |
| `canvas inbox show ID` | `get_conversation_details` |
| `canvas inbox send --to ID --subject TEXT --body TEXT` | `send_conversation` |
| `canvas inbox reply ID --body TEXT` | `reply_to_conversation` |
| `canvas inbox update ID --state read\|unread\|archived` | `update_conversation` |
| `canvas discussion post COURSE TOPIC --message TEXT` | `post_discussion_entry` |
| `canvas discussion reply COURSE TOPIC ENTRY --message TEXT` | `reply_to_discussion_entry` |
| `canvas assignments submissions comment COURSE ASSIGNMENT --comment TEXT` | `add_submission_comment` |
| `canvas course structure ID` | `get_course_structure` |
| `canvas course module-items COURSE MODULE` | `list_module_items` |
| `canvas course module-done COURSE MODULE ITEM [--undo]` | `mark_module_item_done` |
| `canvas course people ID` | `list_course_people` |
| `canvas url URL` | `resolve_canvas_url` |

`canvas_get_page` is wiki pages only. Use `canvas url` when the link type is unknown. Non-self submission queries need extra Canvas permissions.

The new write commands preview without `--confirm`; repeat identical arguments with `--confirm TOKEN` after approving the exact preview. The MCP equivalents take `confirmation_token`. Tokens expire after 10 minutes and cannot be reused. Read-only Inbox commands do not mark messages read. `submissions` is a status report, while `assignments submissions` contains the submission/comment workflows; `assignments submissions status JOB` still inspects a scheduled job.

Scan/output limits are independent. Raise scan limits if `partial`/`warnings` report incomplete discovery; increasing only `--limit` does not scan additional assignments. Course structure includes accessible module items; it is not an inventory of unmoduled resources. See [README](../README.md) for status definitions, peer-review discovery and confirmation storage.
