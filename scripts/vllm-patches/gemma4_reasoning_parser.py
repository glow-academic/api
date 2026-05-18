# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project
#
# Hand-ported fix for vLLM PR #40006 (closed un-merged 2026-05-08).
# Adapted to vLLM 0.19.0+nv26.04 — the upstream PR was authored against
# main, which has further-evolved parser scaffolding (is_reasoning_end
# with <|tool_call> handling, start_token_id/tool_call_token_id helpers)
# that our base lacks. We port only the no-start-token streaming
# fallback, which is the root fix for the symptom (#39885): on Gemma 4
# MoE A4B (and on our gemma-4-E4B-it under the custom chat template),
# the model often does NOT emit <|channel> at the start of reasoning.
# BaseThinkingReasoningParser.extract_reasoning_streaming then falls
# through to ``DeltaMessage(content=delta_text)`` and the entire
# reasoning channel leaks into output_text.delta events on the
# streaming Responses API path.
#
# Drop this file once NVIDIA ships an image with PR #40006 (or an
# equivalent fix) included.

from collections.abc import Sequence
from typing import TYPE_CHECKING

from vllm.entrypoints.openai.engine.protocol import DeltaMessage
from vllm.reasoning.basic_parsers import BaseThinkingReasoningParser
from vllm.tokenizers import TokenizerLike

if TYPE_CHECKING:
    from vllm.entrypoints.openai.chat_completion.protocol import (
        ChatCompletionRequest,
    )
    from vllm.entrypoints.openai.responses.protocol import ResponsesRequest

# Role label that Gemma4 emits at the start of the thinking channel.
# The model generates: <|channel>thought\n...reasoning...<channel|>
# This prefix must be stripped to expose only the actual reasoning content.
_THOUGHT_PREFIX = "thought\n"


