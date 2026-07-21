
import frappe


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
    
def get_address(address_id):
    
    address = frappe.get_doc("Address", address_id)
    
    resolved_country = address.country
    resolved_city = address.city
    resolved_state = address.state
    
    # Fallback: resolver country_name al name de Frappe Country
    # (MySQL collation puede ser case-insensitive, pero JS .val() no lo es)
    if address.country:
        country_doc_name = frappe.db.get_value("Country",
            {"country_name": address.country}, "name"
        )
        if country_doc_name and country_doc_name != address.country:
            resolved_country = country_doc_name
    
    # Fallback: si el valor almacenado no es un codigo de qp_CO_State,
    # buscar por state_name (caso datos legacy sincronizados con nombre plano)
    if address.city and not frappe.db.exists("qp_CO_State", address.city):
        state_doc = frappe.db.get_value("qp_CO_State",
            {"state_name": address.city}, "name"
        )
        if state_doc:
            resolved_city = state_doc
    
    # Fallback: si el valor almacenado no es un codigo de qp_CO_Municipality,
    # buscar por municipality_name
    if address.state and not frappe.db.exists("qp_CO_Municipality", address.state):
        filters = {"municipality_name": address.state}
        mun_doc = frappe.db.get_value("qp_CO_Municipality", filters, "name")
        if not mun_doc and frappe.db.exists("qp_CO_State", resolved_city):
            filters = {
                "municipality_name": address.state,
                "state_code": resolved_city
            }
            mun_doc = frappe.db.get_value("qp_CO_Municipality", filters, "name")
        if mun_doc:
            resolved_state = mun_doc
    
    address_dict = address.as_dict()
    if resolved_country != address.country:
        address_dict["country"] = resolved_country
    if resolved_city != address.city:
        address_dict["city"] = resolved_city
    if resolved_state != address.state:
        address_dict["state"] = resolved_state
    
    return {
        "address": address_dict,
        **get_cities(resolved_country),
        **get_states(resolved_city)
    }