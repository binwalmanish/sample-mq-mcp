#!/usr/bin/env python3
"""
MQ Message Reader - Gets messages from a queue on QM1 using REST API

This program connects to QM1 via REST API and retrieves messages from a specified queue.
No MQ client libraries required!
"""

import httpx
import sys
import json

# MQ REST API Configuration
QM_NAME = 'QM1'
MQ_REST_BASE = 'https://localhost:9443/ibmmq/rest/v2/messaging'
QUEUE_NAME = 'DEV.QUEUE.1'
USER = 'app'
PASSWORD = 'passw0rd'

def get_queue_depth():
    """Get the current depth of the queue"""
    try:
        url = f"{MQ_REST_BASE}/qmgr/{QM_NAME}/queue/{QUEUE_NAME}"

        headers = {
            'ibm-mq-rest-csrf-token': 'value',
        }

        auth = httpx.BasicAuth(username=USER, password=PASSWORD)

        with httpx.Client(verify=False) as client:
            response = client.get(url, headers=headers, auth=auth, timeout=30.0)
            response.raise_for_status()

            data = response.json()
            return data.get('queue', {}).get('currentDepth', 0)
    except Exception as e:
        print(f"Warning: Could not get queue depth: {e}")
        return None

def get_message(destructive=True):
    """
    Get a message from the MQ queue using REST API

    Args:
        destructive: If True, removes message from queue. If False, this
                    operation is not supported by REST messaging API v2.

    Returns:
        Message text if successful, None otherwise
    """
    try:
        # Construct URL
        url = f"{MQ_REST_BASE}/qmgr/{QM_NAME}/queue/{QUEUE_NAME}/message"

        # Set up headers
        headers = {
            'ibm-mq-rest-csrf-token': 'value',
        }

        # Set up authentication
        auth = httpx.BasicAuth(username=USER, password=PASSWORD)

        print("=" * 60)
        print("MQ Message Reader - Get Message from Queue (REST API)")
        print("=" * 60)
        print(f"Queue Manager: {QM_NAME}")
        print(f"Queue: {QUEUE_NAME}")
        print(f"REST API: {MQ_REST_BASE}")
        print("=" * 60)
        print()

        # Get queue depth first
        depth = get_queue_depth()
        if depth is not None:
            print(f"Current queue depth: {depth}")
            if depth == 0:
                print("No messages on the queue")
                return None
        print()

        # Get the message
        print("Retrieving message...")

        with httpx.Client(verify=False) as client:
            response = client.delete(
                url,
                headers=headers,
                auth=auth,
                timeout=30.0
            )

            if response.status_code == 204:
                print("\nNo messages available on the queue")
                return None

            response.raise_for_status()

            # Get message text
            message_text = response.text

            print("\n" + "=" * 60)
            print("MESSAGE RECEIVED")
            print("=" * 60)
            print(f"Message: {message_text}")

            # Display message properties from headers
            if 'ibm-mq-md-messageId' in response.headers:
                print(f"Message ID: {response.headers['ibm-mq-md-messageId']}")
            if 'ibm-mq-md-correlationId' in response.headers:
                print(f"Correlation ID: {response.headers['ibm-mq-md-correlationId']}")
            if 'ibm-mq-md-format' in response.headers:
                print(f"Format: {response.headers['ibm-mq-md-format']}")
            if 'ibm-mq-md-priority' in response.headers:
                print(f"Priority: {response.headers['ibm-mq-md-priority']}")

            print("=" * 60)

            return message_text

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print("\n✗ Queue not found or no messages available")
        else:
            print(f"✗ HTTP Error: {e.response.status_code}")
            print(f"Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None

def get_all_messages():
    """
    Get all messages from the queue

    Returns:
        List of messages
    """
    messages = []
    count = 0

    print("Retrieving all messages from queue...")
    print("=" * 60)

    while True:
        # We need to create a new session for each message
        message = get_message(destructive=True)
        if message is None:
            break
        count += 1
        messages.append(message)
        print(f"\n✓ Message {count} retrieved")
        print("-" * 60)

    print(f"\nTotal messages retrieved: {count}")
    return messages

def main():
    """Main function"""
    # Check command line arguments
    mode = 'single'
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--all', '-a']:
            mode = 'all'
        elif sys.argv[1] in ['--help', '-h']:
            print("Usage:")
            print("  python mq_get_message.py          # Get one message (destructive)")
            print("  python mq_get_message.py --all    # Get all messages (destructive)")
            print()
            print("Note: REST messaging API v2 only supports destructive reads.")
            print("      Browse mode is not available via REST API.")
            return

    # Get messages based on mode
    if mode == 'all':
        messages = get_all_messages()

        if messages:
            print("\n" + "=" * 60)
            print(f"SUCCESS - Retrieved {len(messages)} message(s)")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("No messages found on queue")
            print("=" * 60)
    else:
        message = get_message(destructive=True)

        if message:
            print("\n" + "=" * 60)
            print("SUCCESS - Message retrieved")
            print("=" * 60)

if __name__ == "__main__":
    main()