class Gemma4ReasoningParser(BaseThinkingReasoningParser):
    """
    Reasoning parser for Google Gemma4 thinking models.

    Gemma4 uses <|channel>...<channel|> tokens to delimit reasoning/thinking
    content. Thinking is activated via ``enable_thinking=True`` in the chat
    template kwargs, which injects <|think|> (token 98).

    Output pattern when thinking is enabled::

        <|channel>thought
        ...chain of thought reasoning...<channel|>
        Final answer text here.

    The ``thought\\n`` role label is a structural artefact (analogous to
    ``user\\n`` in ``<|turn>user\\n...``). This parser strips it so
    downstream consumers see only the actual reasoning text.
    """

    def __init__(self, tokenizer: TokenizerLike, *args, **kwargs):
        super().__init__(tokenizer, *args, **kwargs)
        self._reasoning_text: str = ""
        self._prefix_stripped: bool = False
        # Token id for <|tool_call>. Used to detect when the model went
        # straight to tool calls without ever opening the reasoning
        # channel — in that case the no-start-token fallback should
        # route as content, not reasoning, so the tool parser picks it up.
        vocab = tokenizer.get_vocab() if hasattr(tokenizer, "get_vocab") else {}
        self.tool_call_token_id: int | None = vocab.get("<|tool_call>")

    def is_reasoning_end(self, input_ids):
        # Extend the base implementation: any <|tool_call> token also
        # ends reasoning. Without this, serving.py never flips
        # reasoning_ended when the model goes straight to tool calls
        # (no <|channel> ever opened, no <channel|> ever emitted), and
        # the tool parser never sees the stream.
        if self.tool_call_token_id is not None and self.tool_call_token_id in input_ids:
            return True
        return super().is_reasoning_end(input_ids)

    @property
    def start_token(self) -> str:
        return "<|channel>"

    @property
    def end_token(self) -> str:
        return "<channel|>"

    # ------------------------------------------------------------------
    # Non-streaming path
    # ------------------------------------------------------------------

    def extract_reasoning(
        self,
        model_output: str,
        request: "ChatCompletionRequest | ResponsesRequest",
    ) -> tuple[str | None, str | None]:
        if self.start_token not in model_output and self.end_token not in model_output:
            return None, model_output
        reasoning, content = super().extract_reasoning(model_output, request)
        if reasoning is not None:
            reasoning = _strip_thought_label(reasoning)
        return reasoning, content

    # ------------------------------------------------------------------
    # Streaming path — no-start-token fallback (PR #40006 backport)
    # ------------------------------------------------------------------

    def _apply_prefix_stripping(
        self, result: DeltaMessage | None
    ) -> DeltaMessage | None:
        """Strip the ``thought\\n`` role label from streaming reasoning deltas.

        Accumulates reasoning text in ``_reasoning_text`` across calls and
        suppresses/trims the leading ``thought\\n`` label, which may arrive
        split across multiple deltas. Returns the (possibly modified)
        DeltaMessage, or None when the entire delta was consumed by the
        prefix and there's nothing to emit yet.
        """
        if result is None:
            return None
        if result.reasoning is None:
            return result

        self._reasoning_text += result.reasoning

        if self._prefix_stripped:
            return result

        # Case 1: accumulated text starts with the full prefix — strip it.
        if self._reasoning_text.startswith(_THOUGHT_PREFIX):
            prefix_len = len(_THOUGHT_PREFIX)
            prev_reasoning_len = len(self._reasoning_text) - len(result.reasoning)
            if prev_reasoning_len >= prefix_len:
                self._prefix_stripped = True
                return result
            chars_of_prefix_in_delta = prefix_len - prev_reasoning_len
            stripped = result.reasoning[chars_of_prefix_in_delta:]
            if stripped:
                self._prefix_stripped = True
                result.reasoning = stripped
                return result
            if len(self._reasoning_text) >= prefix_len:
                self._prefix_stripped = True
            return None

        # Case 2: accumulated text is a strict prefix of _THOUGHT_PREFIX
        # (e.g. only "thou" so far). Buffer — can't tell yet if it diverges.
        if _THOUGHT_PREFIX.startswith(self._reasoning_text):
            return None

        # Case 3: text diverged from thought prefix. Re-emit everything
        # buffered so far to avoid data loss.
        self._prefix_stripped = True
        result.reasoning = self._reasoning_text
        return result

    def extract_reasoning_streaming(
        self,
        previous_text: str,
        current_text: str,
        delta_text: str,
        previous_token_ids: Sequence[int],
        current_token_ids: Sequence[int],
        delta_token_ids: Sequence[int],
    ) -> DeltaMessage | None:
        """Stream-extract reasoning, with a fallback for missing start tokens.

        On Gemma 4 MoE (A4B) — and observed on our gemma-4-E4B-it serve
        with the custom tool chat template — the model often does not
        emit ``<|channel>`` at the start of the reasoning channel
        (typically when the previous message is a tool response and the
        model continues the same turn). The base
        ``BaseThinkingReasoningParser.extract_reasoning_streaming`` then
        falls through to ``DeltaMessage(content=delta_text)`` and every
        reasoning token leaks into ``response.output_text.delta`` —
        which is the visible symptom (#39885) of unstripped ``<channel|>``
        markers in the chat panel.

        When neither ``<|channel>`` (``start_token_id``) appears in
        ``previous_token_ids`` nor ``delta_token_ids``, mirror the sync
        ``extract_reasoning`` fallback: assume the reasoning phase and
        route each delta as ``reasoning`` until ``<channel|>``
        (``end_token_id``) is observed.
        """
        # Skip single special tokens — same guard the base class uses.
        if len(delta_token_ids) == 1 and (
            delta_token_ids[0] in [self.start_token_id, self.end_token_id]
        ):
            return None

        start_seen = (
            self.start_token_id in previous_token_ids
            or self.start_token_id in delta_token_ids
        )

        if not start_seen:
            # No <|channel> emitted yet — fall back to the
            # "assume reasoning until end token" strategy. This matches
            # what extract_reasoning (non-streaming) already does, and
            # is what PR #40006 ports into the streaming path.
            if self.end_token_id in previous_token_ids:
                # Already past <channel|> — pure content from here.
                return DeltaMessage(content=delta_text)
            if self.end_token_id in delta_token_ids:
                end_index = delta_text.find(self.end_token)
                if end_index == -1:
                    # Token present but text empty (e.g. rendered as
                    # empty string with skip_special_tokens=True) —
                    # nothing to emit, just mark the phase transition.
                    return None
                reasoning_part = delta_text[:end_index]
                content_part = delta_text[end_index + len(self.end_token) :]
                result = DeltaMessage(
                    reasoning=reasoning_part if reasoning_part else None,
                    content=content_part if content_part else None,
                )
                return self._apply_prefix_stripping(result)
            # If the model emitted a <|tool_call> token with no prior
            # <|channel>, it skipped reasoning entirely — route as
            # content so the tool parser handles the subsequent stream.
            if self.tool_call_token_id is not None and (
                self.tool_call_token_id in previous_token_ids
                or self.tool_call_token_id in delta_token_ids
            ):
                return DeltaMessage(content=delta_text)
            # Still inside (assumed) reasoning with no start token seen.
            return self._apply_prefix_stripping(
                DeltaMessage(reasoning=delta_text)
            )

        # Normal path: <|channel> was emitted — delegate to the base
        # parser and apply our prefix-stripping wrapper on top.
        base_result = super().extract_reasoning_streaming(
            previous_text,
            current_text,
            delta_text,
            previous_token_ids,
            current_token_ids,
            delta_token_ids,
        )
        return self._apply_prefix_stripping(base_result)


def _strip_thought_label(text: str) -> str:
    """Remove the ``thought\\n`` role label from the beginning of text."""
    if text.startswith(_THOUGHT_PREFIX):
        return text[len(_THOUGHT_PREFIX) :]
    return text
