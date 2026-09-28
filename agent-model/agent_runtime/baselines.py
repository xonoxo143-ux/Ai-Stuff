from __future__ import annotations

import ast
import operator
import re

from .contracts import (
    CapabilityContext,
    CapabilityOffer,
    CapabilityResult,
    CapabilityRole,
    PublicMessage,
)


class EchoComposer:
    """Test-only stand-in for a future local language spine."""

    name = "echo-composer"
    role = CapabilityRole.COMPOSER
    contract_version = "0.1"

    def offer(self, context: CapabilityContext):
        return None

    def run(self, context: CapabilityContext) -> CapabilityResult:
        useful = [m for m in context.contributions if m.kind == "fact"]
        if useful:
            text = (
                f"{context.user_text} | "
                + " | ".join(str(m.content) for m in useful)
            )
        else:
            text = context.user_text
        return CapabilityResult(
            messages=(
                PublicMessage(
                    "assistant_text",
                    text,
                    self.name,
                ),
            ),
            active_state_updates={"last_user_text": context.user_text},
        )


class ArithmeticCapability:
    name = "arithmetic"
    role = CapabilityRole.CONTRIBUTOR
    contract_version = "0.1"

    _SAFE_BINOPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _SAFE_UNARY = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }

    def offer(
        self,
        context: CapabilityContext,
    ) -> CapabilityOffer | None:
        text = context.user_text.strip()
        if not re.fullmatch(r"[\d\s+\-*/().%]+", text):
            return None
        return CapabilityOffer(
            self.name,
            relevance=1.0,
            estimated_cost=0.05,
            confidence=1.0,
            tags=("exact",),
        )

    def _eval(self, node):
        if isinstance(node, ast.Expression):
            return self._eval(node.body)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
        ):
            return node.value
        if (
            isinstance(node, ast.BinOp)
            and type(node.op) in self._SAFE_BINOPS
        ):
            return self._SAFE_BINOPS[type(node.op)](
                self._eval(node.left),
                self._eval(node.right),
            )
        if (
            isinstance(node, ast.UnaryOp)
            and type(node.op) in self._SAFE_UNARY
        ):
            return self._SAFE_UNARY[type(node.op)](
                self._eval(node.operand)
            )
        raise ValueError("unsupported arithmetic expression")

    def run(self, context: CapabilityContext) -> CapabilityResult:
        tree = ast.parse(context.user_text, mode="eval")
        value = self._eval(tree)
        return CapabilityResult(
            messages=(
                PublicMessage(
                    "fact",
                    f"arithmetic={value}",
                    self.name,
                ),
            ),
            measured_cost=0.01,
        )


class RememberCapability:
    """Test-only semantic-memory writer using an explicit command."""

    name = "remember"
    role = CapabilityRole.CONTRIBUTOR
    contract_version = "0.1"

    def offer(
        self,
        context: CapabilityContext,
    ) -> CapabilityOffer | None:
        if (
            context.user_text.lower().startswith("remember ")
            and "=" in context.user_text
        ):
            return CapabilityOffer(
                self.name,
                relevance=0.95,
                estimated_cost=0.02,
                confidence=1.0,
            )
        return None

    def run(self, context: CapabilityContext) -> CapabilityResult:
        body = context.user_text[len("remember "):]
        key, value = body.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError("empty semantic key")
        return CapabilityResult(
            messages=(
                PublicMessage(
                    "fact",
                    f"remembered {key}",
                    self.name,
                ),
            ),
            semantic_updates={key: value},
            measured_cost=0.005,
        )
