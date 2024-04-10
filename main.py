import threading
import os
import sys
import subprocess


def start_bot():
    os.system("python dcbot.py")

def start_flask_app():
    os.system("python app.py")

if __name__ == "__main__":
    # Running Flask app
    flask_thread = threading.Thread(target=start_flask_app)
    flask_thread.start()

    # Running Discord bot
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.start()

