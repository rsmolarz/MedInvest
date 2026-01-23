"""
GoHighLevel CRM Integration
Adds new signups to GoHighLevel as contacts
"""
import os
import logging
import requests
from threading import Thread

GHL_API_TOKEN = os.environ.get('GHL_API_TOKEN')
GHL_LOCATION_ID = os.environ.get('GHL_LOCATION_ID')
GHL_API_URL = 'https://services.leadconnectorhq.com/contacts/'


def add_contact_to_ghl(user):
    """
    Add a new user to GoHighLevel CRM as a contact.
    Runs in background thread to not block registration.
    """
    logging.info(f"GoHighLevel sync triggered for user: {user.email}")
    
    if not GHL_API_TOKEN or not GHL_LOCATION_ID:
        logging.warning("GoHighLevel not configured - GHL_API_TOKEN or GHL_LOCATION_ID missing")
        return
    
    def _sync():
        try:
            logging.info(f"Sending contact to GoHighLevel: {user.email}")
            
            headers = {
                'Authorization': f'Bearer {GHL_API_TOKEN}',
                'Content-Type': 'application/json',
                'Version': '2021-07-28'
            }
            
            payload = {
                'locationId': GHL_LOCATION_ID,
                'firstName': user.first_name,
                'lastName': user.last_name,
                'email': user.email,
                'source': 'MedInvest Registration',
                'tags': ['medinvest', 'new-signup', 'medmoneyincubator']
            }
            
            if user.specialty:
                payload['customFields'] = [
                    {'key': 'specialty', 'value': user.specialty}
                ]
            
            logging.info(f"GoHighLevel payload: {payload}")
            
            response = requests.post(
                GHL_API_URL,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code in (200, 201):
                logging.info(f"SUCCESS: Added user {user.email} to GoHighLevel CRM")
            else:
                logging.error(f"GoHighLevel API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logging.error(f"Failed to add contact to GoHighLevel: {str(e)}")
    
    thread = Thread(target=_sync, daemon=True)
    thread.start()
