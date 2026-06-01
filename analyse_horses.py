import json
import statistics
from pathlib import Path
from collections import defaultdict


def parse_time_to_seconds(t: str | None) -> float | None:
    """Convert HH:MM:SS.mmm to total seconds."""
    if not t:
        return None
    parts = t.split(":")
    if len(parts) != 3:
        return None
    h, m, s = parts
    return int(h) * 3600 + int(m) * 60 + float(s)


def speed_stats_from_live(live_data: list[dict]) -> dict:
    """Aggregate speed metrics from raw live_data points."""
    speeds = [ld["speed"] for ld in live_data if ld["speed"] > 0]
    if not speeds:
        return {"max_speed": None, "avg_speed": None, "min_speed": None, "std_speed": None}
    return {
        "max_speed": round(max(speeds), 4),
        "avg_speed": round(statistics.mean(speeds), 4),
        "min_speed": round(min(speeds), 4),
        "std_speed": round(statistics.stdev(speeds), 4) if len(speeds) > 1 else 0.0,
    }


def speed_profile_by_segment(live_data: list[dict], segments: list[dict]) -> list[dict]:
    """Per-segment speed summary derived from live_data points (complements intermediate data)."""
    seg_map = defaultdict(list)
    for ld in live_data:
        seg_map[ld["segment"]].append(ld["speed"])

    seg_names = {s["nr"]: s["name"] for s in segments}

    profile = []
    for seg_nr in sorted(seg_map):
        speeds = [s for s in seg_map[seg_nr] if s > 0]
        profile.append({
            "segment_number": seg_nr,
            "segment_name": seg_names.get(seg_nr),
            "max_speed": round(max(speeds), 4) if speeds else None,
            "avg_speed": round(statistics.mean(speeds), 4) if speeds else None,
            "data_points": len(seg_map[seg_nr]),
        })
    return profile


def build_segment_summary(intermediates: list[dict]) -> list[dict]:
    """Clean intermediate data into a per-segment speed summary."""
    return [
        {
            "segment_number": mid["segment_number"],
            "name": mid["name"],
            "rank": mid["rank"],
            "average_speed": mid["average_speed"],
            "top_speed": mid["top_speed"],
            "average_stride_frequency": mid["average_stride_frequency"],
            "average_stride_length": mid["average_stride_length"],
            "distance_traveled": mid["distance_traveled"],
            "section_time_s": parse_time_to_seconds(mid["section_time"]),
            "intermediate_time_s": parse_time_to_seconds(mid["intermediate_time"]),
            "section_time": mid["section_time"],
            "intermediate_time": mid["intermediate_time"],
        }
        for mid in sorted(intermediates, key=lambda m: m["segment_number"])
    ]


def acceleration_profile(live_data: list[dict]) -> list[dict]:
    """Compute per-second acceleration snapshots (speed delta between consecutive points)."""
    if len(live_data) < 2:
        return []
    result = []
    for i in range(1, len(live_data)):
        prev, curr = live_data[i - 1], live_data[i]
        delta_speed = curr["speed"] - prev["speed"]
        result.append({
            "time": curr["time"],
            "speed": round(curr["speed"], 4),
            "delta_speed": round(delta_speed, 4),
            "distance_travelled": curr["distance_travelled"],
            "segment": curr["segment"],
        })
    return result


def analyse_horse_race(horse: dict, race: dict) -> dict:
    live = horse["live_data"]
    intermediates = horse["intermediates"]

    overall_stats = speed_stats_from_live(live)
    seg_profile_live = speed_profile_by_segment(live, race["segments"])
    seg_summary = build_segment_summary(intermediates)
    accel = acceleration_profile(live)

    # Identify peak speed moment
    peak = max(live, key=lambda ld: ld["speed"]) if live else {}

    # Speed at finish: average of last 5 live points
    finish_speeds = [ld["speed"] for ld in live[-5:] if ld["speed"] > 0]
    finish_avg_speed = round(statistics.mean(finish_speeds), 4) if finish_speeds else None

    return {
        "horse_id": horse["horse_id"],
        "horse_name": horse["horse_name"],
        "date": horse["date"],
        "race_number": horse["race_number"],
        "jockey_name": horse["jockey_name"],
        "race_name": race["race_name"],
        "race_length": race["race_length"],
        "official_finish_rank": horse["official_finish_rank"],
        "official_finish_margin": horse["official_finish_margin"],
        "official_finish_time": horse["official_finish_time"],
        "official_finish_time_s": parse_time_to_seconds(horse["official_finish_time"]),
        "speed": {
            "overall": overall_stats,
            "finish_avg_speed": finish_avg_speed,
            "peak": {
                "speed": round(peak.get("speed", 0), 4),
                "time": peak.get("time"),
                "distance_travelled": peak.get("distance_travelled"),
                "segment": peak.get("segment"),
            } if peak else None,
            "by_segment_intermediates": seg_summary,
            "by_segment_live": seg_profile_live,
            "acceleration_profile": accel,
        },
    }


def main():
    base_dir = Path(__file__).parent
    input_path = base_dir / "parsed_xml.json"
    output_path = base_dir / "horse_analysis.json"

    with open(input_path, encoding="utf-8") as f:
        races = json.load(f)

    # Build a race lookup keyed by (date, race_number) for segment info
    race_lookup = {(r["date"], r["race_number"]): r for r in races}

    # Group race entries by horse_id
    by_horse: dict[str, dict] = {}
    for race in races:
        for horse in race["horses"]:
            hid = horse["horse_id"]
            if hid not in by_horse:
                by_horse[hid] = {
                    "horse_id": hid,
                    "horse_name": horse["horse_name"],
                    "races": [],
                }
            race_meta = race_lookup[(horse["date"], horse["race_number"])]
            entry = analyse_horse_race(horse, race_meta)
            by_horse[hid]["races"].append(entry)

    # Sort each horse's race list chronologically
    for entry in by_horse.values():
        entry["races"].sort(key=lambda r: (r["date"], r["race_number"]))

    # Sort horses by name for stable output
    output = sorted(by_horse.values(), key=lambda h: h["horse_name"])

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    total_races = sum(len(h["races"]) for h in output)
    print(f"Done. {len(output)} horses, {total_races} race entries → {output_path}")


if __name__ == "__main__":
    main()
