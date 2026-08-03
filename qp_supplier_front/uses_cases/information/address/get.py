
import frappe
import unicodedata


def get_cities(country):
    
    cities_list = frappe.get_list("qp_CO_State", filters = {"country": country}, fields = ["name", "state_name"])
    
    cities = cities_list if cities_list else [{"name": "Otro-Otro", "state_name": "Otros"}]
    
    return {
        "cities": cities
    }

def get_states(city):
    
    states_list = frappe.get_list("qp_CO_Municipality", filters = {"state_code": city}, fields = ["name", "municipality_name"])
    
    states = states_list if states_list else [{"name": "Otro-Otro", "municipality_name": "Otros"}]
    
    return {
        "states": states
    }


def _normalize(value):
    """Normaliza un valor para comparacion insensible a mayusculas, acentos y espacios."""
    if not value:
        return ""
    text = unicodedata.normalize("NFD", str(value).strip().lower())
    return "".join(char for char in text if unicodedata.category(char) != "Mn").replace(" ", "")


def _find_state_record(value):
    """Resuelve un valor (codigo o nombre) a un registro de qp_CO_State."""
    if not value:
        return None
    if frappe.db.exists("qp_CO_State", value):
        return frappe.db.get_value(
            "qp_CO_State", value, ["name", "state_name"], as_dict=True
        )
    normalized = _normalize(value)
    for record in frappe.db.get_all(
        "qp_CO_State", fields=["name", "state_name"]
    ):
        if normalized == _normalize(record.get("state_name")) or normalized == _normalize(record.get("name")):
            return record
    return None


def _find_municipality_record(value):
    """Resuelve un valor (codigo o nombre) a un registro de qp_CO_Municipality."""
    if not value:
        return None
    if frappe.db.exists("qp_CO_Municipality", value):
        return frappe.db.get_value(
            "qp_CO_Municipality", value, ["name", "municipality_name", "state_code"], as_dict=True
        )
    normalized = _normalize(value)
    for record in frappe.db.get_all(
        "qp_CO_Municipality", fields=["name", "municipality_name", "state_code"]
    ):
        if normalized == _normalize(record.get("municipality_name")):
            return record
    return None


def _resolve_department_municipality(city_value, state_value):
    """
    Clasifica los valores almacenados de city/state como departamento o municipio.

    Soporta la convencion moderna (city = departamento, state = municipio) y la
    legacy de datos sincronizados (city = municipio, state = departamento).
    """
    city_state = _find_state_record(city_value)
    city_municipality = _find_municipality_record(city_value)
    state_state = _find_state_record(state_value)
    state_municipality = _find_municipality_record(state_value)

    if city_state and state_municipality:
        department_code, department_raw = city_state.get("name"), city_value
        municipality_code, municipality_raw = state_municipality.get("name"), state_value
    elif state_state and city_municipality:
        department_code, department_raw = state_state.get("name"), state_value
        municipality_code, municipality_raw = city_municipality.get("name"), city_value
    else:
        state_record = city_state or state_state
        municipality_record = city_municipality or state_municipality
        if state_record:
            department_code = state_record.get("name")
            department_raw = city_value if state_record is city_state else state_value
            municipality_raw = state_value if state_record is city_state else city_value
        else:
            department_code = city_value or state_value
            department_raw = city_value or state_value
            municipality_raw = state_value or city_value
        municipality_code = municipality_record.get("name") if municipality_record else municipality_raw

    return {
        "department_code": department_code,
        "department_raw": department_raw,
        "municipality_code": municipality_code,
        "municipality_raw": municipality_raw,
    }


def get_address(address_id):
    
    address = frappe.get_doc("Address", address_id)
    
    raw_country = address.country
    raw_city = address.city
    raw_state = address.state
    
    resolved_country = raw_country
    if raw_country:
        country_doc_name = frappe.db.get_value("Country",
            {"country_name": raw_country}, "name"
        )
        if country_doc_name and country_doc_name != raw_country:
            resolved_country = country_doc_name
    
    resolved = _resolve_department_municipality(raw_city, raw_state)
    
    resolved_city = resolved.get("department_code")
    resolved_state = resolved.get("municipality_code")
    
    cities = get_cities(resolved_country).get("cities", [])
    if resolved_city and resolved_city not in [city.get("name") for city in cities]:
        state_doc = frappe.db.get_value(
            "qp_CO_State", resolved_city, ["name", "state_name"], as_dict=True
        )
        if state_doc:
            cities.append({"name": state_doc.get("name"), "state_name": state_doc.get("state_name")})
    if not cities:
        cities = [{"name": "Otro-Otro", "state_name": "Otros"}]
    
    states = get_states(resolved_city).get("states", [])
    if resolved_state and resolved_state not in [state.get("name") for state in states]:
        municipality_doc = frappe.db.get_value(
            "qp_CO_Municipality", resolved_state, ["name", "municipality_name"], as_dict=True
        )
        if municipality_doc:
            states.append({"name": municipality_doc.get("name"), "municipality_name": municipality_doc.get("municipality_name")})
    if not states:
        states = [{"name": "Otro-Otro", "municipality_name": "Otros"}]
    
    address_dict = address.as_dict()
    if resolved_country != raw_country:
        address_dict["country"] = resolved_country
    if resolved_city != raw_city:
        address_dict["city"] = resolved_city
    if resolved_state != raw_state:
        address_dict["state"] = resolved_state
    
    # Valores originales almacenados para que el frontend detecte conversiones
    # y busque equivalencias por nombre al mapear los selects
    address_dict["raw_country"] = raw_country
    address_dict["raw_city"] = raw_city
    address_dict["raw_state"] = raw_state
    
    return {
        "address": address_dict,
        "cities": cities,
        "states": states
    }
