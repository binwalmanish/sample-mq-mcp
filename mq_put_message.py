#!/usr/bin/env python3
"""
MQ Message Writer - Puts messages to a queue on QM1 using REST API

This program connects to QM1 via REST API and puts a message to a specified queue.
No MQ client libraries required!
"""

import httpx
import sys
from datetime import datetime

# MQ REST API Configuration
QM_NAME = 'QM1'
MQ_REST_BASE = 'https://localhost:9443/ibmmq/rest/v2/messaging'
QUEUE_NAME = 'DEV.QUEUE.1'
USER = 'app'
PASSWORD = 'passw0rd'

def put_message(message_text=None):
    """
    Put a message to the MQ queue using REST API

    Args:
        message_text: The message to send. If None, uses a default message.

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create message if not provided
        if message_text is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message_text = f"Test message sent at {timestamp}"

        # Construct URL
        url = f"{MQ_REST_BASE}/qmgr/{QM_NAME}/queue/{QUEUE_NAME}/message"

        # Set up headers
        headers = {
            'Content-Type': 'text/plain;charset=utf-8',
            'ibm-mq-rest-csrf-token': 'value',
        }

        # Set up authentication
        auth = httpx.BasicAuth(username=USER, password=PASSWORD)

        print("=" * 60)
        print("MQ Message Writer - Put Message to Queue (REST API)")
        print("=" * 60)
        print(f"Queue Manager: {QM_NAME}")
        print(f"Queue: {QUEUE_NAME}")
        print(f"REST API: {MQ_REST_BASE}")
        print("=" * 60)
        print()

        # Send the message
        print(f"Sending message: {message_text}")
        print()

        with httpx.Client(verify=False) as client:
            response = client.post(
                url,
                headers=headers,
                auth=auth,
                content=message_text,
                timeout=30.0
            )

            response.raise_for_status()

            print("✓ Message sent successfully!")
            print()
            print(f"Response status: {response.status_code}")

            # Parse response headers
            if 'ibm-mq-md-messageId' in response.headers:
                msg_id = response.headers['ibm-mq-md-messageId']
                print(f"Message ID: {msg_id}")

            return True

    except httpx.HTTPStatusError as e:
        print(f"✗ HTTP Error: {e.response.status_code}")
        print(f"Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Main function"""
    # Get message from command line or use default
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h']:
            print("Usage:")
            print("  python mq_put_message.py                    # Send default message")
            print("  python mq_put_message.py 'Your message'     # Send custom message")
            print("  python mq_put_message.py 'Multi word msg'   # Send multi-word message")
            return
        message = ' '.join(sys.argv[1:])
    else:
        message = None

    # Put the message
    success = put_message(message)

    if success:
        print("\n" + "=" * 60)
        print("SUCCESS - Message sent to queue!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("FAILED - Could not send message")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
