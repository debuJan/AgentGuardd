"""
Configuration models for the AI Agent Reliability & Security Platform.

These models are the developer-facing "contract": they describe an agent,
its tools, its permissions/policies, and its test cases. Nothing here is
domain-specific — the same models describe an e-commerce refund agent,
a banking agent, or the existing RAG QA agent.
"""
from __future__ import annotations

import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------
# External-agent auth allowlist
# ---------------------------------------------------------------------
# `auth_header_env` lets a config name an environment variable whose value
# is sent as a bearer token to the external endpoint. To prevent an API
# caller from exfiltrating arbitrary server secrets (e.g. DATABASE_URL),
# the name must appear in this operator-controlled allowlist.
_AUTH_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def allowed_auth_env_vars() -> set:
    """Env-var names the operator permits for external-agent auth headers.

    Configured via the ``AGENTGUARD_ALLOWED_AUTH_ENV`` environment variable
    (comma-separated). Empty by default: the feature is opt-in.
    """
    raw = os.environ.get("AGENTGUARD_ALLOWED_AUTH_ENV", "")
    return {name.strip() for name in raw.split(",") if name.strip()}


# ---------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------
class ToolParameter(BaseModel):
    name: str
    type: str = Field(description="json-schema-like type: string, integer, number, boolean, object, array")
    required: bool = True
    description: Optional[str] = None


