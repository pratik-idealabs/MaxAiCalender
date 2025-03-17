import json
import requests
import streamlit as st
from datetime import datetime, timedelta
import pytz

# Timezone Setup
IST = pytz.timezone("Asia/Kolkata")

def get_current_date():
    """Returns the current datetime in IST timezone."""
    return datetime.now(IST)

def parse_azure_response(response_text):
    """Parses Azure OpenAI response and extracts calendar action details or function calls."""
    try:
        response_data = json.loads(response_text)
        tool_calls = response_data.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
        
        # Extract function call arguments if present
        if tool_calls and tool_calls[0]["type"] == "function" and "arguments" in tool_calls[0]["function"]:
            # Parse the arguments which are in JSON string format
            arguments_str = tool_calls[0]["function"]["arguments"]
            arguments = json.loads(arguments_str)
            return arguments
            
        # Fallback to message content
        message = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"action": "message", "content": message.strip() or "Received an empty response from the assistant."}
            
    except (json.JSONDecodeError, IndexError, KeyError) as e:
        st.error(f"Error processing response: {str(e)}")
        return {"action": "error", "content": "Response parsing error."}

def call_azure_openai(user_input):
    """Sends user input to Azure OpenAI and returns parsed response using tool calling."""
    try:
        current_date = get_current_date().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get credentials from secrets
        try:
            # The endpoint in secrets should NOT contain api-version
            endpoint_with_version = st.secrets['AZURE_OPENAI_ENDPOINT']
            api_key = st.secrets['AZURE_OPENAI_API_KEY']
            
            # Extract just the base URL without any query parameters
            base_url = endpoint_with_version.split('?')[0]
            
            # Remove any trailing spaces or slashes
            base_url = base_url.strip()
            while base_url.endswith('/'):
                base_url = base_url[:-1]
                
            # Use a current API version
            api_version = "2023-05-15"
            
            # Create clean URL with API version
            url_with_params = f"{base_url}?api-version={api_version}"
            
        except Exception as e:
            st.error(f"Error accessing secrets: {str(e)}")
            return {"action": "error", "content": "Configuration error - API credentials not found"}
        
        # Construct the headers
        headers = {
            "Content-Type": "application/json",
            "api-key": api_key
        }
        
        payload = {
            "messages": [
                {"role": "system", "content": f"""
                    You are a highly capable calendar assistant. Current date and time is {current_date} in the Asia/Kolkata timezone.
                    You will receive user inputs related to calendar events. Your job is to map the user's request to a specific calendar action 
                    (create, find, delete, reschedule) and provide structured event details as needed using tool calling.

                    When handling deletion requests:
                    - If the user asks to delete events for a specific day, use the "delete" action, not "find"
                    - For "tomorrow", use the next day's date range
                    - For "today", use the current day's date range
                    - Set both start_time and end_time to cover the full day (00:00:00 to 23:59:59)

                    When handling rescheduling requests:
                    - Use the "reschedule" action directly, not "find" then "reschedule"
                    - Preserve the original event's time of day when moving to a new date
                    - For specific date changes (e.g., "from X to Y"), use those exact dates
                    - Always include both new_start_time and new_end_time in the response
                """.strip()},
                {"role": "user", "content": user_input.strip()}
            ],
            "tools": [{
                "type": "function",
                "function": {
                    "name": "calendar_action",
                    "description": "Handles creating, finding, deleting, or rescheduling events.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["create", "find", "delete", "reschedule"],
                                "description": "The type of calendar action requested by the user. Use 'delete' for deletion requests, not 'find'."
                            },
                            "event": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string", "description": "The title or summary of the event. Use empty string for bulk deletions."},
                                    "start_time": {"type": "string", "description": "The start time of the event in ISO format with timezone."},
                                    "end_time": {"type": "string", "description": "The end time of the event in ISO format with timezone."},
                                    "new_start_time": {"type": "string", "description": "The new start time for rescheduling. When rescheduling, provide this directly without using find action first."},
                                    "new_end_time": {"type": "string", "description": "The new end time for rescheduling. Should maintain the same duration as the original event."},
                                    "description": {"type": "string", "description": "A description or purpose of the event."}
                                },
                                "required": ["summary", "start_time"]
                            }
                        },
                        "required": ["action"]
                    }
                }
            }],
            "tool_choice": {"type": "function", "function": {"name": "calendar_action"}}
        }
        
        try:
            with st.spinner("Processing your request..."):
                response = requests.post(url_with_params, headers=headers, json=payload)
                response.raise_for_status()
                return parse_azure_response(response.text)
        except requests.exceptions.HTTPError as e:
            st.error(f"HTTP Error: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                st.error(f"Response content: {e.response.text}")
            return {"action": "error", "content": str(e)}
            
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {str(e)}")
        return {"action": "error", "content": str(e)}
    except json.JSONDecodeError:
        st.error("Failed to parse Azure OpenAI response.")
        return {"action": "error", "content": "Response parsing error."}
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return {"action": "error", "content": str(e)}