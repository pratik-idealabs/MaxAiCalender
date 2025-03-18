import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os
import json


def get_client_config():
    """Return the Google client configuration from secrets."""
    return {
        "web": {
            "client_id": st.secrets["GOOGLE_CLIENT_ID"],
            "project_id": "max-calendar-453518",  # You can hardcode this as it's not sensitive
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
            "redirect_uris": [st.secrets["REDIRECT_URI"]]
        }
    }

def get_auth_code_from_url():
    """Extract authorization code from URL if present."""
    params = st.query_params
    if 'code' in params:
        return params['code']
    return None

def setup_google_oauth():
    """Set up Google OAuth flow and return credentials if already authenticated."""
    # Initialize session state if needed
    if 'google_credentials' not in st.session_state:
        st.session_state.google_credentials = None
    
    if 'calendar_id' not in st.session_state:
        st.session_state.calendar_id = None
    
    # Check if we have credentials
    if st.session_state.google_credentials:
        try:
            credentials_dict = json.loads(st.session_state.google_credentials)
            credentials = Credentials.from_authorized_user_info(credentials_dict)
            
            # Check if credentials are valid
            if credentials.valid:
                return credentials
        except Exception as e:
            st.error(f"Error with stored credentials: {str(e)}")
            st.session_state.google_credentials = None
    
    return None

def show_auth_screen():
    """Display the Google authentication button and handle the flow."""
    st.header("Google Calendar Authentication")
    
    # Check for authorization code in URL
    auth_code = get_auth_code_from_url()
    
    if auth_code and not st.session_state.google_credentials:
        with st.spinner("🔐 Completing authentication..."):
            try:
                flow = Flow.from_client_config(
                    get_client_config(),
                    scopes=[
                        'https://www.googleapis.com/auth/calendar',
                        'https://www.googleapis.com/auth/calendar.events',
                        'https://www.googleapis.com/auth/calendar.readonly'
                    ],
                    redirect_uri=st.secrets["REDIRECT_URI"]
                )
                flow.fetch_token(code=auth_code)
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
                st.error(f"Authentication failed: {str(e)}")
    
    if not st.session_state.google_credentials:
        if st.button("Sign in with Google", key="google_login"):
            try:
                flow = Flow.from_client_config(
                    get_client_config(),
                    scopes=[
                        'https://www.googleapis.com/auth/calendar',
                        'https://www.googleapis.com/auth/calendar.events',
                        'https://www.googleapis.com/auth/calendar.readonly'
                    ],
                    redirect_uri=st.secrets["REDIRECT_URI"]
                )
                auth_url, _ = flow.authorization_url(prompt='consent')
                st.markdown(f"[Click here to authorize]({auth_url})")
            except Exception as e:
                st.error(f"Error initiating authentication: {str(e)}")

def handle_oauth_callback():
    """Handle the OAuth callback - now integrated into show_auth_screen."""
    # This functionality is now handled directly in show_auth_screen
    pass

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