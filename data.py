"""
data.py — CEB Sri Lanka grid data
Areas, faults, customers, fault types, adjacency, crew capacity, uncertainty levels.
"""

AREAS = {
    "Colombo-07": {
        "substation": "Borella Grid Substation",
        "feeders": ["Feeder 1A (Thurstan Rd)", "Feeder 1B (Baseline Rd)", "Feeder 2A (Horton Place)"],
        "current_fault": {
            "type": "line_tripped",
            "feeder": "Feeder 1A (Thurstan Rd)",
            "description": "Main feeder line tripped at junction box near Thurstan Road due to tree contact",
            "eta_minutes": 45,
            "reported_at": "14:30",
            "crew_on_site": True,
        },
    },
    "Negombo": {
        "substation": "Negombo Grid Substation",
        "feeders": ["North Feeder", "South Feeder", "Beach Road Feeder"],
        "current_fault": {
            "type": "transformer_overload",
            "feeder": "North Feeder",
            "description": "Distribution transformer #NB-04 overloaded due to peak demand surge, protective relay triggered",
            "eta_minutes": 90,
            "reported_at": "13:15",
            "crew_on_site": True,
        },
    },
    "Kandy": {
        "substation": "Kandy Central Substation",
        "feeders": ["Peradeniya Feeder", "Katugastota Feeder", "City Feeder"],
        "current_fault": None,
        "note": "All feeders operating normally. No active faults.",
    },
    "Galle": {
        "substation": "Galle Grid Substation",
        "feeders": ["Fort Feeder", "Wakwella Feeder", "Karapitiya Feeder"],
        "current_fault": {
            "type": "cable_break",
            "feeder": "Karapitiya Feeder",
            "description": "Underground cable break detected near Karapitiya Hospital junction, excavation team required",
            "eta_minutes": 180,
            "reported_at": "11:00",
            "crew_on_site": False,
        },
    },
    "Matara": {
        "substation": "Matara Grid Substation",
        "feeders": ["Walgama Feeder", "Kotuwegoda Feeder"],
        "current_fault": {
            "type": "scheduled_maintenance",
            "feeder": "Walgama Feeder",
            "description": "Pre-announced scheduled maintenance — feeder insulator replacement. Work order #MT-2024-089",
            "eta_minutes": 120,
            "reported_at": "09:00",
            "crew_on_site": True,
        },
    },
}

# BUTTERFLY EFFECT: geographic adjacency — fault in one area stresses these neighbours
AREA_ADJACENCY = {
    "Colombo-07": ["Negombo", "Kandy"],
    "Negombo":    ["Colombo-07"],
    "Kandy":      ["Colombo-07", "Matara"],
    "Galle":      ["Matara"],
    "Matara":     ["Galle", "Kandy"],
}

# NEGOTIATION: starting crew capacity per area
CREW_CAPACITY = {
    "Colombo-07": 3,
    "Negombo":    2,
    "Kandy":      2,
    "Galle":      2,
    "Matara":     1,
}

# UNCERTAINTY: base diagnosis confidence by fault type
FAULT_UNCERTAINTY = {
    "line_tripped":          {"base_confidence": 85, "note": "Grid sensors confirm trip event"},
    "transformer_overload":  {"base_confidence": 90, "note": "Load telemetry is precise"},
    "cable_break":           {"base_confidence": 60, "note": "Underground faults require excavation to verify"},
    "scheduled_maintenance": {"base_confidence": 98, "note": "Work order documented"},
}

FAULT_TYPE_INFO = {
    "line_tripped":          {"label": "Line Tripped",           "severity": "high",     "color": "red",    "icon": "⚡"},
    "transformer_overload":  {"label": "Transformer Overload",   "severity": "high",     "color": "orange", "icon": "🔴"},
    "cable_break":           {"label": "Cable Break",            "severity": "critical", "color": "red",    "icon": "🔧"},
    "scheduled_maintenance": {"label": "Scheduled Maintenance",  "severity": "medium",   "color": "blue",   "icon": "🔵"},
    None:                    {"label": "No Fault",               "severity": "none",     "color": "green",  "icon": "✅"},
}

SAMPLE_CUSTOMERS = [
    {"id": "C001", "name": "Saman Perera",          "area": "Colombo-07", "phone": "071-1234567"},
    {"id": "C002", "name": "Nimali Fernando",        "area": "Negombo",    "phone": "071-2345678"},
    {"id": "C003", "name": "Ruwan Silva",            "area": "Kandy",      "phone": "071-3456789"},
    {"id": "C004", "name": "Dilani Jayawardena",     "area": "Galle",      "phone": "071-4567890"},
    {"id": "C005", "name": "Kasun Bandara",          "area": "Matara",     "phone": "071-5678901"},
    {"id": "C006", "name": "Priya Wickramasinghe",   "area": "Colombo-07", "phone": "071-6789012"},
    {"id": "C007", "name": "Anil Gunasekara",        "area": "Negombo",    "phone": "071-7890123"},
    {"id": "C008", "name": "Chamari Rathnayake",     "area": "Galle",      "phone": "071-8901234"},
    {"id": "C009", "name": "Tharaka Dissanayake",    "area": "Matara",     "phone": "071-9012345"},
    {"id": "C010", "name": "Malika Senanayake",      "area": "Kandy",      "phone": "071-0123456"},
    {"id": "C011", "name": "Custom Customer",        "area": None,         "phone": ""},
]

STATUS_CONFIG = {
    "RECEIVED":   {"color": "#F59E0B", "label": "Received",   "bg": "#FEF3C7"},
    "ROUTING":    {"color": "#6366F1", "label": "Routing",    "bg": "#EEF2FF"},
    "DIAGNOSING": {"color": "#8B5CF6", "label": "Diagnosing", "bg": "#F5F3FF"},
    "DIAGNOSED":  {"color": "#F97316", "label": "Diagnosed",  "bg": "#FFF7ED"},
    "RESOLVED":   {"color": "#10B981", "label": "Resolved",   "bg": "#ECFDF5"},
    "NO_FAULT":   {"color": "#3B82F6", "label": "No Fault",   "bg": "#EFF6FF"},
}
