import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET


def float_or_none(value: str | None) -> float | None:
    if value is None or value == "NaN":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def int_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_file(xml_path: Path) -> dict | None:
    match = re.search(r'_(\d+)_[A-Z]+_(\d{4}-\d{2}-\d{2})_', xml_path.name)
    if not match:
        print(f"Skipping {xml_path.name}: filename doesn't match expected pattern")
        return None

    race_number = int(match.group(1))
    date = match.group(2)

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # --- Venue ---
    venue_el = root.find("Venue")
    venue = None
    if venue_el is not None:
        venue = {
            "name": venue_el.get("Name"),
            "abbreviation": venue_el.get("Abbrevation"),
        }

    # --- Segments ---
    segments = []
    for seg in root.findall(".//Segment"):
        segments.append({
            "nr": int(seg.get("Nr")),
            "name": seg.get("Name"),
            "race_distance": float(seg.get("RaceDistance")),
            "segment_length": float(seg.get("SegmentLength")),
            "left_x": float(seg.get("LeftX")),
            "left_y": float(seg.get("LeftY")),
            "right_x": float(seg.get("RightX")),
            "right_y": float(seg.get("RightY")),
        })

    # --- Dynamic Rail ---
    dynamic_rail = []
    for dr in root.findall(".//DynamicRailPosition"):
        dynamic_rail.append({
            "nr": int(dr.get("Nr")),
            "x": float(dr.get("X")),
            "y": float(dr.get("Y")),
        })

    # --- Horses ---
    horses = []
    for horse in root.findall(".//Horse"):
        # Skip virtual LeaderMiddle entry
        if horse.get("Id") == "LeaderMiddle":
            continue

        jockey_el = horse.find("Jockey")
        finish_time_el = horse.find("OfficialFinishTime")

        # --- Intermediates ---
        intermediates = []
        for mid in horse.findall(".//IntermediateData"):
            section_time_el = mid.find("SectionTime")
            intermediate_time_el = mid.find("IntermediateTime")
            intermediates.append({
                "segment_number": int(mid.get("SegmentNumber")),
                "name": mid.get("Name"),
                "rank": int(mid.get("Rank")),
                "average_speed": float(mid.get("AverageSpeed")),
                "top_speed": float(mid.get("TopSpeed")),
                "average_distance_to_rail": float(mid.get("AverageDistanceToRail")),
                "average_stride_frequency": float(mid.get("AverageStrideFrequency")),
                "average_stride_length": float(mid.get("AverageStrideLength")),
                "distance_traveled": float_or_none(mid.get("DistanceTraveled")),
                "section_time": section_time_el.get("Time") if section_time_el is not None else None,
                "intermediate_time": intermediate_time_el.get("Time") if intermediate_time_el is not None else None,
            })

        # --- Live Data ---
        live_data = []
        for ld in horse.findall(".//LiveData"):
            live_data.append({
                "time": ld.get("Time"),
                "x": float(ld.get("X")),
                "y": float(ld.get("Y")),
                "longitude": float(ld.get("Longitude")),
                "latitude": float(ld.get("Latitude")),
                "speed": float(ld.get("Speed")),
                "course": float_or_none(ld.get("Course")),
                "rank": int(ld.get("Rank")),
                "segment": int(ld.get("Segment")),
                "distance_travelled": float(ld.get("DistanceTravelled")),
                "distance_to_rail": float(ld.get("DistanceToRail")),
                "stride_rate": float(ld.get("StrideRate")),
                "stride_length": float(ld.get("StrideLength")),
            })

        horses.append({
            "date": date,
            "race_number": race_number,
            "horse_id": horse.get("ExternalId"),
            "horse_name": horse.get("Name"),
            "jockey_name": jockey_el.get("Name") if jockey_el is not None else None,
            "state": horse.get("State"),
            "draw_number": int(horse.get("DrawNumber")),
            "lane": int_or_none(horse.get("Lane")),
            "distance_travelled": float_or_none(horse.get("DistanceTravelled")),
            "official_finish_rank": int(horse.get("OfficialFinishRank")),
            "official_finish_margin": float(horse.get("OfficialFinishMargin")),
            "official_finish_time": finish_time_el.get("Time") if finish_time_el is not None else None,
            "intermediates": intermediates,
            "live_data": live_data,
        })

    return {
        "date": date,
        "race_number": race_number,
        "race_name": root.get("Name"),
        "race_length": int(root.get("RaceLength")),
        "start_time": root.get("StartTime"),
        "finish_time": root.get("FinishTime"),
        "weather": root.get("Weather"),
        "rail_position": root.get("RailPosition"),
        "track_condition": root.get("TrackCondition"),
        "venue": venue,
        "segments": segments,
        "dynamic_rail": dynamic_rail,
        "horses": horses,
    }


def main():
    base_dir = Path(__file__).parent
    races = []

    xml_files = sorted(base_dir.rglob("*.xml"))
    if not xml_files:
        print(f"No XML files found under {base_dir}")
        return

    for xml_path in xml_files:
        print(f"Parsing {xml_path.relative_to(base_dir)} ...")
        race = parse_file(xml_path)
        if race:
            races.append(race)

    races.sort(key=lambda r: (r["date"], r["race_number"]))

    output_path = base_dir / "parsed_xml.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(races, f, indent=2, ensure_ascii=False)

    total_horses = sum(len(r["horses"]) for r in races)
    total_live = sum(len(h["live_data"]) for r in races for h in r["horses"])
    print(f"\nDone. {len(races)} races, {total_horses} horses, {total_live:,} live data points → {output_path}")


if __name__ == "__main__":
    main()
