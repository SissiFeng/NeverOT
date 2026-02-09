"""
USB Relay Controller for SainSmart 16-channel relay module
Manages relay switching for electrochemical cell selection
"""
import logging
import time
try:
    import serial
except ImportError:
    serial = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)


class RelayController:
    """
    Controller for SainSmart USB 16-channel relay module
    Controls which electrochemical cell is connected to the potentiostat
    """

    def __init__(self, port: str, baudrate: int = 9600, timeout: int = 1):
        """
        Initialize relay controller

        Args:
            port: COM port for the relay (e.g., 'COM11')
            baudrate: Communication baudrate (default: 9600)
            timeout: Serial timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.device = None
        self.current_active_channel = None

        # Connect to relay
        self._connect()

    def _connect(self):
        """Establish connection to the relay device"""
        try:
            self.device = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            time.sleep(2)  # Allow device to initialize
            LOGGER.info(f"Successfully connected to SainSmart USB Relay on {self.port}")

            # Initialize all relays to OFF state
            self.deactivate_all()

        except serial.SerialException as e:
            LOGGER.error(f"Could not connect to USB Relay on port {self.port}. {e}")
            LOGGER.warning("Relay control will be disabled.")
            self.device = None

    def _send_command(self, channel_zero_indexed: int, state: bool) -> bool:
        """
        Send command to control a single relay

        Args:
            channel_zero_indexed: Channel number (0-15)
            state: True to turn ON, False to turn OFF

        Returns:
            True if command sent successfully, False otherwise
        """
        if not self.device or not self.device.is_open:
            LOGGER.error("Relay device is not connected. Cannot send command.")
            return False

        if not (0 <= channel_zero_indexed <= 15):
            LOGGER.warning(f"Relay channel {channel_zero_indexed} is out of range (0-15).")
            return False

        try:
            # Build command packet
            header_val = 0xFE  # Start byte
            cmd_val = 0x05     # Command for single relay control
            addr_val = 0x00    # Address
            channel_val = channel_zero_indexed
            value_high_val = 0xFF if state else 0x00
            value_low_val = 0x00

            # Calculate checksum
            checksum_sum = (header_val + cmd_val + addr_val + channel_val +
                           value_high_val + value_low_val)
            checksum_val = (256 - (checksum_sum % 256)) % 256

            # Format command string
            command_str = (
                f":FE{cmd_val:02X}{addr_val:02X}{channel_val:02X}"
                f"{value_high_val:02X}{value_low_val:02X}{checksum_val:02X}\r\n"
            )

            action = "ON" if state else "OFF"
            # Note: Channel 0 = Relay 1 in documentation
            LOGGER.info(
                f"Sending command (Relay {channel_zero_indexed + 1} {action}): {command_str.strip()}",
                extra={"step_id": f"relay_{channel_zero_indexed+1}_{action.lower()}"}
            )

            # Send command
            self.device.write(command_str.encode('ascii'))

            # Read response
            time.sleep(0.1)
            response = self.device.readline().decode('ascii').strip()
            LOGGER.info(f"Relay response: {response}", extra={"step_id": "relay_response"})

            return True

        except Exception as e:
            LOGGER.error(f"Error sending relay command: {e}")
            return False

    def activate_channel(self, channel: int) -> bool:
        """
        Turn on a specific relay channel

        Args:
            channel: Channel number (0-15)

        Returns:
            True if successful
        """
        return self._send_command(channel, state=True)

    def deactivate_channel(self, channel: int) -> bool:
        """
        Turn off a specific relay channel

        Args:
            channel: Channel number (0-15)

        Returns:
            True if successful
        """
        return self._send_command(channel, state=False)

    def deactivate_all(self) -> bool:
        """
        Turn off all relay channels

        Returns:
            True if all channels deactivated successfully
        """
        if not self.device or not self.device.is_open:
            logging.error("Relay device is not connected. Cannot deactivate all.")
            return False

        logging.info("Setting all relays to OFF state...")
        success = True

        for i in range(16):
            if not self._send_command(i, state=False):
                success = False
            time.sleep(0.05)  # Small delay between commands

        if success:
            logging.info("All relays are off.")
            self.current_active_channel = None

        return success

    def switch_to_channel(self, channel: int) -> bool:
        """
        Switch active relay to a specific channel
        Automatically deactivates previously active channel

        Args:
            channel: Channel number to activate (0-15)

        Returns:
            True if successful
        """
        if not (0 <= channel <= 15):
            logging.warning(f"Channel {channel} is out of range (0-15).")
            return False

        if not self.device or not self.device.is_open:
            logging.error("Relay device is not connected. Cannot switch channel.")
            return False

        # Deactivate previous channel if different
        if self.current_active_channel is not None and self.current_active_channel != channel:
            logging.info(f"Deactivating previous channel: {self.current_active_channel} (Relay {self.current_active_channel + 1})")
            self.deactivate_channel(self.current_active_channel)
        elif self.current_active_channel == channel:
            logging.info(f"Channel {channel} (Relay {channel + 1}) is already the active channel.")
            return True

        # Activate new channel
        logging.info(f"Activating new channel: {channel} (Relay {channel + 1})")
        success = self.activate_channel(channel)

        if success:
            self.current_active_channel = channel

        return success

    def get_active_channel(self) -> int:
        """
        Get the currently active relay channel

        Returns:
            Active channel number (0-15) or None if no channel active
        """
        return self.current_active_channel

    def is_connected(self) -> bool:
        """
        Check if relay device is connected

        Returns:
            True if connected
        """
        return self.device is not None and self.device.is_open

    def close(self):
        """Close connection to relay device"""
        if self.device and self.device.is_open:
            logging.info("Closing connection, turning all relays off.")
            self.deactivate_all()
            self.device.close()
            logging.info("USB Relay connection closed.")
