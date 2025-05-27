
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
    
    return {
        "address": address.as_dict(),
        **get_cities(address.country),
        **get_states(address.city)
    }