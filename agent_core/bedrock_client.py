from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Optional

from langchain_aws import ChatBedrock
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage


@dataclass
class BedrockConfig:
    model: str = os.environ.get("CLAUDE_MODEL", "anthropic.claude-3-5-sonnet-20240620-v1:0")
    region: Optional[str] = os.environ.get("AWS_REGION")
    aws_access_key_id: Optional[str] = os.environ.get("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = os.environ.get("AWS_SECRET_ACCESS_KEY")


class ClaudeClient:
    """Wrapper that uses Bedrock when credentials exist, otherwise emits demo text."""

    def __init__(self, config: BedrockConfig | None = None) -> None:
        self.config = config or BedrockConfig()
        self.demo_mode = not (
            self.config.region and self.config.aws_access_key_id and self.config.aws_secret_access_key
        )
        self._llm: BaseLanguageModel | None = None
        if not self.demo_mode:
            self._llm = ChatBedrock(
                model_id=self.config.model,
                region_name=self.config.region,
                aws_access_key_id=self.config.aws_access_key_id,
                aws_secret_access_key=self.config.aws_secret_access_key,
            )

    def complete(self, prompt: str) -> str:
        if self.demo_mode or not self._llm:
            demo_id = uuid.uuid4().hex[:6]
            return f"[Claude Demo {demo_id}] {prompt[:260]}"
        response = self._llm.invoke([HumanMessage(content=prompt)])
        return response.content if isinstance(response.content, str) else str(response.content)
