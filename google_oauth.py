import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os
import json

# Get OAuth credentials from Streamlit secrets
CLIENT_ID = st.secrets.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = st.secrets.get("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = st.secrets.get("REDIRECT_URI", "http://localhost:8501/")

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def setup_google_oauth():
    """Set up Google OAuth flow and return credentials if already authenticated."""
    # Define the OAuth flow
    if 'google_credentials' not in st.session_state:
        st.session_state.google_credentials = None
    
    if 'calendar_id' not in st.session_state:
        st.session_state.calendar_id = None
    
    # Check if we have credentials
    if st.session_state.google_credentials:
        credentials_dict = json.loads(st.session_state.google_credentials)
        credentials = Credentials.from_authorized_user_info(credentials_dict)
        
        # Check if credentials are valid
        if credentials.valid:
            return credentials
    
    return None

def show_auth_screen():
    """Display the Google authentication button and handle the flow."""
    st.header("Google Calendar Authentication")
    
    # Check if credentials are properly configured
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("Google OAuth credentials are not configured. Please set up your secrets.")
        st.info("If you're the developer, check the .streamlit/secrets.toml file or Streamlit Cloud secrets.")
        return
    
    if st.button("Sign in with Google"):
        # Create a flow instance with client secrets
        client_config = {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        
        # Generate the authorization URL
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        # Redirect to the authorization URL
        st.markdown(f'<a href="{auth_url}" target="_self">Click here to authorize</a>', unsafe_allow_html=True)
        
def handle_oauth_callback():
    """Handle the OAuth callback and retrieve credentials."""
    # Use only the newer st.query_params
    query_params = st.query_params
    
    if "code" in query_params:
        try:
            # Create a flow instance with client secrets
            client_config = {
                "web": {
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT_URI],
                }
            }
            
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI
            )
            
            # Use the authorization code to get credentials
            flow.fetch_token(code=query_params["code"])
            credentials = flow.credentials
            
            # Save credentials
            st.session_state.google_credentials = credentials.to_json()
            
            # Get the user's primary calendar ID
            service = build('calendar', 'v3', credentials=credentials)
            calendar_list = service.calendarList().list().execute()
            
            # Find the primary calendar
            primary_calendar = None
            for calendar_entry in calendar_list.get('items', []):
                if calendar_entry.get('primary'):
                    primary_calendar = calendar_entry
                    break
            
            if primary_calendar:
                st.session_state.calendar_id = primary_calendar['id']
            
            # Clear the URL parameters
            st.query_params.clear()
            
            st.success("Successfully authenticated with Google!")
            st.rerun()
            
        except Exception as e:
            st.error(f"Error during authentication: {str(e)}")
    
def is_authenticated():
    """Check if the user is authenticated."""
    return st.session_state.get('google_credentials') is not None

def get_calendar_service():
    """Return an authenticated calendar service if available."""
    if is_authenticated():
        try:
            credentials_dict = json.loads(st.session_state.google_credentials)
            credentials = Credentials.from_authorized_user_info(credentials_dict)
            service = build('calendar', 'v3', credentials=credentials)
            
            # Test the service with a minimal API call
            try:
                service.calendarList().list(maxResults=1).execute()
                return service
            except Exception as e:
                if "enabled" in str(e):
                    st.error("Calendar API is not enabled. Please enable it in Google Cloud Console.")
                    st.markdown("Visit the [Google Cloud Console](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com) to enable the Calendar API.")
                else:
                    st.error(f"Error connecting to Calendar API: {str(e)}")
                return None
                
        except Exception as e:
            st.error(f"Error creating calendar service: {str(e)}")
            return None
    return None

def get_calendar_id():
    """Return the user's calendar ID if available."""
    return st.session_state.get('calendar_id')

def logout():
    """Clear the stored credentials."""
    if 'google_credentials' in st.session_state:
        del st.session_state.google_credentials
    if 'calendar_id' in st.session_state:
        del st.session_state.calendar_id
    st.success("Logged out successfully!")
    st.rerun()