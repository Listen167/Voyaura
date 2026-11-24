"""Small deterministic day planner; estimates never become verified traffic facts."""

import math
from datetime import date, timedelta


def minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def distance(a: dict, b: dict) -> float:
    # Used only for candidate grouping, never labelled as real road distance/time.
    lat = math.radians((a["latitude"] + b["latitude"]) / 2)
    x = (a["longitude"] - b["longitude"]) * math.cos(lat)
    y = a["latitude"] - b["latitude"]
    return math.hypot(x, y)


def group_candidates(
    candidates: list[dict], count: int, pace: str, stops_per_day: int | None = None,
    *, day_minutes: int | None = None,
) -> list[list[dict]]:
    if not candidates:
        return [[] for _ in range(count)]
    quota = stops_per_day
    if quota is None and day_minutes is None:
        quota = 2 if pace == "relaxed" else 3
    selected = sorted(candidates, key=lambda x: not x["must_visit"])
    if quota is not None and day_minutes is None:
        selected = selected[:max(quota * count, sum(c["must_visit"] for c in candidates))]
    # Farthest-first real candidate seeds, followed by capacity-aware nearest assignment.
    seeds = [selected[0]]
    while len(seeds) < min(count, len(selected)):
        remaining = [x for x in selected if x not in seeds]
        seeds.append(max(remaining, key=lambda x: min(distance(x, s) for s in seeds)))
    groups = [[s] for s in seeds] + [[] for _ in range(count - len(seeds))]
    loads = [seed["stay_minutes"] for seed in seeds] if day_minutes is not None else []
    for candidate in selected:
        if candidate in seeds:
            continue
        if day_minutes is None:
            index = min(range(len(seeds)), key=lambda i: (
                quota is not None and len(groups[i]) >= quota,
                distance(candidate, seeds[i]) + len(groups[i]) * 0.02,
            ))
        else:
            index = min(range(len(seeds)), key=lambda i: (
                quota is not None and len(groups[i]) >= quota,
                max(0, loads[i] + candidate["stay_minutes"] + 30 - day_minutes),
                distance(candidate, seeds[i]) + 0.00025 * loads[i],
            ))
            loads[index] += candidate["stay_minutes"] + 30
        groups[index].append(candidate)
    ordered = []
    for group in groups:
        if not group:
            ordered.append([])
            continue
        first = next((c for c in group if c["must_visit"]), group[0]) if day_minutes is not None else group[0]
        path = [first]
        remaining = [c for c in group if c is not first]
        while remaining:
            nxt = min(remaining, key=lambda x: (
                day_minutes is not None and not x["must_visit"], distance(path[-1], x),
            ))
            path.append(nxt)
            remaining.remove(nxt)
        ordered.append(path)
    return ordered


def flexible_sightseeing(request: dict) -> bool:
    return bool(request.get("allow_external") and not request.get("candidates"))


