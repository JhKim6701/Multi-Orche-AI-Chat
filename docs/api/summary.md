# API Summary

## System
- `GET /system/health`
- `GET /system/hardware`
- `GET /system/ollama`

## Projects/Chats
- `POST /projects`
- `GET /projects`
- `PATCH /projects/{project_id}`
- `DELETE /projects/{project_id}`
- `POST /chats`
- `GET /chats?project_id={id}`
- `GET /chats/{chat_id}`
- `DELETE /chats/{chat_id}`

## Messages (core MVP path)
- `GET /messages?chat_thread_id={id}`
- `POST /messages`
- `POST /messages/execute`
- `GET /messages/stream?chat_thread_id={id}&model_name={name}&prompt={text}`

## Assets
- `POST /assets/upload`
- `GET /assets/chat/{chat_id}`
- `GET /assets/{asset_id}`
- `GET /assets/{asset_id}/download`

## Models
- `GET /models`
- `GET /models/enabled`
- `POST /models/sync`
- `POST /models/pull`
- `DELETE /models/{model_name}`
- `PATCH /models/{model_id}/toggle`
- `PATCH /models/{model_id}/sort`

## Orchestration
- `POST /orchestration/run` (rule-based steps + final response persist)
- `GET /orchestration/runs?chat_thread_id={id}`
- `GET /orchestration/runs/{run_id}` (run metadata + ordered steps + final message)
- `GET /orchestration/runs/{run_id}/stream`


## Segments
- `GET /segments?chat_thread_id={id}`
- `GET /segments/{segment_id}`
- `POST /segments/detect?chat_thread_id={id}&new_text={text}`
- `POST /segments/switch?chat_thread_id={id}`
- `POST /segments/branch?chat_thread_id={id}`
