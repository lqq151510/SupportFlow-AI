"""工单正文清洗。

设计约束（见 PLAN.md「工单清洗与分类」）：

* 工单**同时**保存原文、清洗文本与清洗版本号，清洗规则变更时递增版本。
* 清洗只做结构性处理：去 HTML、去无效空白、去引用行、去重复签名块。
* **绝不改写数值。** 订单编号、时间、金额与商品名必须原样保留 —— 清洗管线中
  没有任何一步触及数字或标点内容，仅处理标签、空白与整行丢弃。

清洗版本历史：

* ``1`` —— 首个版本：HTML 剥离、空白归一、引用行丢弃、签名尾块截断、连续重复行去重。
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

CLEAN_VERSION = 1

_SCRIPT_OR_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_TAG = re.compile(r"<[^>]{0,2000}>")
_QUOTED_LINE = re.compile(r"^\s*(?:>|＞|&gt;)\s?")
_SIGNATURE_DELIMITER = re.compile(r"^\s*(?:-{2,}|_{2,}|={2,}|—{2,}|\*{2,})\s*$")
_SIGNATURE_STARTER = re.compile(
    r"^\s*(?:此致|谢谢|感谢|祝好|顺祝|发自我的|来自我的|"
    r"sent from my|thanks,?|regards,?|best regards)\b",
    re.IGNORECASE,
)
_HORIZONTAL_SPACE = re.compile(r"[ \t\u00a0\u3000]+")
_MULTI_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True, slots=True)
class CleanResult:
    text: str
    version: int


def _strip_scripts_and_comments(raw: str) -> str:
    return _HTML_COMMENT.sub("", _SCRIPT_OR_STYLE.sub("", raw))


def _strip_tags_and_unescape(raw: str) -> str:
    # 标签替换为换行，避免 <p>a</p><p>b</p> 被粘连成 "ab"。
    return html.unescape(_TAG.sub("\n", raw))


def _normalize_newlines(raw: str) -> str:
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def _drop_quoted_lines(raw: str) -> str:
    """丢弃邮件引用行（以 > 或 ＞ 开头的整行）。"""
    kept = [line for line in raw.split("\n") if not _QUOTED_LINE.match(line)]
    return "\n".join(kept)


def _cut_signature_tail(raw: str) -> str:
    """从签名分隔符或常见签名开场白处截断尾块。

    两类信号的可信度不同，因此采用不同的位置阈值：

    * **分隔符行**（``--``、``____``、``====``）是 RFC 3676 定义的签名标记，本身
      就足够强，出现在第 1 行之后就一律截断。
    * **签名开场白**（``此致``、``谢谢``、``Sent from my ...``）是弱信号，正文里也
      可能出现，因此只在文本**后半段**才截断，避免误伤。

    阈值关于「后半段」的判断必须在**删除引用行之前**的原始行数上做 —— 因此管线里
    本步骤排在 ``_drop_quoted_lines`` 之前。否则像「正文 + 引用行 + 签名块」这种短
    工单，删掉引用行后签名分隔符会被挤到前半段而逃过检测（这正是首个版本漏截签名
    块的原因）。
    """
    lines = raw.split("\n")
    weak_threshold = max(1, len(lines) // 2)
    for index in range(1, len(lines)):
        line = lines[index]
        if _SIGNATURE_DELIMITER.match(line):
            return "\n".join(lines[:index])
        if index >= weak_threshold and _SIGNATURE_STARTER.match(line):
            return "\n".join(lines[:index])
    return raw


def _dedupe_consecutive_lines(raw: str) -> str:
    """去掉连续重复的整行，处理"重复签名"被粘贴多次的情况。"""
    kept: list[str] = []
    previous: str | None = None
    for line in raw.split("\n"):
        if line and line == previous:
            continue
        kept.append(line)
        previous = line
    return "\n".join(kept)


def _collapse_whitespace(raw: str) -> str:
    """归一水平空白（含全角空格），统一换行并压缩连续空行。"""
    collapsed = _HORIZONTAL_SPACE.sub(" ", raw)
    stripped = "\n".join(line.strip() for line in collapsed.split("\n"))
    return _MULTI_BLANK_LINES.sub("\n\n", stripped).strip()


def clean_body(raw: str) -> CleanResult:
    """执行清洗管线并返回清洗文本与所用版本。

    顺序有意为之：签名截断必须在**删除引用行之前**执行，否则短工单删掉引用行后
    行数减半，签名分隔符会掉进前半段而逃过检测。
    """
    text = _strip_scripts_and_comments(raw)
    text = _strip_tags_and_unescape(text)
    text = _normalize_newlines(text)
    text = _cut_signature_tail(text)
    text = _drop_quoted_lines(text)
    text = _dedupe_consecutive_lines(text)
    return CleanResult(text=_collapse_whitespace(text), version=CLEAN_VERSION)