def usable_day_minutes(request: dict) -> int:
    full_window = minutes(request["daily_end"]) - minutes(request["daily_start"])
    rest = request.get("rest_minutes")
    if rest is None:
        rest = 60 if request["pace"] == "relaxed" else 30
    return full_window - min(rest, full_window // 4)


def groups_for_plan(request: dict, candidates: list[dict]) -> list[list[dict]]:
    return group_candidates(
        candidates, request["days"], request["pace"], request.get("stops_per_day"),
        day_minutes=usable_day_minutes(request) if flexible_sightseeing(request) else None,
    )


def assemble_days(request: dict, groups: list[list[dict]], legs: list[dict]) -> list[dict]:
    edge_map = {(x["from_id"], x["to_id"]): x for x in legs}
    days = []
    flexible = flexible_sightseeing(request)
    latest = minutes(request["daily_start"]) + usable_day_minutes(request) if flexible else None
    quota = request.get("stops_per_day")
    for index, group in enumerate(groups):
        now = minutes(request["daily_start"])
        stops, day_legs = [], []
        timing_known = True
        for candidate in group:
            leg = None
            arrival = now
            if stops:
                previous_id = stops[-1]["candidate_id"]
                leg = edge_map.get((previous_id, candidate["id"])) or {
                    "from_id": previous_id,
                    "to_id": candidate["id"],
                    "duration_minutes": None,
                    "distance_meters": None,
                    "source": "unknown",
                    "queried_at": None,
                }
                arrival += leg["duration_minutes"] if leg["duration_minutes"] is not None else 30
            if candidate["opening_start"]:
                arrival = max(arrival, minutes(candidate["opening_start"]))
            departure = arrival + candidate["stay_minutes"]
            if latest is not None and not candidate["must_visit"]:
                if quota is not None and len(stops) >= quota:
                    continue
                closes = minutes(candidate["opening_end"]) if candidate["opening_end"] else latest
                if departure > min(closes, latest):
                    continue
            if leg is not None:
                day_legs.append(leg)
                timing_known &= leg["duration_minutes"] is not None
            now = departure
            stops.append(
                {
                    "candidate_id": candidate["id"],
                    "name": candidate["name"],
                    "longitude": candidate["longitude"],
                    "latitude": candidate["latitude"],
                    "arrival": clock(arrival),
                    "departure": clock(now),
                    "stay_minutes": candidate["stay_minutes"],
                    "stay_source": candidate.get("stay_source"),
                    "stay_references": candidate.get("stay_references", []),
                    "timing_basis": (
                        "user_schedule"
                        if not stops
                        else "provider"
                        if timing_known
                        else "planning_buffer"
                    ),
                    "source": candidate["source"],
                }
            )
        days.append(
            {
                "day": index + 1,
                "date": (
                    date.fromisoformat(request["start_date"]) + timedelta(days=index)
                ).isoformat(),
                "start": request["daily_start"],
                "end": clock(now),
                "stops": stops,
                "legs": day_legs,
                "total_minutes": now - minutes(request["daily_start"]),
            }
        )
    return days


def validate_plan(request: dict, candidates: list[dict], days: list[dict]) -> dict:
    """Independent checks read produced timeline and evidence, not planner success flags."""
    checks: list[dict] = []
    unknowns: list[str] = []
    by_id = {c["id"]: c for c in candidates}
    visited = [s["candidate_id"] for day in days for s in day["stops"]]

    def check(code: str, ok: bool, message: str) -> None:
        checks.append({"code": code, "status": "pass" if ok else "fail", "message": message})

    check("unique_stops", len(set(visited)) == len(visited), "每个地点只安排一次。")
    required = {c["id"] for c in candidates if c["must_visit"]}
    check("must_visit", required.issubset(set(visited)), "用户标记的必去地点须全部安排。")
    check(
        "daily_end",
        all(minutes(d["end"]) <= minutes(request["daily_end"]) for d in days),
        "每日活动须在用户结束时间之前完成。",
    )
    quota = request.get("stops_per_day")
    if quota is not None:
        check("daily_stop_limit", all(len(day["stops"]) <= quota for day in days),
              f"每日景点最多 {quota} 个；如需保留更多必去地点，请增加天数或调整上限。")
    opening_ok = True
    time_ok = True
    for day in days:
        for i, stop in enumerate(day["stops"]):
            item = by_id[stop["candidate_id"]]
            if item["opening_start"] and item["opening_end"]:
                opening_ok &= minutes(stop["arrival"]) >= minutes(
                    item["opening_start"]
                ) and minutes(stop["departure"]) <= minutes(item["opening_end"])
            else:
                unknowns.append(f"{item['name']}的具体日期开放时间未核实。")
            time_ok &= minutes(stop["departure"]) - minutes(stop["arrival"]) == item["stay_minutes"]
            if i:
                leg = day["legs"][i - 1]
                expected = leg["duration_minutes"]
                if expected is None:
                    unknowns.append(
                        f"{day['stops'][i - 1]['name']}至{stop['name']}的交通时间未知；时间线暂留30分钟规划缓冲。"
                    )
                else:
                    time_ok &= (
                        minutes(stop["arrival"])
                        >= minutes(day["stops"][i - 1]["departure"]) + expected
                    )
    check("opening_windows", opening_ok, "已提供的开放窗口不得与停留时间冲突。")
    check("time_propagation", time_ok, "每日时间线包含停留及已有交通证据。")
    selected = [by_id[i] for i in visited]
    known_cost = round(sum(c["cost_yuan"] or 0 for c in selected), 2)
    missing_cost = sum(c["cost_yuan"] is None for c in selected)
    if missing_cost:
        unknowns.append(f"{missing_cost}个地点的费用未知，不能声称预算已通过。")
    if request["budget_yuan"] is not None:
        check(
            "budget_lower_bound",
            known_cost <= request["budget_yuan"],
            "已知地点费用不得超过总预算。",
        )
    unknowns.append("住宿、餐饮、往返交通及预约余量未纳入本版已验证范围。")
    if any(c["source"] == "user_provided" for c in selected):
        unknowns.append("用户提供地点及开放／费用信息尚未获得独立地图或官方核验。")
    unplaced = [c["name"] for c in candidates if c["id"] not in visited]
    failed = any(c["status"] == "fail" for c in checks)
    status = "conflict" if failed else "conditional" if selected else "information_missing"
    # Even live routes cannot verify date-specific opening, reservations, meals or full budget.
    # This deliberately never upgrades a partial city itinerary to a fully validated trip.
    return {
        "verification_status": status,
        "checks": checks,
        "unknowns": list(dict.fromkeys(unknowns)),
        "known_cost_yuan": known_cost,
        "unknown_cost_count": missing_cost,
        "unplaced_candidates": unplaced,
    }
