"""Geographic resolution for the daily planner.

Turns a free-text customer name from the weekly-planning workbook into a
destination, real road distance from the depot, and coordinates:

  * The client directory (app/data/clients_directory.json) is authoritative for
    delivery site coordinates and the legacy depot distance metadata.
  * Nominatim is used only as a fallback when a directory entry has no
    coordinates.

Customers not in the directory fall back to resolving a Tunisian locality from
the name (city tokens + a supplemental table seeded from the real mappings in
app/data/synthetic_daily_planning.py) and geocoding that. If geocoding is
unreachable, geocode() returns None and the caller marks the delivery
unassigned. Travel times themselves are computed by the builder from distance,
not here.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GEOCODE_CACHE = DATA_DIR / "geocode_cache.json"
# Cached OSRM road-distance matrices, keyed by a hash of the rounded coordinate
# set, so repeat builds of the same day don't re-hit the routing server.
ROAD_MATRIX_CACHE = DATA_DIR / "road_matrix_cache.json"
# Authoritative customer directory (destination + real road km from the depot),
# generated from the frontend Clients page data (frontend/data/coficabData.js).
CLIENTS_DIRECTORY = DATA_DIR / "clients_directory.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Public OSRM demo server — same one the frontend map uses for road geometry.
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving/"
USER_AGENT = "coficab-daily-planner/1.0 (logistics planning)"

# COFICAB Sidi Hassine depot — geocoded once, kept as a stable fallback.
DEPOT_QUERY = "Sidi Hassine, Tunis, Tunisia"
DEPOT_FALLBACK: Tuple[float, float] = (36.7708, 10.1103)

# Factor that turns straight-line km into approximate road km (used by the
# builder for client↔client legs that have no directory distance).
ROAD_WINDING_FACTOR = 1.30

# Customers that are foreign sites / exports — not domestic truck deliveries.
FOREIGN_TOKENS = (
    "EGYPT", "BADR CITY", "PORT SAID", "6 OCT", "BRAZIL", "BRASIL", "MEXICO",
    "MX S.DE", "MX S.DE R.L", "HONDURAS", "POLAND", "POLSKA", "SP.Z.O.O",
    "FRANCE", "S.A.S", "PORTUGAL", "ROMANIA", "S.R.L", "PLOIESTI", "TURKEY",
    "BURSA", "GEMLIK", "MUDANYA", "SHANG", "TIANJIN", "CHINA", "MAROC",
    "KENITRA", "JELESNIA", "EASTERN EUROPE", "JUGOISTOCNA",
    "SPOL.S.R.O", "GMB",
)

# Supplemental customer→locality facts for names whose city is not derivable
# from the name and not present in the synthetic dataset. Localities are real;
# coordinates are still looked up online.
SUPPLEMENTAL_CITY = {
    "YURA CORPORATION TUNISIA": "Kairouan, Tunisia",
    "SEBN": "El Fejja, Manouba, Tunisia",
    "SEBN SUMITOMO": "El Fejja, Manouba, Tunisia",
    "SE BORDNETZE EL FEJJA": "El Fejja, Manouba, Tunisia",
    "COFAT TUNIS": "Mghira, Ben Arous, Tunisia",
    "COFAT MATEUR": "Mateur, Bizerte, Tunisia",
    "COFAT KAIROUAN": "Kairouan, Tunisia",
    "COFAT AUTOMATIVE SYSTEMS": "Mghira, Ben Arous, Tunisia",
    "SCHULTE ZAGHOUANE": "Zaghouan, Tunisia",
    "SCHULTE AUTOMOTIVE TUNISIA": "Bouarada, Siliana, Tunisia",
    "LEONI WIRING SYSTEMS TUNISIA NORD": "Mateur, Bizerte, Tunisia",
    "LEONI WIRING SYSTEMS TUNISIA SUD": "Sousse, Tunisia",
    "LEONI SOUSSE": "Sousse, Tunisia",
    "LEONI MENZEL HAYET": "Menzel Hayet, Monastir, Tunisia",
    "MEDITERRANEAN ELECTRIC WIRING": "Nadhour, Zaghouan, Tunisia",
    "A C T ASSEMBLAGE CABLE TUNISIE": "Soliman, Nabeul, Tunisia",
    "APTIV SERVICES TUNISIA": "Mjez El Bab, Beja, Tunisia",
    "WEWIRE HAMMAMET TUNISIA": "Hammamet, Nabeul, Tunisia",
    "YAZAKI TUNISIA": "El Agba, Tunis, Tunisia",
    "YAZAKI AUTOMOTIVE PRODUCTS TUNISIA": "Bizerte, Tunisia",
    "SEWS TN": "Monastir, Tunisia",
    "SEWS TN SARL": "Monastir, Tunisia",
    "PROD-ELEC": "Kalaa Kebira, Sousse, Tunisia",
    "ELECTROCONTACT TUNISIE": "Ksar Hellal, Monastir, Tunisia",
    "I.C.EM": "Beni Khalled, Nabeul, Tunisia",
    "AMPHENOL TUNISIE": "El Fahs, Zaghouan, Tunisia",
    "AEC WIRING TECHNOLOGY": "Mghira, Ben Arous, Tunisia",
    "CABLISYS TUNISIE": "Sousse, Tunisia",
    "ERA CONTACTS TUNISIA": "Bizerte, Tunisia",
    "KAB-LEM TUNISIA": "Bizerte, Tunisia",
    "KAB-LEM": "Bizerte, Tunisia",
    "KROMBERG & SCHUBERT TUNISIE": "Beja, Tunisia",
    "KROMBERG & SCHUBERT CABLE&WIRE": "Beja, Tunisia",
    "CHAKIRA CABLE": "Grombalia, Nabeul, Tunisia",
    "COELEC TUNISIA": "El Agba, Tunis, Tunisia",
    "DIS DRAXLMAIER INDUST SOLUTION": "Siliana, Tunisia",
    "REFLEXALLEN": "Hammam Zriba, Zaghouan, Tunisia",
    "METS MANUFAC ELECTRO.DE SOUSSE": "Sousse, Tunisia",
    "TTE INTERNATIONAL": "Bizerte, Tunisia",
    "TTE INTERNATIONAL / FUJIKURA": "Bizerte, Tunisia",
    "JETTY": "Hammam Lif, Ben Arous, Tunisia",
    "COFICAB MED": "Mjez El Bab, Beja, Tunisia",
    "PLASTEKNIQUE": "Mghira, Ben Arous, Tunisia",
}

# Authoritative EXACT site coordinates per client (lat, lon, locality label),
# keyed by the normalised customer name (same _norm() form the resolver uses).
# These are the real factory/warehouse locations — used verbatim so two clients
# in the same town are not collapsed onto a single city-centroid point, and so
# the optimiser's distance/time reflect each site. Alias spellings are included
# so workbook variants resolve to the same site.
CLIENT_COORDS: Dict[str, Tuple[float, float, str]] = {
    "AEC WIRING TECHNOLOGY":              (36.72422, 10.18543, "Mghira"),
    "AMPHENOL TUNISIE":                   (36.38624,  9.91497, "El Fahs"),
    "APTIV SERVICES TUNISIA":             (36.63183,  9.61988, "Medjez el Bab"),
    "CABLISYS TUNISIE":                   (35.90557, 10.53103, "Akouda / Sousse"),
    "COELEC TUNISIA":                     (36.78757, 10.07286, "Agba / Tunis"),
    "COFAT MATEUR":                       (37.04846,  9.68369, "Mateur"),
    "COFAT TUNIS":                        (36.76191, 10.11649, "Tunis"),
    "COFICAB MED":                        (36.63330,  9.61888, "Medjez el Bab"),
    "DIS DRAXLMAIER INDUST SOLUTION":     (36.09985,  9.35774, "Siliana"),
    "DIS DRAXLMAIER INDUST. SOLUTION":    (36.09985,  9.35774, "Siliana"),
    "DIS DRAXLMAIER":                     (36.09985,  9.35774, "Siliana"),
    "ELECTROCONTACT TUNISIE":             (35.65602, 10.88034, "Ksar Hellal"),
    "ERA CONTACTS TUNISIA":               (37.17707,  9.96126, "El Azib / Bizerte"),
    "I.C.EM":                             (36.63280, 10.56735, "Bni Khalled"),
    "KAB-LEM TUNISIA":                    (37.21750,  9.93854, "Menzel Jemil / Bizerte"),
    "KAB-LEM":                            (37.21750,  9.93854, "Menzel Jemil / Bizerte"),
    "KROMBERG & SCHUBERT TUNISIE":        (36.73376,  9.20496, "Beja"),
    "KROMBERG & SCHUBERT CABLE&WIRE":     (36.73376,  9.20496, "Beja"),
    "LECTRIC":                            (36.38624,  9.91497, "El Fahs"),
    "LEONI MENZEL HAYET":                 (35.56120, 10.61933, "Manzel Hayet"),
    "LEONI SOUSSE":                       (35.75726, 10.60193, "Messadine / Sousse"),
    "LEONI WIRING SYSTEMS TUNISIA NORD":  (37.04683,  9.68219, "Mateur"),
    "LEONI WIRING SYSTEMS TUNISIA SUD":   (35.75726, 10.60193, "Messadine / Sousse"),
    "MEDITERRANEAN ELECTRIC WIRING":      (36.11489, 10.06021, "Nadhour"),
    "METS MANUFAC ELECTRO.DE SOUSSE":     (35.85031, 10.60712, "Sousse"),
    "REFLEXALLEN":                        (36.35762, 10.20660, "Hammam Zriba"),
    "PROD-ELEC":                          (35.86943, 10.54224, "Kaala Kebira"),
    "SCHULTE AUTOMOTIVE TUNISIA":         (36.35393,  9.63358, "Bouarada"),
    "SCHULTE AUTOMOTIVE TUN ZAGHOUAN":    (36.55923, 10.07932, "Jebel Oust / Zaghouan"),
    "SCHULTE ZAGHOUANE":                  (36.55923, 10.07932, "Jebel Oust / Zaghouan"),
    "SEBN":                               (36.57104,  8.79706, "Jendouba"),
    "SEBN SUMITOMO":                      (36.57104,  8.79706, "Jendouba"),
    "SE BORDNETZE EL FEJJA":              (36.67612,  9.96586, "El Fejja"),
    "SEWS TN":                            (35.72389, 10.74911, "Monastir"),
    "STE S.C.E.E.T":                      (36.38411,  9.91080, "El Fahs"),
    "TTE INTERNATIONAL":                  (37.19885,  9.95498, "El Azib / Bizerte"),
    "TTE INTERNATIONAL / FUJIKURA":       (37.19885,  9.95498, "El Azib / Bizerte"),
    "WEWIRE HAMMAMET TUNISIA":            (36.41160, 10.52893, "Hammamet"),
    "YAZAKI AUTOMOTIVE PRODUCTS TUNISIA": (37.17305,  9.96520, "Bizerte"),
    "YAZAKI GAFSA":                       (34.41551,  8.73951, "Gafsa"),
    "YURA CORPORATION TUNISIA":           (35.69373, 10.11254, "Kairouan"),
    "COFAT KAIROUAN":                     (35.81832, 10.15357, "Kairouan (Sbikha)"),
    "A C T ASSEMBLAGE CABLE TUNISIE":     (36.69253, 10.45185, "Soliman"),
    "JETTY":                              (36.70427, 10.38539, "Borj Cedria / Hammam Lif"),
    "PERPLASTIC TN":                      (36.70883, 10.17373, "Mghira"),
    "ADC SOUSSE":                         (35.83748, 10.59457, "Sousse"),
    "CHAKIRA":                            (36.75711, 10.11703, "Tunis"),
    "CHAKIRA CABLE":                      (36.75711, 10.11703, "Tunis"),
}

# Client-directory destination labels → proper Tunisian city geocoding queries.
# The directory's distances (km) are authoritative, but its embedded coordinates
# are unreliable, so coordinates are looked up online from the (normalised) city.
DESTINATION_QUERY = {
    "MGHIRA": "Mghira, Ben Arous, Tunisia",
    "FAHS": "El Fahs, Zaghouan, Tunisia",
    "MJEZ EL BEB": "Mejez el Bab, Beja, Tunisia",
    "SOUSSE": "Sousse, Tunisia",
    "SOUSE": "Sousse, Tunisia",
    "AGBA": "El Agba, Tunis, Tunisia",
    "MATEUR": "Mateur, Bizerte, Tunisia",
    "TN": "Tunis, Tunisia",
    "TUNIS": "Tunis, Tunisia",
    "SELIANA": "Siliana, Tunisia",
    "KSAR HLEL": "Ksar Hellal, Monastir, Tunisia",
    "BIZERTE": "Bizerte, Tunisia",
    "BNI KHALLED": "Beni Khalled, Nabeul, Tunisia",
    "BEJA": "Beja, Tunisia",
    "MANZEL HAYET": "Menzel Hayet, Monastir, Tunisia",
    "NADOUR": "Nadhour, Zaghouan, Tunisia",
    "SIDI ABDELHMID": "Sidi Abdelhamid, Sousse, Tunisia",
    "HAMMEM ZRIBA": "Hammam Zriba, Zaghouan, Tunisia",
    "KAALA KOBRA": "Kalaa Kebira, Sousse, Tunisia",
    "ZAGHOUEN": "Zaghouan, Tunisia",
    "JENDOUBA": "Jendouba, Tunisia",
    "FEJJA": "El Fejja, Manouba, Tunisia",
    "MOUNASTIR": "Monastir, Tunisia",
    "HAMMMET": "Hammamet, Nabeul, Tunisia",
    "GAFSSA": "Gafsa, Tunisia",
    "KAIRAOUEN": "Kairouan, Tunisia",
    "SLIMANE": "Soliman, Nabeul, Tunisia",
    "HAMMEM LIF": "Hammam Lif, Ben Arous, Tunisia",
    "BOUARADA": "Bouarada, Siliana, Tunisia",
}

# Tunisian locality tokens that may appear directly inside a customer name.
CITY_TOKENS = {
    "MATEUR": "Mateur, Bizerte, Tunisia",
    "KAIROUAN": "Kairouan, Tunisia",
    "ZAGHOUAN": "Zaghouan, Tunisia",
    "ZAGHOUANE": "Zaghouan, Tunisia",
    "HAMMAMET": "Hammamet, Nabeul, Tunisia",
    "SOUSSE": "Sousse, Tunisia",
    "MENZEL HAYET": "Menzel Hayet, Monastir, Tunisia",
    "EL FEJJA": "El Fejja, Manouba, Tunisia",
    "FEJJA": "El Fejja, Manouba, Tunisia",
    "BIZERTE": "Bizerte, Tunisia",
    "MONASTIR": "Monastir, Tunisia",
    "TUNIS": "Tunis, Tunisia",
    "GROMBALIA": "Grombalia, Nabeul, Tunisia",
    "NABEUL": "Nabeul, Tunisia",
}

_LEGAL_SUFFIXES = (
    "SARL", "S.A.R.L", "S.A.S", "S.R.L", "SUARL", "SRL", "LTD", "GMBH",
    "S.DE R.L", "SPA", "S.A", "SA", "SAS", "S.A.R.L.", "S.P.A",
)


def _strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    )


def _norm(name: str) -> str:
    """Uppercase, de-accent, collapse whitespace; drop parentheticals + suffix."""
    text = _strip_accents(str(name or "")).upper().strip()
    # Drop parenthetical groups, e.g. "SEBN (SUMITOMO)" -> "SEBN".
    while "(" in text and ")" in text:
        start, end = text.index("("), text.index(")")
        if start < end:
            text = (text[:start] + " " + text[end + 1:]).strip()
        else:
            break
    text = " ".join(text.split())
    for suffix in sorted(_LEGAL_SUFFIXES, key=len, reverse=True):
        if text.endswith(" " + suffix):
            text = text[: -(len(suffix) + 1)].strip()
            break
    return text


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = rlat2 - rlat1, rlon2 - rlon1
    h = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2.0 * 6371.0 * math.asin(math.sqrt(max(0.0, h)))


class GeoService:
    """Caching geocoder + road-matrix client for the daily planner."""

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout
        self._lock = threading.Lock()
        self._geocode_cache: Dict[str, Optional[List[float]]] = self._load(GEOCODE_CACHE)
        self._road_cache: Dict[str, List[List[float]]] = self._load(ROAD_MATRIX_CACHE)
        self._last_nominatim = 0.0
        self._city_from_synthetic = self._load_synthetic_cities()
        self._client_directory = self._load_client_directory()

    # ----------------------------------------------------------------- caches
    @staticmethod
    def _load(path: Path) -> Dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self, path: Path, data: Dict) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
        except OSError as exc:
            log.warning("GeoService: could not persist cache %s — %s", path.name, exc)

    @staticmethod
    def _load_client_directory() -> Dict[str, Dict]:
        """Index the authoritative client directory by normalised name."""
        try:
            raw = json.loads(CLIENTS_DIRECTORY.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        return {_norm(e["customer"]): e for e in raw if e.get("customer")}

    @staticmethod
    def _load_synthetic_cities() -> Dict[str, str]:
        """Reuse the real customer→locality facts already in the repo."""
        try:
            from app.data.synthetic_daily_planning import MOCK_TRANSPORTS
        except Exception:
            return {}
        cities: Dict[str, str] = {}
        for row in MOCK_TRANSPORTS:
            loc = str(row.get("end_location") or "").strip()
            client = _norm(row.get("client"))
            if client and loc and loc.upper() not in {"TN", ""}:
                cities.setdefault(client, f"{loc}, Tunisia")
        return cities

    # Workbook spellings that differ from the client-directory entry name.
    # Maps a normalised workbook name → the directory customer it refers to.
    _DIRECTORY_ALIASES = {
        "SCHULTE ZAGHOUANE": "SCHULTE AUTOMOTIVE TUN ZAGHOUAN",
        "CHAKIRA CABLE": "CHAKIRA",
    }

    # ----------------------------------------------------------- resolution
    def lookup_client(self, customer: str) -> Optional[Dict]:
        """Exact (normalised) match against the authoritative client directory,
        with a small alias table for known workbook spelling variants."""
        norm = _norm(customer)
        entry = self._client_directory.get(norm)
        if entry is None and norm in self._DIRECTORY_ALIASES:
            entry = self._client_directory.get(_norm(self._DIRECTORY_ALIASES[norm]))
        return entry

    def locate(self, customer: str) -> Optional[Dict]:
        """Resolve a customer to coordinates + depot distance.

        Returns one of:
          {"lat", "lon", "km", "label", "source"}  — located
          {"is_export": True}                        — foreign / export site
          None                                       — could not be located

        The client directory is authoritative: when a customer is listed there
        we use its stored delivery-site coordinates. Online geocoding is only a
        fallback for missing directory coordinates or customers not listed there.
        """
        # Exact per-client site coordinates take precedence over everything: a
        # client's real factory location, never the shared city centroid, so the
        # map and the client↔client legs use the true site. The authoritative
        # depot↔client road distance (km) from the client directory is still
        # used when available — haversine from the depot would over-estimate
        # long hauls and wrongly drop far deliveries.
        exact = CLIENT_COORDS.get(_norm(customer))
        if exact:
            lat, lon, label = exact
            entry = self.lookup_client(customer)
            return {
                "lat": lat, "lon": lon,
                "km": entry.get("km") if entry else None,
                "label": label, "source": "exact-client",
            }

        entry = self.lookup_client(customer)
        if entry:
            dest = entry["destination"]
            coords = None
            if entry.get("lat") is not None and entry.get("lon") is not None:
                coords = (float(entry["lat"]), float(entry["lon"]))
            if not coords:
                query = DESTINATION_QUERY.get(_strip_accents(dest).upper().strip(), f"{dest}, Tunisia")
                coords = self.geocode(query)
            if coords:
                return {
                    "lat": coords[0], "lon": coords[1],
                    "km": entry.get("km"), "label": dest,
                    "source": "directory",
                }

        query, is_export = self.resolve_query(customer)
        if is_export:
            return {"is_export": True}
        coords = self.geocode(query) if query else None
        if coords:
            return {
                "lat": coords[0], "lon": coords[1],
                "km": None, "label": query, "source": "geocode",
            }
        return None

    # ------------------------------------------------------- customer → query
    def resolve_query(self, customer: str) -> Tuple[Optional[str], bool]:
        """Return (geocoding_query, is_export). query is None only for exports."""
        norm = _norm(customer)
        if not norm:
            return None, False

        raw_upper = _strip_accents(str(customer)).upper()
        if any(tok in raw_upper for tok in FOREIGN_TOKENS) and "TUNISIA" not in raw_upper:
            return None, True

        if norm in SUPPLEMENTAL_CITY:
            return SUPPLEMENTAL_CITY[norm], False
        if norm in self._city_from_synthetic:
            return self._city_from_synthetic[norm], False
        for token, query in CITY_TOKENS.items():
            if token in norm:
                return query, False
        # Last resort: let Nominatim try the company name within Tunisia.
        return f"{customer.strip()}, Tunisia", False

    # ------------------------------------------------------------- geocoding
    def geocode(self, query: str) -> Optional[Tuple[float, float]]:
        if not query:
            return None
        key = query.strip().lower()
        if key in self._geocode_cache:
            cached = self._geocode_cache[key]
            return (cached[0], cached[1]) if cached else None

        result, ok = self._nominatim(query)
        # Only cache deterministic outcomes (found, or genuinely not found).
        # Network errors (ok=False) are left uncached so the next build retries.
        if ok:
            with self._lock:
                self._geocode_cache[key] = list(result) if result else None
                self._save(GEOCODE_CACHE, self._geocode_cache)
        return result

    def _nominatim(self, query: str) -> Tuple[Optional[Tuple[float, float]], bool]:
        """Return (coords_or_none, ok). ok=False means a network error."""
        # Nominatim usage policy: ≤1 request/second.
        wait = 1.05 - (time.time() - self._last_nominatim)
        if wait > 0:
            time.sleep(wait)
        params = urllib.parse.urlencode({
            "q": query, "format": "json", "limit": 1, "countrycodes": "tn",
        })
        url = f"{NOMINATIM_URL}?{params}"
        last_exc: Optional[Exception] = None
        for attempt in range(3):  # tolerate transient timeouts
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read())
                self._last_nominatim = time.time()
                if data:
                    return (float(data[0]["lat"]), float(data[0]["lon"])), True
                # Retry without the country filter for edge cases.
                return self._nominatim_global(query), True
            except Exception as exc:
                last_exc = exc
                time.sleep(1.0 * (attempt + 1))
        log.warning("GeoService: geocode failed for %r — %s", query, last_exc)
        self._last_nominatim = time.time()
        return None, False

    def _nominatim_global(self, query: str) -> Optional[Tuple[float, float]]:
        params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
        try:
            req = urllib.request.Request(f"{NOMINATIM_URL}?{params}",
                                         headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
            self._last_nominatim = time.time()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception:
            pass
        return None

    # --------------------------------------------------- road-distance matrix
    @staticmethod
    def _road_key(coords: List[Tuple[float, float]]) -> str:
        """Order-sensitive cache key (the matrix is indexed by position)."""
        return "|".join(f"{lat:.4f},{lon:.4f}" for lat, lon in coords)

    def road_km_matrix(
        self, coords: List[Tuple[float, float]]
    ) -> Optional[List[List[float]]]:
        """Real driving-distance matrix (km) for ``coords`` ([(lat, lon), ...])
        via the OSRM ``/table`` service, so depot↔client and client↔client legs
        use actual road distance instead of straight-line estimates.

        One request returns the whole NxN matrix; results are cached on disk by
        a hash of the rounded coordinates so a repeated build is instant.
        Returns None on any failure (caller falls back to the haversine matrix).
        """
        if not coords or len(coords) < 2:
            return None
        key = self._road_key(coords)
        if key in self._road_cache:
            return self._road_cache[key]
        locs = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in coords)
        url = f"{OSRM_TABLE_URL}{locs}?annotations=distance"
        matrix, ok = self._osrm_table(url, len(coords))
        if ok and matrix is not None:  # only cache deterministic outcomes
            with self._lock:
                self._road_cache[key] = matrix
                self._save(ROAD_MATRIX_CACHE, self._road_cache)
        return matrix

    def _osrm_table(
        self, url: str, size: int
    ) -> Tuple[Optional[List[List[float]]], bool]:
        """Return (km_matrix_or_none, ok). ok=False marks a network error so the
        result is not cached and the next build retries."""
        last_exc: Optional[Exception] = None
        for attempt in range(2):  # tolerate a transient hiccup
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read())
                if data.get("code") != "Ok":
                    return None, True  # OSRM answered but couldn't route — definitive
                dist = data.get("distances")
                if not dist or len(dist) != size:
                    return None, True
                km = [
                    [(v / 1000.0 if v is not None else None) for v in row]
                    for row in dist
                ]
                if any(v is None for row in km for v in row):
                    return None, True  # an unroutable pair — use the fallback
                return km, True
            except Exception as exc:
                last_exc = exc
                time.sleep(0.5 * (attempt + 1))
        log.warning("GeoService: OSRM table failed — %s", last_exc)
        return None, False

    def depot(self) -> Tuple[float, float]:
        return self.geocode(DEPOT_QUERY) or DEPOT_FALLBACK
