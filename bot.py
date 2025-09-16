import time
import pyautogui
import cv2
import numpy as np
import pytesseract
from datetime import datetime

# path to your icons (from the pack I made you)
ICON_CAMERA_OFF = "cam_off_dark.png"
ICON_CAMERA_OFF_LIGHT = "cam_off_light.png"

# dictionary to store timers for each guest
guest_timers = {}

def locate_icon(image_path, confidence=0.8):
    """Locate image on screen using pyautogui"""
    try:
        location = pyautogui.locateOnScreen(image_path, confidence=confidence)
        return location
    except Exception:
        return None

def click_icon(image_path, confidence=0.8):
    """Click an icon if found"""
    location = locate_icon(image_path, confidence)
    if location:
        pyautogui.click(pyautogui.center(location))
        return True
    return False

def ask_to_start_video(user_position):
    """Right-click guest -> Ask to Start Video"""
    pyautogui.rightClick(user_position)
    time.sleep(0.5)
    # Search menu for "Ask to Start Video"
    # Here OCR is more reliable than image
    # (you can also use an image for the menu option)
    pyautogui.typewrite("Ask to Start Video")  
    pyautogu
