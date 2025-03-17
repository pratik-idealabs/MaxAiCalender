import streamlit as st
from azure_api import call_azure_openai
from google_oauth import setup_google_oauth, show_auth_screen, handle_oauth_callback, is_authenticated, get_calendar_service, get_calendar_id, logout
from user_event_handler import handle_calendar_action
import urllib.parse
from datetime import datetime, timedelta
import pytz
import time

# UI Setup
st.set_page_config(layout="wide", page_title="AI Calendar Assistant")
st.title("AI-Powered Calendar Assistant")

# Timezone Setup
IST = pytz.timezone("Asia/Kolkata")

# Custom CSS for better styling and visibility
st.markdown("""
<style>
    .event-card {
        border-left: 4px solid #4285F4; 
        padding: 10px 15px; 
        margin-bottom: 10px; 
        background-color: #ffffff;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
    }
    .event-title {
        font-weight: bold;
        font-size: 1em;
        color: #202124;
        margin-bottom: 4px;
    }
    .event-time {
        color: #5f6368;
        font-size: 0.9em;
        margin-bottom: 4px;
    }
    .event-location {
        color: #5f6368;
        font-size: 0.9em;
    }
    .day-header {
        padding: 8px 12px;
        background-color: #f1f3f4;
        border-radius: 4px;
        margin-bottom: 8px;
        font-weight: bold;
        color: #202124;
    }
    .expander-override {
        background-color: white !important;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #e0e0e0 !important;
        border-radius: 8px !important;
        margin-bottom: 10px !important;
    }
    div[data-testid="stExpander"] > div[role="button"] {
        background-color: #f8f9fa !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state for tracking changes
if 'last_action_time' not in st.session_state:
    st.session_state.last_action_time = time.time()

if 'refresh_requested' not in st.session_state:
    st.session_state.refresh_requested = False

# Handle OAuth callback if there's a code parameter in the URL
handle_oauth_callback()

# Check if the user is authenticated
authenticated = is_authenticated()

if not authenticated:
    # Show authentication screen
    show_auth_screen()
else:
    # User is authenticated, show the calendar interface
    calendar_id = get_calendar_id()
    
    # Show logout button in sidebar
    if st.sidebar.button("Logout from Google"):
        logout()
    
    col1, col2 = st.columns([0.37, 0.63])

    with col1:
        st.markdown("""
        ### Examples:
        - "Create a meeting titled 'Team Sync' tomorrow at 2 PM for 1 hour"
        - "Find all events for next week"
        - "Delete the event titled 'Old Meeting'"
        - "Reschedule the Team Sync meeting to Friday at 3 PM"
        """)
        
        user_input = st.text_area("How can I help you with your calendar?", height=150)
        
        # Event trigger for the button
        if st.button("Process Request 🚀", type="primary"):
            if user_input.strip():
                try:
                    # Process the request with Azure OpenAI and handle the calendar action
                    with st.spinner("Processing your request..."):
                        response = call_azure_openai(user_input.strip())
                        handle_calendar_action(response)
                        
                        # Mark that we've made a change that requires a refresh
                        st.session_state.last_action_time = time.time()
                        st.session_state.refresh_requested = True
                        
                        # Automatically rerun the app to refresh the calendar display
                        st.rerun()
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
            else:
                st.warning("Please provide a valid input before processing.")
                
        # Add a manual refresh button
        if st.button("Refresh Calendar"):
            st.session_state.refresh_requested = True
            st.rerun()

    with col2:
        st.subheader("Your Calendar")
        
        # Create a button to open the calendar in a new window
        st.markdown("""
        <a href="https://calendar.google.com/calendar/r" target="_blank" 
           style="display: inline-block; background-color: #4285F4; color: white; 
           padding: 10px 20px; text-decoration: none; border-radius: 5px; 
           font-weight: bold; margin-bottom: 15px;">
            Open Google Calendar
        </a>
        """, unsafe_allow_html=True)
        
        # Display a smaller placeholder
        st.markdown("""
        <div style="border: 1px solid #ddd; border-radius: 8px; padding: 10px; text-align: center; 
                    background-color: #f9f9f9; margin-bottom: 15px; height: 120px; display: flex; 
                    flex-direction: column; justify-content: center; align-items: center;">
            <img src="https://www.gstatic.com/calendar/images/dynamiclogo_2020q4/calendar_10_2x.png" 
                 style="width: 48px; height: 48px; margin-bottom: 10px;">
            <div style="margin: 5px 0; font-size: 18px; font-weight: bold;">Your Google Calendar</div>
            <div style="font-size: 0.9em; color: #666; margin: 5px 0;">
                You can use the assistant on the left to manage your calendar without leaving this page.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Display refresh status if needed
        if st.session_state.refresh_requested:
            with st.spinner("Refreshing calendar data..."):
                # Reset the flag
                st.session_state.refresh_requested = False
        
        # Try to display upcoming events
        calendar_container = st.container()
        with calendar_container:
            try:
                calendar_service = get_calendar_service()
                if calendar_service:
                    # Get events for the next 7 days
                    now = datetime.now(IST)
                    time_min = now.isoformat()
                    time_max = (now + timedelta(days=7)).isoformat()
                    
                    events_result = calendar_service.events().list(
                        calendarId=calendar_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        maxResults=10,
                        singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                    
                    events = events_result.get('items', [])
                    
                    if events:
                        st.markdown("### Upcoming Events")
                        
                        # Group events by day
                        days = {}
                        for event in events:
                            start = event['start'].get('dateTime', event['start'].get('date'))
                            
                            if 'dateTime' in event['start']:
                                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(IST)
                                day_key = start_dt.strftime("%Y-%m-%d")
                                day_display = start_dt.strftime("%A, %b %d")
                            else:
                                start_dt = datetime.strptime(start, "%Y-%m-%d")
                                day_key = start
                                day_display = start_dt.strftime("%A, %b %d")
                            
                            if day_key not in days:
                                days[day_key] = {"display": day_display, "events": []}
                            days[day_key]["events"].append(event)
                        
                        # Display events grouped by day
                        for day_key in sorted(days.keys()):
                            day_info = days[day_key]
                            
                            # Create an expander for each day
                            with st.expander(day_info["display"], expanded=(day_key == list(days.keys())[0])):
                                for event in day_info["events"]:
                                    start = event['start'].get('dateTime', event['start'].get('date'))
                                    
                                    if 'dateTime' in event['start']:
                                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00')).astimezone(IST)
                                        time_str = start_dt.strftime("%I:%M %p")
                                        
                                        # If we have an end time, include it
                                        if 'dateTime' in event.get('end', {}):
                                            end_dt = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00')).astimezone(IST)
                                            time_str += f" - {end_dt.strftime('%I:%M %p')}"
                                    else:
                                        time_str = "All day"
                                    
                                    summary = event.get('summary', 'No title')
                                    location = event.get('location', '')
                                    
                                    # Instead of using HTML markdown, use st.container for better visibility
                                    with st.container():
                                        st.markdown(f"""
                                        <div class="event-card">
                                            <div class="event-title">{summary}</div>
                                            <div class="event-time">⏰ {time_str}</div>
                                            {f'<div class="event-location">📍 {location}</div>' if location else ''}
                                        </div>
                                        """, unsafe_allow_html=True)
                    else:
                        st.info("No upcoming events found in the next 7 days.")
            except Exception as e:
                st.error(f"Unable to fetch upcoming events: {str(e)}")
                st.info("You can still use the assistant to create and manage events.")   