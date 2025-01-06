# Slot Bot

Welcome to **Slot Bot**, the ultimate solution for managing and selling slots on your server! Designed with advanced features and a user-friendly interface, this bot makes slot management effortless and efficient.

## Key Features

- **Advanced Slot Management**: Easily create, hold, unhold, and revoke slots.
- **Ownership Transfer**: Seamlessly transfer slot ownership between users.
- **Slot Renewal and Recovery**: Extend slot durations and recover slots as needed.
- **Detailed Slot Information**: Get comprehensive details about slots and their ownership.
- **Automated Slot Operations**: Includes commands for auto-pinging, slot cleanup, and more.

## Commands

### `/create_slot`
Create a new slot with advanced options including duration and ping settings.

### `/hold`
Temporarily hold a slot to prevent it from being purchased.

### `/unhold`
Make a held slot available for purchase again.

### `/revoke`
Revoke a slot, making it unavailable for future use.

### `/transfer`
Transfer slot ownership to another user, updating all relevant details.

### `/renew`
Extend the duration of an existing slot for any user.

### `/slot_info`
Retrieve detailed information about a slot, including its owner and status.

### `/recovery`
Recreate and assign permissions for a slot at the time of termination.

### `/delete_slot`
Permanently delete revoked slots and their associated data.

## Installation

1. **Download the Bot**: Obtain the bot files from the provided source.
2. **Set Up Your Environment**: Ensure you have Python installed and set up a virtual environment if desired.
3. **Install Dependencies**:

    Create a `requirements.txt` file with the following libraries:

    ```txt
    discord.py
    configparser
    pytz
    ```

    Install the dependencies using:

    ```bash
    pip install -r requirements.txt
    ```

4. **Configure the Bot**: Update the configuration file with your bot token and other settings as needed.

5. **Run the Bot**:

    ```bash
    python bot.py
    ```

## Support

Join Our Discord And Create A Ticket For Futher Support. https://discord.gg/AfTYsj7tU9

## License

This software is intended for personal use only. Redistribution or commercial use is not permitted.

## Author 
 
Created By FadedSoul & Yesh

**Thank you for choosing Slot Bot! We hope it enhances your server’s slot management experience.** 🚀
