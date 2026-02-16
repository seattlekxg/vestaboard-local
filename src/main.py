#!/usr/bin/env python3
"""Main entry point for Vestaboard Local Automation."""

import sys
from .web import run_server
from .client import VestaboardClient
from .config import config


def test_connection():
    """Test connection to Vestaboard."""
    print("Testing connection to Vestaboard...")
    print(f"  URL: {config.vestaboard_local_url}")

    try:
        client = VestaboardClient()
        if client.test_connection():
            print("  Connection successful!")
            return True
        else:
            print("  Connection failed!")
            return False
    except Exception as e:
        print(f"  Error: {e}")
        return False


def send_test_message():
    """Send a test message."""
    print("Sending test message...")
    try:
        client = VestaboardClient()
        success = client.send_message("Hello from Vestaboard Local!")
        if success:
            print("  Test message sent!")
        else:
            print("  Failed to send test message")
        return success
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "test":
            success = test_connection()
            sys.exit(0 if success else 1)

        elif command == "send":
            if len(sys.argv) < 3:
                print("Usage: python -m src.main send 'Your message here'")
                sys.exit(1)
            message = " ".join(sys.argv[2:])
            client = VestaboardClient()
            success = client.send_message(message)
            sys.exit(0 if success else 1)

        elif command == "hello":
            success = send_test_message()
            sys.exit(0 if success else 1)

        else:
            print(f"Unknown command: {command}")
            print("Available commands: test, send, hello")
            print("Or run without arguments to start the web server")
            sys.exit(1)

    # Validate configuration
    if not config.vestaboard_local_url:
        print("Error: VESTABOARD_LOCAL_URL not configured")
        print("Please set this environment variable to your Vestaboard's local API URL")
        sys.exit(1)

    if not config.vestaboard_local_key:
        print("Error: VESTABOARD_LOCAL_KEY not configured")
        print("Please set this environment variable to your Vestaboard's local API key")
        sys.exit(1)

    print("=" * 50)
    print("Vestaboard Local Automation")
    print("=" * 50)
    print(f"Vestaboard URL: {config.vestaboard_local_url}")
    print(f"Web server: http://{config.web_host}:{config.web_port}")
    print("=" * 50)

    # Start the web server (which also starts the scheduler)
    run_server()


if __name__ == "__main__":
    main()
