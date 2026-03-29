# Most-Popular-Locations

A backend service that, given a location (city or coordinates) and a radius in miles, returns a ranked list of nearby places based on popularity and ratings.

## Overview

Google Maps rating count is a strong proxy for how many people have visited a place. This service surfaces the most popular and highest-rated places near any location using the Google Places API.

## Features

- Search by city name or coordinates (lat/lng)
- Configurable search radius (in miles)
- Ranking based on number of user ratings (popularity) and average rating
- Optional filtering (by place type, minimum rating, etc.)

## Tech Stack

- **Python**
- **FastAPI**
- **httpx** / **requests** — Google Places API client

## API Usage

### `GET /places`

Returns a ranked list of places near a given location.

| Parameter  | Type    | Required | Description                          |
|------------|---------|----------|--------------------------------------|
| `location` | string  | Yes      | City name or `lat,lng` coordinates   |
| `radius`   | float   | Yes      | Search radius in miles               |
| `type`     | string  | No       | Place type (e.g. `restaurant`, `park`) |
| `min_rating` | float | No       | Minimum average rating (0–5)         |

**Example:**

```
GET /places?location=Austin,TX&radius=5
```

## Ranking Logic

Places are ranked using a weighted score that prioritizes:

1. **Number of ratings** — primary popularity signal
2. **Average rating** — quality signal

## License

MIT
