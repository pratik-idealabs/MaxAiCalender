import streamlit as st
from datetime import datetime, timedelta
import pytz
from google_oauth import get_calendar_service, get_calendar_id

# Timezone Setup
IST = pytz.timezone("Asia/Kolkata")

def handle_calendar_action(params):
    """Dispatches calendar actions to appropriate handlers using user's credentials."""
    if not params or "action" not in params:
        st.warning("Invalid or missing action in the response.")
        return
    
    # Get the user's calendar service and ID
    service = get_calendar_service()
    calendar_id = get_calendar_id()
    
    if not service or not calendar_id:
        st.error("Not authenticated with Google. Please sign in first.")
        return

    action_handlers = {
        "message": handle_message,
        "error": handle_error,
        "find": lambda data: find_events(data, service, calendar_id),
        "create": lambda data: create_event(data, service, calendar_id),
        "delete": lambda data: delete_event(data, service, calendar_id),
        "reschedule": lambda data: reschedule_event(data, service, calendar_id),
    }

    action = params["action"]
    event_data = params.get("event", {})

    handler = action_handlers.get(action, lambda _: st.warning(f"Unsupported action: {action}"))
    try:
        handler(event_data)
    except Exception as e:
        st.error(f"Error executing {action} action: {str(e)}")

def handle_message(event_data):
    """Displays message from the assistant."""
    content = event_data.get("content", "").strip()
    if content:
        st.info(f"**Assistant Response:** {content}")
    else:
        st.warning("Received an empty response. Please try again.")

def handle_error(event_data):
    """Displays error messages."""
    st.error(event_data.get("content", "An error occurred"))

def find_events(event_data, service, calendar_id):
    """Finds events within a specified time range."""
    start_time = event_data.get("start_time")
    end_time = event_data.get("end_time", start_time)

    if not start_time:
        st.warning("Start time is required for finding events.")
        return

    # Convert to RFC 3339 format with timezone
    start_time = datetime.fromisoformat(start_time).astimezone(IST).isoformat()
    end_time = datetime.fromisoformat(end_time).astimezone(IST).isoformat()

    try:
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy="startTime"
        ).execute().get("items", [])

        if events:
            st.write("**Found Events:**")
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                st.write(f"📅 {event.get('summary', 'No Title')}: {start}")
        else:
            st.info("No events found.")
    except Exception as e:
        st.error(f"Failed to fetch events: {str(e)}")

def create_event(event_data, service, calendar_id):
    """Creates a new event in Google Calendar and displays details."""
    required_fields = ["start_time", "summary"]
    missing_fields = [field for field in required_fields if not event_data.get(field)]

    if missing_fields:
        st.warning(f"Missing required fields: {', '.join(missing_fields)}")
        return

    start_time_iso = event_data["start_time"]
    
    # Automatically set end_time to 1 hour after start_time if not provided
    if not event_data.get("end_time"):
        start_time_obj = datetime.fromisoformat(start_time_iso)
        end_time_obj = start_time_obj + timedelta(hours=1)
        end_time_iso = end_time_obj.isoformat()
    else:
        end_time_iso = event_data["end_time"]

    event = {
        "summary": event_data["summary"],
        "start": {"dateTime": start_time_iso, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_time_iso, "timeZone": "Asia/Kolkata"},
        "description": event_data.get("description", "Created by AI Calendar Assistant"),
    }

    try:
        with st.spinner("Creating event..."):
            created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
            st.success(f"✅ Event '{event['summary']}' created successfully!")
    except Exception as e:
        st.error(f"Failed to create event: {str(e)}")
        
def delete_event(event_data, service, calendar_id):
    """Delete events based on title or within a specific date range, including today."""
    event_title = event_data.get("summary", "")
    start_time = event_data.get("start_time", None)
    end_time = event_data.get("end_time", None)
    
    # Handle bulk deletion cases by setting title to empty string
    if event_title and any(keyword in event_title.lower() for keyword in ["all events", "all my events"]):
        event_title = ""

    # If the user requested to delete "today's events"
    if not start_time:
        today = datetime.now(IST).date()
        start_time = datetime.combine(today, datetime.min.time()).astimezone(IST).isoformat()
        end_time = datetime.combine(today, datetime.max.time()).astimezone(IST).isoformat()

    if start_time and not end_time:
        end_time = (datetime.fromisoformat(start_time) + timedelta(days=1)).astimezone(IST).isoformat()

    try:
        # Fetch events in the specified time range
        with st.spinner("Finding events to delete..."):
            events_query = service.events().list(
                calendarId=calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                # Only use q parameter if we're looking for a specific event title
                **({"q": event_title} if event_title else {})
            ).execute()

            events = events_query.get("items", [])

        if events:
            # Immediately delete events
            with st.spinner(f"Deleting {len(events)} events..."):
                for event in events:
                    service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()

                st.success(f"✅ Deleted {len(events)} events successfully!")
        else:
            st.info("No matching events found for deletion.")

    except Exception as e:
        st.error(f"Error while deleting events: {str(e)}")

def reschedule_event(event_data, service, calendar_id):
    """Reschedules an existing event."""
    event_title = event_data.get("summary")
    new_start_time = event_data.get("new_start_time")
    new_end_time = event_data.get("new_end_time")

    if not event_title:
        st.warning("Event title is required for rescheduling.")
        return

    try:
        # First find the event
        with st.spinner("Finding event to reschedule..."):
            events = service.events().list(
                calendarId=calendar_id,
                q=event_title,
                singleEvents=True,
                maxResults=1  # We'll take the first matching event
            ).execute().get("items", [])

        if events:
            event = events[0]
            event_id = event["id"]
            
            # Get the original event time components
            orig_start = datetime.fromisoformat(event["start"]["dateTime"])
            orig_end = datetime.fromisoformat(event["end"]["dateTime"])
            orig_duration = orig_end - orig_start
            
            # If new_start_time is a full day format (00:00-23:59), preserve original time
            new_start = datetime.fromisoformat(new_start_time)
            if new_start.hour == 0 and new_start.minute == 0:
                # Create new datetime with original time
                new_start = datetime.combine(new_start.date(), orig_start.time())
                new_start = new_start.replace(tzinfo=orig_start.tzinfo)
                new_start_time = new_start.isoformat()
            
            # Calculate new end time based on original duration
            new_end = new_start + orig_duration
            new_end_time = new_end.isoformat()
            
            # Update the event times
            event["start"]["dateTime"] = new_start_time
            event["end"]["dateTime"] = new_end_time
            
            # Update the event
            with st.spinner("Updating event..."):
                updated_event = service.events().update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event
                ).execute()
                
                st.success(f"✅ Rescheduled event '{event_title}' to {new_start.strftime('%B %d, %Y at %I:%M %p')}")
        else:
            st.info(f"No events found matching '{event_title}' for rescheduling.")
            
    except Exception as e:
        st.error(f"Error while rescheduling event: {str(e)}")