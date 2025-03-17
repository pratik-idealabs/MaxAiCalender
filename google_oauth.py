import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os
import json
import requests
from urllib.parse import quote_plus

# Get OAuth credentials from Streamlit secrets with detailed error handling
try:
    CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    REDIRECT_URI = st.secrets["REDIRECT_URI"]
    
    # Validate we have actual values, not empty strings
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        st.error("One or more OAuth credentials are empty. Please check your secrets configuration.")
except Exception as e:
    st.error(f"Error loading OAuth credentials from secrets: {str(e)}")
    # Fallback values - only for development
    CLIENT_ID = "615890780784-7s647bu9b0lkprobtccp92h4nuheb1s3.apps.googleusercontent.com"
    CLIENT_SECRET = "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"
    REDIRECT_URI = "https://maxaicalender.streamlit.app/"

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
        try:
            credentials_dict = json.loads(st.session_state.google_credentials)
            credentials = Credentials.from_authorized_user_info(credentials_dict)
            
            # Check if credentials are valid
            if credentials.valid:
                return credentials
        except Exception as e:
            st.error(f"Error parsing stored credentials: {str(e)}")
            # Clear invalid credentials
            st.session_state.google_credentials = None
    
    return None

def show_auth_screen():
    """Display the Google authentication button and handle the flow."""
    st.header("Google Calendar Authentication")
    
    # Add debug information
    with st.expander("Debug Information"):
        st.write("Current configuration:")
        st.write(f"- Client ID: {CLIENT_ID[:10]}...{CLIENT_ID[-5:] if CLIENT_ID else 'Not set'}")
        st.write(f"- Redirect URI: {REDIRECT_URI}")
    
    if st.button("Sign in with Google"):
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
            
            # Generate the authorization URL with appropriate parameters
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true', 
                prompt='consent',
                state=quote_plus(REDIRECT_URI)  # Add state parameter for better security
            )
            
            # Provide clear information to the user
            st.markdown("### Google Authorization")
            st.markdown("You will be redirected to Google to authorize this application.")
            st.markdown("After authorization, you will be redirected back to this app.")
            
            # Redirect to the authorization URL
            st.markdown(f'<a href="{auth_url}" target="_self">Click here to authorize with Google</a>', unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"Error setting up authentication flow: {str(e)}")
            st.write(f"Error type: {type(e).__name__}")
        
def handle_oauth_callback():
    """Handle the OAuth callback and retrieve credentials."""
    # Use only the newer st.query_params
    query_params = st.query_params
    
    if "code" in query_params:
        st.info("Processing authorization code...")
        
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
            try:
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
                    
            except Exception as e:
                st.error(f"Error retrieving calendar list: {str(e)}")
                # Continue anyway since we have valid credentials
            
            # Clear the URL parameters
            st.query_params.clear()
            
            st.success("Successfully authenticated with Google!")
            st.rerun()
            
        except Exception as e:
            st.error(f"Error during authentication: {str(e)}")
            
            # Show more detailed error information
            with st.expander("Detailed Error Information"):
                st.write(f"Error Type: {type(e).__name__}")
                st.write(f"Error Message: {str(e)}")
                
                if hasattr(e, 'response') and e.response:
                    st.write(f"Response Status: {e.response.status_code}")
                    st.write(f"Response Headers: {e.response.headers}")
                    try:
                        st.write(f"Response Content: {e.response.text}")
                    except:
                        st.write("Could not extract response content")
    
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