from __future__ import annotations

import copy
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.config import settings
from app.errors import AppError


@dataclass(frozen=True)
class ImageProviderInfo:
    provider: str
    available: bool
    missing_settings: tuple[str, ...]


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    mime_type: str
    provider_job_id: str
    metadata: dict[str, object]


class ImageProvider(Protocol):
    name: str

    def generate(
        self,
        source_path: str,
        *,
        prompt: str,
        negative_prompt: str | None,
    ) -> GeneratedImage: ...


def get_image_provider_info() -> ImageProviderInfo:
    provider = settings.image_provider.strip().lower() or "disabled"
    if provider != "comfyui":
        return ImageProviderInfo(provider=provider, available=False, missing_settings=("IMAGE_PROVIDER",))
    required = {
        "COMFYUI_BASE_URL": settings.comfyui_base_url,
        "COMFYUI_WORKFLOW_PATH": settings.comfyui_workflow_path,
        "COMFYUI_INPUT_NODE_ID": settings.comfyui_input_node_id,
        "COMFYUI_POSITIVE_PROMPT_NODE_ID": settings.comfyui_positive_prompt_node_id,
    }
    missing = tuple(name for name, value in required.items() if not str(value).strip())
    if settings.comfyui_workflow_path and not Path(settings.comfyui_workflow_path).is_file():
        missing += ("COMFYUI_WORKFLOW_FILE",)
    return ImageProviderInfo(provider=provider, available=not missing, missing_settings=missing)


