import logging
import constants
import requests
import tkinter as tk

class CustomLogger:
    def __init__(self, filename, equity):
        self.logger = logging.getLogger('custom_logger')
        self.logger.setLevel(logging.DEBUG)
        self.filename = filename

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        file_handler = logging.FileHandler(f'logs/{equity}_logs.log')  # Fix: changed filename to 'logs.log'
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def log_message(self, level, message):
        filename = self.filename
        # Include filename in the log message
        message_with_filename = f"{filename} - {message}"

        if level == 'debug':
            self.logger.debug(message_with_filename)
        elif level == 'info':
            self.logger.info(message_with_filename)
        elif level == 'warning':
            self.logger.warning(message_with_filename)
        elif level == 'error':
            self.logger.error(message_with_filename)
        elif level == 'critical':
            self.logger.critical(message_with_filename)
        else:
            print("Invalid log level")




# Telegram Bot Messenger

class TelegramBot:
    def __init__(self):
        self.token = constants.TELEGRAM_BOT_TOKEN
        self.chat_id = constants.TRENDLINES_CHAT_ID

    def send_message(self, message):
        try:
            url=f"https://api.telegram.org/bot{self.token}/sendMessage?chat_id={self.chat_id}&text={message}"
            if not requests.get(url).json()['ok']:
                raise Exception("Failed to send message on Telegram")
        except Exception as e:
            print(e)


# Confirmation Popup

class ConfirmationPopup:
    def __init__(self, root, message, title="Confirmation"):
        self.root = root
        self.message = message
        self.title = title
        self.popup = None
        self.result = None

    def show(self):
        # Create the pop-up window
        self.popup = tk.Toplevel(self.root)
        self.popup.title(self.title)

        # Set up the message
        label = tk.Label(self.popup, text=self.message)
        label.pack(pady=20)

        # Set up the buttons
        yes_button = tk.Button(self.popup, text="Yes", command=self.yes_action)
        yes_button.pack(side="left", padx=20, pady=20)

        no_button = tk.Button(self.popup, text="No", command=self.no_action)
        no_button.pack(side="right", padx=20, pady=20)

        # Center the popup on the screen
        self.popup.geometry("300x150+%d+%d" % (self.root.winfo_screenwidth() / 2 - 150, self.root.winfo_screenheight() / 2 - 75))

        # Start the Tkinter main loop, which will block further code execution until the window is closed
        self.root.mainloop()
        return self.result

    def yes_action(self):
        self.result = "Yes"
        print("You clicked Yes!")
        self.popup.destroy()
        self.root.quit()

    def no_action(self):
        self.result = "No"
        print("You clicked No!")
        self.popup.destroy()
        self.root.quit()
    
    # function to close the popup
    def close_popup(self):
        self.popup.destroy()
        self.root.quit()