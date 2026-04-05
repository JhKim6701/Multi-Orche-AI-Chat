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

## Orchestration (minimal)
- `POST /orchestration/run`
- `GET /orchestration/runs?chat_thread_id={id}`
- `GET /orchestration/runs/{run_id}`
- `GET /orchestration/runs/{run_id}/stream`
