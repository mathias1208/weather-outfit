import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


ROOT = Path(__file__).parent

CONFIG = json.loads(
    (ROOT / "config.json").read_text(encoding="utf-8")
)

TIMEZONE = ZoneInfo(CONFIG["timezone"])

HEADERS = {
    "User-Agent": (
        "weather-outfit-assistant/1.0 "
        "(personal weather project)"
    )
}


def get_weather(location):
    """
    Download today's hourly weather for one location.
    """

    url = (
        "https://api.met.no/weatherapi/"
        "locationforecast/2.0/compact"
    )

    response = requests.get(
        url,
        params={
            "lat": round(location["latitude"], 4),
            "lon": round(location["longitude"], 4),
        },
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    weather_data = response.json()

    start_time = time.fromisoformat(location["from"])
    end_time = time.fromisoformat(location["to"])

    today = datetime.now(TIMEZONE).date()

    result = []

    for point in weather_data["properties"]["timeseries"]:

        forecast_time = datetime.fromisoformat(
            point["time"].replace("Z", "+00:00")
        ).astimezone(TIMEZONE)

        local_time = forecast_time.time().replace(
            tzinfo=None
        )

        if forecast_time.date() != today:
            continue

        if not start_time <= local_time <= end_time:
            continue

        instant = point["data"]["instant"]["details"]

        next_hour = (
            point["data"]
            .get("next_1_hours", {})
            .get("details", {})
        )

        result.append(
            {
                "place": location["name"],
                "time": forecast_time,
                "temperature": instant[
                    "air_temperature"
                ],
                "wind": instant.get("wind_speed", 0),
                "rain": (
                    next_hour.get(
                        "precipitation_amount", 0
                    )
                    or 0
                ),
            }
        )

    return result


def make_recommendation(
    minimum_temperature,
    maximum_temperature,
    maximum_wind,
    total_rain,
    rainy_hours,
    runs_cold=False,
    allow_dress=True,
):
    """
    Apply transparent rule-based clothing criteria.
    """

    effective_temperature = minimum_temperature

    # Wind adjustment
    if maximum_wind >= 8:
        effective_temperature -= 2
    elif maximum_wind >= 5:
        effective_temperature -= 1

    # Personal cold sensitivity
    if runs_cold:
        effective_temperature -= 2

    # Basic temperature categories
    if effective_temperature < 0:
        top = (
            "Thermal base layer, warm sweater "
            "and winter coat"
        )
        bottom = (
            "Warm trousers with a thermal layer"
        )
        footwear = "Warm waterproof boots"
        extras = [
            "Scarf",
            "Gloves",
            "Warm hat",
        ]

    elif effective_temperature < 5:
        top = "Warm sweater and winter coat"
        bottom = "Full-length trousers"
        footwear = (
            "Closed waterproof shoes or boots"
        )
        extras = [
            "Scarf",
            "Gloves",
        ]

    elif effective_temperature < 10:
        top = (
            "Sweater and medium-weight jacket"
        )
        bottom = "Full-length trousers"
        footwear = "Closed shoes"
        extras = [
            "Light scarf",
        ]

    elif effective_temperature < 15:
        top = (
            "Long-sleeve top or light sweater "
            "with a light jacket"
        )
        bottom = "Full-length trousers"
        footwear = "Closed shoes"
        extras = []

    elif effective_temperature < 20:
        top = (
            "T-shirt or blouse with a removable "
            "light layer"
        )

        if allow_dress:
            bottom = (
                "Light trousers, or a dress or "
                "skirt with an optional layer"
            )
        else:
            bottom = "Light trousers"

        footwear = "Closed shoes or trainers"
        extras = []

    elif effective_temperature < 25:
        top = "T-shirt or light blouse"

        if allow_dress:
            bottom = (
                "Light trousers, skirt or dress"
            )
        else:
            bottom = "Light trousers"

        footwear = "Light shoes or trainers"
        extras = []

    else:
        top = "Breathable short-sleeve top"

        if allow_dress:
            bottom = (
                "Shorts, light skirt or "
                "summer dress"
            )
        else:
            bottom = "Shorts or light trousers"

        footwear = (
            "Sandals or breathable shoes"
        )
        extras = [
            "Sun protection",
        ]

    # Large temperature variation
    if maximum_temperature - minimum_temperature >= 7:
        extras.append(
            "Removable layers for the "
            "temperature change"
        )

    # Rain adjustments
    if total_rain >= 3:
        extras.append("Waterproof jacket")
        footwear = "Water-resistant shoes"

    elif rainy_hours > 0:
        extras.append(
            "Compact umbrella or light rain jacket"
        )

    # Wind adjustments
    if maximum_wind >= 10:
        extras.append(
            "Windproof outer layer. Do not rely "
            "on an umbrella"
        )

    elif maximum_wind >= 7:
        extras.append(
            "Wind-resistant outer layer"
        )

    return {
        "top": top,
        "bottom": bottom,
        "footwear": footwear,
        "extras": extras,
        "effective_temperature": (
            effective_temperature
        ),
    }


def make_html(weather_rows, recommendation):
    """
    Create the phone-friendly webpage.
    """

    now = datetime.now(TIMEZONE)

    minimum_temperature = min(
        row["temperature"] for row in weather_rows
    )

    maximum_temperature = max(
        row["temperature"] for row in weather_rows
    )

    maximum_wind = max(
        row["wind"] for row in weather_rows
    )

    total_rain = sum(
        row["rain"] for row in weather_rows
    )

    extra_items = "".join(
        f"<li>{item}</li>"
        for item in recommendation["extras"]
    )

    if not extra_items:
        extra_items = "<li>No special extras</li>"

    location_cards = []

    location_names = dict.fromkeys(
        row["place"] for row in weather_rows
    )

    for location_name in location_names:

        location_rows = [
            row
            for row in weather_rows
            if row["place"] == location_name
        ]

        location_minimum = min(
            row["temperature"]
            for row in location_rows
        )

        location_maximum = max(
            row["temperature"]
            for row in location_rows
        )

        location_wind = max(
            row["wind"]
            for row in location_rows
        )

        location_rain = sum(
            row["rain"]
            for row in location_rows
        )

        card = f"""
        <section class="card">
            <h2>{location_name}</h2>

            <p>
                <strong>
                    {location_minimum:.0f}
                    to
                    {location_maximum:.0f}°C
                </strong>
            </p>

            <p>
                Wind up to
                {location_wind:.1f} m/s
            </p>

            <p>
                Expected rain:
                {location_rain:.1f} mm
            </p>
        </section>
        """

        location_cards.append(card)

    location_html = "".join(location_cards)

    html = f"""
<!doctype html>

<html lang="en">

<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Today's outfit</title>

    <style>
        body {{
            font-family:
                system-ui,
                -apple-system,
                BlinkMacSystemFont,
                sans-serif;

            max-width: 720px;
            margin: auto;
            padding: 18px;

            background: #f4f7fb;
            color: #172033;
        }}

        h1 {{
            margin-bottom: 4px;
        }}

        section {{
            background: white;
            border-radius: 18px;
            padding: 20px;
            margin: 14px 0;

            box-shadow:
                0 3px 14px
                rgba(23, 32, 51, 0.07);
        }}

        .hero {{
            background:
                linear-gradient(
                    135deg,
                    #dff3ff,
                    #fff0d9
                );
        }}

        .summary {{
            font-size: 1.15rem;
        }}

        .muted {{
            color: #667085;
        }}

        li {{
            margin: 8px 0;
        }}
    </style>
</head>

<body>

    <h1>Today's outfit</h1>

    <div class="muted">
        {now:%A %d %B %Y}
        · updated {now:%H:%M}
    </div>

    <section class="hero">

        <p class="summary">
            <strong>
                {minimum_temperature:.0f}
                to
                {maximum_temperature:.0f}°C
            </strong>

            · wind up to
            {maximum_wind:.1f} m/s

            · rain
            {total_rain:.1f} mm
        </p>

        <h2>Suggested clothes</h2>

        <ul>
            <li>
                <strong>Top:</strong>
                {recommendation["top"]}
            </li>

            <li>
                <strong>Bottom:</strong>
                {recommendation["bottom"]}
            </li>

            <li>
                <strong>Footwear:</strong>
                {recommendation["footwear"]}
            </li>

            {extra_items}
        </ul>

    </section>

    {location_html}

    <p class="muted">
        Rule-based estimate.
        Effective minimum used:
        {recommendation["effective_temperature"]:.0f}°C.
    </p>

</body>

</html>
"""

    return html


def main():
    weather_rows = []

    for location in CONFIG["locations"]:
        location_weather = get_weather(location)
        weather_rows.extend(location_weather)

    if not weather_rows:
        raise RuntimeError(
            "No forecast points were found for "
            "today's configured periods."
        )

    minimum_temperature = min(
        row["temperature"] for row in weather_rows
    )

    maximum_temperature = max(
        row["temperature"] for row in weather_rows
    )

    maximum_wind = max(
        row["wind"] for row in weather_rows
    )

    total_rain = sum(
        row["rain"] for row in weather_rows
    )

    rainy_hours = sum(
        row["rain"] >= 0.1
        for row in weather_rows
    )

    preferences = CONFIG.get(
        "preferences", {}
    )

    recommendation = make_recommendation(
        minimum_temperature=minimum_temperature,
        maximum_temperature=maximum_temperature,
        maximum_wind=maximum_wind,
        total_rain=total_rain,
        rainy_hours=rainy_hours,
        runs_cold=preferences.get(
            "runs_cold", False
        ),
        allow_dress=preferences.get(
            "dress_or_skirt_options", True
        ),
    )

    html = make_html(
        weather_rows,
        recommendation,
    )

    output_file = ROOT / "docs" / "index.html"

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file.write_text(
        html,
        encoding="utf-8",
    )

    print(
        f"Updated {output_file}"
    )


if __name__ == "__main__":
    main()
