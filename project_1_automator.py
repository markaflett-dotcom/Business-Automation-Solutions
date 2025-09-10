def generate_personalized_message(lead_data):
    name = lead_data.get('name', 'there')
    title = lead_data.get('title', 'your role')
    company = lead_data.get('company', 'your company')
    message = f"Hi {name}, I came across your profile and was impressed by your work as {title} at {company}. Would be great to connect."
    return message

def simulate_hubspot_sync(lead_data):
    name = lead_data.get('name', '').strip()
    parts = name.split()
    firstname = parts[0] if parts else ''
    lastname = parts[-1] if len(parts) > 1 else ''

    hubspot_payload = {
        "properties": {
            "firstname": firstname,
            "lastname": lastname,
            "jobtitle": lead_data.get('title', ''),
            "company": lead_data.get('company', '')
        }
    }
    print(f"[SIMULATION] Generated HubSpot API Payload: {hubspot_payload}")
    return hubspot_payload

def main():
    print("--- Starting LinkedIn Lead Generation Automator ---")
    
    leads_to_process = [
        {'name': 'Jane Doe', 'title': 'Head of Marketing', 'company': 'Innovate Corp'},
        {'name': 'John Smith', 'title': 'Lead Developer', 'company': 'Tech Solutions Inc.'},
        {'name': 'Emily White', 'title': 'CEO', 'company': 'Future Gadgets'},
        {'name': 'David Green', 'title': 'Product Manager', 'company': 'Synergy Systems'},
        {'name': 'Chiara Rossi', 'title': 'Data Analyst', 'company': 'QuantumLeap Analytics'}
    ]
    
    print(f"[INFO] Successfully loaded {len(leads_to_process)} mock leads.")

    if not leads_to_process:
        print("--- Workflow finished. No leads to process. ---")
        return

    print("\n--- Processing Leads ---")
    for i, lead in enumerate(leads_to_process, 1):
        print(f"\n[INFO] Processing Lead #{i}: {lead.get('name')}")
        
        personalized_message = generate_personalized_message(lead)
        print(f"   - Generated Message: '{personalized_message}'")
        
        simulate_hubspot_sync(lead)
    
    print("\n--- Workflow finished successfully. ---")


if __name__ == "__main__":
    main()