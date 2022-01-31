from socket import timeout
import serial as pyserial
import cv2
import numpy as np
import mss
import mss.tools
import matplotlib.pyplot as plt
import time
# for OCR
import pytesseract
import random
import threading

mode = 'm'
fields = []

class Sides:
    FRONT = 0
    LEFT = 1
    RIGHT = 2
    BACK = 3


def get_input():
    global mode
    while True:
        user_input = input("Enter mode: m (matches), d (decorative)")
        if user_input == 'm' or user_input == 'd':
            mode = user_input

def send_colors_to_pixels(ser, pixel_range, colors_dict, delay=0.015):
    # write colors in order as string
    color_str = str(colors_dict['r'] + 1) + " " + str(colors_dict['g'] + 1) + " " + str(colors_dict['b'] + 1)
    send_str = 'x' + str(pixel_range[0] + 1) + " " + str(pixel_range[1] + 1) + " " + color_str + 'y'
    print(send_str)
    ser.write(bytes(send_str, 'utf-8'))
    time.sleep(delay)

class FieldLED():
    # A setup of 450 LEDs arranged in a square
    def __init__(self, port, baudrate, field_name, corner_indices, total_lights=15*30):
        self.ser = pyserial.Serial(port, baudrate)
        self.field_name = field_name
        self.corner_indices = corner_indices
        self.total_lights = total_lights

    def index_to_pos(self, indices):
        return (indices + self.corner_indices[0]) % self.total_lights


if __name__ == '__main__':
    # new thread for get_input
    get_input_thread = threading.Thread(target=get_input)
    get_input_thread.start()

    ser = pyserial.Serial(port='/dev/cu.usbmodem14301', baudrate=230400)
    while True:
        time.sleep(4)
        send_colors_to_pixels(ser, (0, 100), {'r': 5, 'g': 5, 'b': 105}, delay=0.1)
        time.sleep(1)
        # create new serial
        send_colors_to_pixels(ser, (0, 1), {'r': 255, 'g': 255, 'b': 255}, delay=2)
        send_colors_to_pixels(ser, (0, 100), {'r': random.randint(0, 256), 'g': random.randint(0, 256), 'b': random.randint(0, 256)}
            , delay=0.015)
        time.sleep(3)