"""Markets supported in v1 and their Google Ads geo IDs (DataForSEO `location_code`)."""

LOCATIONS = {
    "US": 2840, "GB": 2826, "CA": 2124, "AU": 2036, "IN": 2356, "IE": 2372, "NZ": 2554,
    "DE": 2276, "AT": 2040, "CH": 2756, "FR": 2250, "ES": 2724, "IT": 2380, "NL": 2528,
    "SE": 2752, "DK": 2208, "NO": 2578, "PL": 2616, "JP": 2392, "SG": 2702,
}


def location_code(country: str) -> int:
    code = LOCATIONS.get(country.strip().upper())
    if not code:
        raise ValueError(f"Unsupported market {country!r}. Supported: {', '.join(sorted(LOCATIONS))}")
    return code
