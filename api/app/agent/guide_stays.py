"""Turn explicitly quoted visit times into attributable scheduling suggestions."""

import re
from statistics import median
from unicodedata import normalize
from urllib.parse import urlsplit

CHINESE_DIGITS = {digit: index for index, digit in enumerate("〇一二三四五六七八九")}
CHINESE_DIGITS.update({"零": 0, "两": 2})
NUMBER = r"(?:\d{1,3}(?:\.\d{1,2})?|[零〇一二两三四五六七八九十]{1,3})"
HOUR = r"(?:个?小时|钟头)"
UNIT = rf"(?:{HOUR}|分钟)"
RANGE = re.compile(rf"(?P<low>{NUMBER})\s*(?P<low_unit>{UNIT})?\s*[-–—~～至到]\s*(?P<high>{NUMBER})\s*(?P<unit>{UNIT})")
HOURS_AND_MINUTES = re.compile(rf"(?P<hours>{NUMBER})\s*{HOUR}\s*(?P<minutes>{NUMBER})\s*分钟")
HALF_HOURS = re.compile(rf"(?:(?P<hours>{NUMBER})\s*个?(?:半小时|小时半)|(?P<half>半小时))")
SINGLE = re.compile(rf"(?P<number>{NUMBER})\s*(?P<unit>{UNIT})")
VISIT_CONTEXT = re.compile(
    r"(?:建议\s*(?:游玩|参观|停留|预留)|游玩|游览|参观|停留|逛|玩)"
    r"(?:时长|时间|了)?\s*[:：]?\s*(?:大约|大概|约|至少)?\s*"
)


def minutes_for(number: str, unit: str) -> int:
    if re.fullmatch(r"\d+(?:\.\d+)?", number):
        value = float(number)
    elif "十" in number:
        tens, units = number.split("十", maxsplit=1)
        value = CHINESE_DIGITS.get(tens or "一", 0) * 10 + CHINESE_DIGITS.get(units, 0)
    else:
        value = CHINESE_DIGITS.get(number, 0)
    return round(value * 60 if unit != "分钟" else value)


def parse_visit_duration(excerpt: str) -> tuple[int, int]:
    text = normalize("NFKC", excerpt).strip()
    snippets = [(text[match.end():], True) for match in VISIT_CONTEXT.finditer(text)]
    snippets.append((text, False))
    for snippet, in_context in snippets:
        for pattern in (RANGE, HOURS_AND_MINUTES, HALF_HOURS, SINGLE):
            match = pattern.match(snippet)
            if not match:
                continue
            if not in_context and not re.fullmatch(r"\s*(?:左右|上下)?[。.]?", text[match.end():]):
                continue
            fields = match.groupdict()
            if pattern is RANGE:
                low = minutes_for(fields["low"], fields["low_unit"] or fields["unit"])
                high = minutes_for(fields["high"], fields["unit"])
            elif pattern is HOURS_AND_MINUTES:
                low = high = minutes_for(fields["hours"], "小时") + minutes_for(fields["minutes"], "分钟")
            elif pattern is HALF_HOURS:
                low = high = 30 + minutes_for(fields["hours"] or "零", "小时")
            else:
                low = high = minutes_for(fields["number"], fields["unit"])
            if not 15 <= low <= high <= 480:
                raise ValueError("游玩时长须为 15 到 480 分钟，范围请从小到大填写。")
            return low, high
    raise ValueError("请粘贴含明确游玩时长的摘录，例如“建议游玩 2–3 小时”。")


def guide_source(url: str | None) -> str:
    if url is None:
        return "用户提供的攻略摘录"
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https" or not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", host)
            or parsed.username is not None or parsed.password is not None
            or any(char.isspace() or ord(char) < 32 for char in url)
        ):
            raise ValueError
    except ValueError as error:
        raise ValueError("攻略链接请输入完整的 HTTPS 网址。") from error
    if host in {"xhslink.com", "www.xhslink.com"} or host == "xiaohongshu.com" or host.endswith(".xiaohongshu.com"):
        return "小红书 · 用户提供摘录"
    return "用户提供的攻略摘录"


def attraction_key(name: str) -> str:
    return "".join(char for char in normalize("NFKC", name).casefold() if char.isalnum())


def apply_stay_guides(request: dict, candidates: list[dict]) -> tuple[list[dict], list[str]]:
    if not request.get("guide_references"):
        return candidates, []
    suggestions: dict[str, list[dict]] = {}
    unmatched = []
    seen = set()
    for reference in request["guide_references"]:
        key = attraction_key(reference["place_name"])
        matches = [candidate for candidate in candidates if key and attraction_key(candidate["name"]) == key]
        if len(matches) != 1:
            unmatched.append(reference["place_name"])
            continue
        place_id = matches[0]["id"]
        low, high = parse_visit_duration(reference["excerpt"])
        url = reference.get("source_url")
        fingerprint = (place_id, url or (low, high))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        suggestions.setdefault(place_id, []).append({
            "from_minutes": low,
            "to_minutes": high,
            "source": guide_source(url),
            "source_url": url,
        })
    updated = []
    for candidate in candidates:
        references = suggestions.get(candidate["id"])
        if not references:
            updated.append(candidate)
            continue
        typical = median([(entry["from_minutes"] + entry["to_minutes"]) / 2 for entry in references])
        updated.append({
            **candidate,
            "stay_minutes": int(typical + 0.5),
            "stay_source": "guide_reference",
            "stay_references": references,
        })
    return updated, list(dict.fromkeys(unmatched))
