import requests
import uuid
import json

# ==============================================================================
# Section 1: Configuration (Edit this part)
# ==============================================================================

# The full base URL for Server A.
# Example: 'http://localhost:8001' or 'http://your-server-ip:8001'
SERVER_A_URL = 'http://localhost:8001'

# The API Key you received from the system administrator.
API_KEY = 'api_key_for_service_A' # <-- Place your API Key here

# ==============================================================================
# Section 2: Core Sending Function (Do not change this part)
# ==============================================================================

def send_sms(recipient: str, message: str, providers: list = None):
    """
    Sends an SMS request to the Server A gateway.

    Args:
        recipient (str): The recipient's phone number in E.164 format (e.g., +1234567890).
        message (str): The content of the SMS message to send.
        providers (list, optional): A list of preferred providers. If empty or None,
                                    the server will use smart selection.
                                    Example: ["ProviderA", "ProviderD"]
    """
    if providers is None:
        providers = []

    # Generate a unique key to prevent duplicate requests (Idempotency)
    idempotency_key = str(uuid.uuid4())

    # Define the request headers
    headers = {
        'Content-Type': 'application/json',
        'API-Key': API_KEY,
        'Idempotency-Key': idempotency_key
    }

    # Construct the request body (payload)
    payload = {
        'to': recipient,
        'text': message,
        'providers': providers
        # You can also add 'ttl_seconds' here if needed
    }

    # The full URL for the send endpoint
    send_url = f"{SERVER_A_URL}/api/v1/sms/send"

    print(f"🚀 Sending request to: {send_url}")
    print(f"   - Recipient: {recipient}")
    print(f"   - API Key: {API_KEY[:8]}...") # Show first 8 chars for security
    print(f"   - Idempotency-Key: {idempotency_key}")
    
    try:
        # Send the POST request
        response = requests.post(send_url, headers=headers, json=payload, timeout=10)

        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        # If the request was accepted successfully (HTTP 202 Accepted)
        print("\n✅ Request accepted successfully by the server!")
        print("-------------------------------------------------")
        
        # Display the server's response, which includes the tracking_id
        response_data = response.json()
        print(f"   - Server Message: {response_data.get('message')}")
        print(f"   - Tracking ID: {response_data.get('tracking_id')}")
        print("You can use this Tracking ID to trace the message status on Server B.")

    except requests.exceptions.HTTPError as http_err:
        # This block executes if the server returns an HTTP error code
        print(f"\n❌ Server-side error occurred (Status Code: {response.status_code})")
        print("-------------------------------------------------")
        try:
            # Attempt to parse and display the detailed error from the server
            error_details = response.json()
            print(f"   - Error Code: {error_details.get('error_code')}")
            print(f"   - Error Message: {error_details.get('message')}")
        except json.JSONDecodeError:
            # Fallback if the error response is not valid JSON
            print(f"   - Could not parse error response from server: {response.text}")
            
    except requests.exceptions.RequestException as req_err:
        # This block executes if there's a network-related issue
        print(f"\n❌ Failed to connect to the server: {req_err}")
        print("-------------------------------------------------")
        print("   - Please ensure the SERVER_A_URL is correct.")
        print("   - Verify that Server A is running and your network connection is stable.")

# ==============================================================================
# Section 3: Script Execution (Edit this part for your test)
# ==============================================================================

if __name__ == "__main__":
    # --- Configure your test message here ---
    
    # Recipient's phone number (must be in international E.164 format)
    test_recipient = "+15551234567"
    
    # The message text
    test_message = "This is a test message sent via the Python script."
    
    # Optional list of providers
    # To let the server choose, leave this as an empty list: []
    # To request a specific provider: ["ProviderA"]
    # To specify a prioritized failover list: ["ProviderD", "ProviderA"]
    test_providers = []

    # --- Execute the send function ---
    send_sms(
        recipient=test_recipient,
        message=test_message,
        providers=test_providers
    )