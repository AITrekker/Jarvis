"""
Debug UI Elements

This module provides UI elements for debug information display.
"""
import os
import sys
import threading
import itertools
import time

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_banner():
    """Display ASCII art banner."""
    banner = """
       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
       ██║███████║██████╔╝██║   ██║██║███████╗
  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
                                                
  AI-Powered Voice Intelligence Platform
    """
    print(banner)

def loading_animation(stop_event):
    """Display a simple loading animation until stop_event is set.
    
    Args:
        stop_event (threading.Event): Event to signal animation should stop
    """
    spinner = itertools.cycle(['-', '/', '|', '\\'])
    while not stop_event.is_set():
        sys.stdout.write('\rInitializing Jarvis ' + next(spinner))
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write('\r                      \r')