
import can
import sys
import time
bus = None

try:
    # Initialize CAN bus
    bus = can.interface.Bus(
        channel='/dev/ttyUSB0',
        interface='slcan',
        bitrate=250000
    )

    print("Listening for ALL CAN messages... (Press Ctrl+C to stop)\n")
    

    while True:
        message = bus.recv(timeout=1.0)

        if message:
            data_hex = ' '.join(f'{byte:02X}' for byte in message.data)

            print(f"ID: {hex(message.arbitration_id)} | DLC: {message.dlc} | DATA: {data_hex}")
            # time.sleep(1)  # Add a small delay to prevent flooding the console    

# Handle Ctrl+C
except KeyboardInterrupt:
    print("\nInterrupt received. Shutting down CAN bus...")

# Handle other errors
except Exception as e:
    print(f"\nError: {e}")

finally:
    if bus is not None:
        try:
            bus.shutdown()
            print("CAN bus shut down successfully.")
        except Exception as e:
            print(f"Error during shutdown: {e}")

    sys.exit(0)