class ComfyUIImageProvider:
    name = "comfyui"

    def __init__(self) -> None:
        self.base_url = settings.comfyui_base_url.rstrip("/")
        self.workflow_path = Path(settings.comfyui_workflow_path)

    def _workflow(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.workflow_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AppError(
                "COMFYUI_WORKFLOW_INVALID",
                "无法读取 ComfyUI API-format workflow JSON。",
                status_code=500,
                details={"workflow_file": self.workflow_path.name},
            ) from exc
        if not isinstance(payload, dict):
            raise AppError(
                "COMFYUI_WORKFLOW_INVALID",
                "ComfyUI workflow 顶层必须是节点对象。",
                status_code=500,
            )
        return payload

    @staticmethod
    def _node(workflow: dict[str, Any], node_id: str, input_name: str) -> dict[str, Any]:
        node = workflow.get(node_id)
        inputs = node.get("inputs") if isinstance(node, dict) else None
        if not isinstance(inputs, dict):
            raise AppError(
                "COMFYUI_WORKFLOW_NODE_MISSING",
                "ComfyUI workflow 缺少已配置的输入节点。",
                status_code=500,
                details={"node_id": node_id, "input": input_name},
            )
        return inputs

    def _output_descriptor(self, history: dict[str, Any]) -> dict[str, str] | None:
        outputs = history.get("outputs")
        if not isinstance(outputs, dict):
            return None
        candidates: list[Any] = []
        if settings.comfyui_output_node_id:
            candidates.append(outputs.get(settings.comfyui_output_node_id))
        candidates.extend(value for key, value in outputs.items() if key != settings.comfyui_output_node_id)
        for output in candidates:
            images = output.get("images") if isinstance(output, dict) else None
            if not isinstance(images, list):
                continue
            for image in images:
                if isinstance(image, dict) and image.get("filename"):
                    return {
                        "filename": str(image["filename"]),
                        "subfolder": str(image.get("subfolder") or ""),
                        "type": str(image.get("type") or "output"),
                    }
        return None

    @staticmethod
    def _model_names(workflow: dict[str, Any]) -> list[str]:
        names: list[str] = []
        for node in workflow.values():
            inputs = node.get("inputs") if isinstance(node, dict) else None
            if not isinstance(inputs, dict):
                continue
            for key in ("ckpt_name", "unet_name", "model_name"):
                value = inputs.get(key)
                if isinstance(value, str) and value.strip() and value not in names:
                    names.append(value)
        return names

    def generate(
        self,
        source_path: str,
        *,
        prompt: str,
        negative_prompt: str | None,
    ) -> GeneratedImage:
        workflow = copy.deepcopy(self._workflow())
        model_names = self._model_names(workflow)
        client_id = f"voyaura-{uuid.uuid4()}"
        try:
            with httpx.Client(base_url=self.base_url, timeout=30) as client:
                with open(source_path, "rb") as source:
                    upload = client.post(
                        "/upload/image",
                        files={"image": (Path(source_path).name, source, "application/octet-stream")},
                        data={"overwrite": "false", "type": "input"},
                    )
                upload.raise_for_status()
                uploaded = upload.json()
                uploaded_name = str(uploaded.get("name") or "")
                if not uploaded_name:
                    raise ValueError("upload response did not contain a name")

                self._node(workflow, settings.comfyui_input_node_id, "image")["image"] = uploaded_name
                self._node(workflow, settings.comfyui_positive_prompt_node_id, "text")["text"] = prompt
                if settings.comfyui_negative_prompt_node_id:
                    self._node(
                        workflow,
                        settings.comfyui_negative_prompt_node_id,
                        "text",
                    )["text"] = negative_prompt or ""

                queued = client.post("/prompt", json={"prompt": workflow, "client_id": client_id})
                queued.raise_for_status()
                provider_job_id = str(queued.json().get("prompt_id") or "")
                if not provider_job_id:
                    raise ValueError("prompt response did not contain prompt_id")

                deadline = time.monotonic() + settings.comfyui_timeout_seconds
                history_entry: dict[str, Any] | None = None
                while time.monotonic() < deadline:
                    response = client.get(f"/history/{provider_job_id}")
                    response.raise_for_status()
                    history = response.json()
                    entry = history.get(provider_job_id) if isinstance(history, dict) else None
                    if isinstance(entry, dict):
                        descriptor = self._output_descriptor(entry)
                        if descriptor is not None:
                            history_entry = entry
                            break
                        status = entry.get("status")
                        if isinstance(status, dict) and status.get("status_str") == "error":
                            raise AppError(
                                "COMFYUI_GENERATION_FAILED",
                                "ComfyUI workflow 执行失败，请检查节点日志。",
                                status_code=422,
                            )
                        if isinstance(status, dict) and (
                            status.get("completed") is True
                            or status.get("status_str") == "success"
                        ):
                            raise AppError(
                                "COMFYUI_OUTPUT_MISSING",
                                "ComfyUI 已完成任务，但没有返回图片输出。",
                                status_code=422,
                            )
                    time.sleep(settings.comfyui_poll_interval_seconds)
                if history_entry is None:
                    raise AppError(
                        "COMFYUI_TIMEOUT",
                        "等待 ComfyUI 生成结果超时。",
                        status_code=504,
                        retryable=True,
                    )
                descriptor = self._output_descriptor(history_entry)
                if descriptor is None:
                    raise AppError(
                        "COMFYUI_OUTPUT_MISSING",
                        "ComfyUI 已完成任务，但没有返回图片输出。",
                        status_code=422,
                    )
                output = client.get("/view", params=descriptor)
                output.raise_for_status()
                return GeneratedImage(
                    data=output.content,
                    mime_type=output.headers.get("content-type", "application/octet-stream").split(";", 1)[0],
                    provider_job_id=provider_job_id,
                    metadata={"output": descriptor, "model_names": model_names},
                )
        except AppError:
            raise
        except (httpx.HTTPError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise AppError(
                "COMFYUI_UNAVAILABLE",
                "无法连接或读取 ComfyUI 服务。",
                status_code=503,
                retryable=True,
            ) from exc


def get_image_provider() -> ImageProvider:
    info = get_image_provider_info()
    if not info.available:
        raise AppError(
            "IMAGE_PROVIDER_NOT_CONFIGURED",
            "图片生成 Provider 尚未配置完成。",
            status_code=503,
            details={"provider": info.provider, "missing_settings": list(info.missing_settings)},
        )
    if info.provider == "comfyui":
        return ComfyUIImageProvider()
    raise AppError(
        "IMAGE_PROVIDER_UNSUPPORTED",
        "配置的图片生成 Provider 不受支持。",
        status_code=500,
        details={"provider": info.provider},
    )