class ToolSchema(BaseModel):
    """Describes a tool the agent may call, independent of its implementation."""
    name: str
    description: str
    parameters: List[ToolParameter] = Field(default_factory=list)
    is_sensitive: bool = Field(
        default=False,
        description="True for tools that perform irreversible/financial/destructive actions "
                    "(e.g. issue_refund, transfer_funds). Used by the security engine.",
    )

    @field_validator("name")
    @classmethod
    def name_must_be_identifier(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError(f"Tool name '{v}' must be a valid identifier (snake_case).")
        return v


# ---------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------
class Permissions(BaseModel):
    allowed_tools: List[str] = Field(default_factory=list)
    blocked_tools: List[str] = Field(default_factory=list)

    @field_validator("blocked_tools")
    @classmethod
    def no_overlap(cls, blocked: List[str], info) -> List[str]:
        allowed = info.data.get("allowed_tools", [])
        overlap = set(allowed) & set(blocked)
        if overlap:
            raise ValueError(f"Tools cannot be both allowed and blocked: {overlap}")
        return blocked


# ---------------------------------------------------------------------
# Policies (business rules)
# ---------------------------------------------------------------------
class PolicyType(str, Enum):
    TOOL_ORDER = "tool_order"          # e.g. must call check_refund before issue_refund
    PRECONDITION = "precondition"      # e.g. refund only if eligible
    CUSTOM = "custom"                  # evaluated via a named rule function


class Policy(BaseModel):
    id: str
    description: str
    type: PolicyType
    # e.g. {"before": "issue_refund", "after": "check_refund"} for TOOL_ORDER
    # e.g. {"tool": "issue_refund", "requires_prior_tool_result": {"eligible": True}} for PRECONDITION
    rule: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------
# Agent configuration
# ---------------------------------------------------------------------
class LLMProviderConfig(BaseModel):
    provider: str = "groq"
    model: str = "llama-3.1-8b-instant"
    temperature: float = 0.1
    max_tokens: int = 1024


class AgentConfig(BaseModel):
    name: str
    description: str
    system_prompt: Optional[str] = None
    tools: List[ToolSchema] = Field(default_factory=list)
    permissions: Permissions = Field(default_factory=Permissions)
    policies: List[Policy] = Field(default_factory=list)
    # Destinations considered safe by the data-exfiltration security check
    # (email domains / webhook hostnames). Empty = no trust list.
    trusted_email_domains: List[str] = Field(default_factory=list)
    # Cap for distinct tools per run (ExcessiveToolVarietyCheck). None = default.
    max_distinct_tools: Optional[int] = None
    llm: LLMProviderConfig = Field(default_factory=LLMProviderConfig)

    # External agent execution configuration
    execution_type: str = Field(
        default="internal",
        description="Execution mode: 'internal' uses AgentGuard's runner; 'external' invokes a configured external agent.",
    )
    adapter_type: str = Field(
        default="http",
        description="External integration adapter type. Currently supported: 'http'.",
    )
    endpoint_url: Optional[str] = Field(
        default=None,
        description="HTTP(S) endpoint used when execution_type is 'external'. "
                    "Private/loopback/metadata addresses are rejected unless "
                    "the operator sets AGENTGUARD_ALLOW_PRIVATE_ENDPOINTS.",
    )
    auth_header_env: Optional[str] = Field(
        default=None,
        description="Environment variable containing the external agent authentication token. "
                    "The name must be allowlisted by the operator via AGENTGUARD_ALLOWED_AUTH_ENV.",
    )
    timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=300,
        description="Maximum time to wait for an external agent response.",
    )

    def tool_names(self) -> List[str]:
        return [t.name for t in self.tools]

    @field_validator("tools")
    @classmethod
    def unique_tool_names(cls, tools: List[ToolSchema]) -> List[ToolSchema]:
        names = [t.name for t in tools]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate tool names in agent config.")
        return tools

    @field_validator("execution_type")
    @classmethod
    def execution_type_must_be_known(cls, v: str) -> str:
        # Reject unknown modes loudly instead of silently falling back to
        # internal execution (which would evaluate the wrong agent).
        if v not in ("internal", "external"):
            raise ValueError(
                f"Unknown execution_type {v!r}; expected 'internal' or 'external'."
            )
        return v

    @field_validator("endpoint_url")
    @classmethod
    def endpoint_url_must_be_http(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        scheme = v.split("://", 1)[0].lower()
        if scheme not in ("http", "https"):
            raise ValueError(
                "endpoint_url must use the http or https scheme."
            )
        return v

    @field_validator("auth_header_env")
    @classmethod
    def auth_header_env_must_be_allowlisted(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not _AUTH_ENV_NAME_PATTERN.match(v):
            raise ValueError(
                "auth_header_env must be a valid environment variable name."
            )
        if v not in allowed_auth_env_vars():
            raise ValueError(
                f"auth_header_env {v!r} is not permitted by this server. "
                "The operator must add it to AGENTGUARD_ALLOWED_AUTH_ENV."
            )
        return v


# ---------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------
class ExpectedToolCall(BaseModel):
    tool: str
    arguments: Optional[Dict[str, Any]] = None
    order: Optional[int] = None  # 1-based position in the expected sequence


class SecurityExpectation(BaseModel):
    should_detect_prompt_injection: bool = False
    should_block_unauthorized_tool: bool = False
    forbidden_tools: List[str] = Field(default_factory=list)


class TestCaseCategory(str, Enum):
    FUNCTIONAL = "functional"
    SECURITY = "security"
    RELIABILITY = "reliability"


def resolve_allowed_tools(agent_config: Any) -> List[str]:
    """Return the agent's allowed tool names.

    Reads the canonical ``AgentConfig.permissions.allowed_tools`` first.
    Falls back to a legacy top-level ``allowed_tools`` attribute so older
    config shapes keep working.
    """
    permissions = getattr(agent_config, "permissions", None)
    if permissions is not None:
        return list(getattr(permissions, "allowed_tools", None) or [])
    return list(getattr(agent_config, "allowed_tools", None) or [])


def resolve_blocked_tools(agent_config: Any) -> List[str]:
    """Return the agent's blocked tool names.

    Reads the canonical ``AgentConfig.permissions.blocked_tools`` first.
    Falls back to a legacy top-level ``blocked_tools`` attribute so older
    config shapes keep working.
    """
    permissions = getattr(agent_config, "permissions", None)
    if permissions is not None:
        return list(getattr(permissions, "blocked_tools", None) or [])
    return list(getattr(agent_config, "blocked_tools", None) or [])


class TestCase(BaseModel):
    id: str
    # Human-readable label shown in the dashboard library. Optional so test
    # cases constructed before the library existed keep working.
    title: Optional[str] = None
    agent_name: str
    category: TestCaseCategory = TestCaseCategory.FUNCTIONAL
    user_input: str
    expected_tool_calls: List[ExpectedToolCall] = Field(default_factory=list)
    expected_outcome: Optional[str] = None
    security_expectation: SecurityExpectation = Field(default_factory=SecurityExpectation)
    max_tool_calls: Optional[int] = None
    max_latency_ms: Optional[int] = None
