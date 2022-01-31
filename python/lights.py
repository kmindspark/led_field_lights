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
import nltk

cur_field = None

mode = 'm'
# note: these must be one word each
fields = ['main']

class Sides:
    FRONT = 0
    LEFT = 1
    RIGHT = 2
    BACK = 3

def get_input():
    global mode
    while True:
        user_input = input("Enter mode: m (matches), d (decorative): ")
        if user_input == 'm' or user_input == 'd':
            mode = user_input

def send_colors_to_pixels(ser, pixel_range, colors, delay=0.015):
    colors = colors.astype(int)
    # write colors in order as string
    color_str = str(colors[0] + 1) + " " + str(colors[1] + 1) + " " + str(colors[2] + 1)
    send_str = 'x' + str(pixel_range[0] + 1) + " " + str(pixel_range[1] + 1) + " " + color_str + 'y'
    print(send_str)
    ser.write(bytes(send_str, 'utf-8'))
    time.sleep(delay)

def similar_words(w1, w2):
    # levenshtein distance
    return nltk.edit_distance(w1.lower(), w2.lower()) <= 1

def process_img(img, high_contrast=False):
    img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    if high_contrast:
        gray, img_bin = cv2.threshold(img,220,255,cv2.THRESH_BINARY) # | cv2.THRESH_OTSU
    else:
        gray, img_bin = cv2.threshold(img,127,255,cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    gray = cv2.bitwise_not(img_bin)
    kernel = np.ones((2, 1), np.uint8)
    img = cv2.erode(gray, kernel, iterations=1)
    img = cv2.dilate(img, kernel, iterations=1)
    img = cv2.resize(img, (0, 0), fx=0.5, fy=0.5)
    return img  

def get_match_info_with_ocr():
    with mss.mss() as sct:
        # The screen part to capture
        region = {'top': 30, 'left': 150, 'width': 200, 'height': 450}
        # Grab the data
        myScreenshot = sct.grab(region)
    # convert image to numpy
    orig_img = np.array(myScreenshot)
    img = process_img(orig_img)

    # plt.imshow(img, cmap='gray')
    # plt.show()

    # perform OCR on img
    text = pytesseract.image_to_string(img)
    # for time left, find the numbers on either side of the colon
    try:
        colon_idx = text.index(':')
        mins, secs = int(text[colon_idx-1]), int(text[colon_idx+1:colon_idx+3])
        secs_left = mins * 60 + secs

        # get match status
        match_status = None
        strings = text.split()
        for string in strings:
            if similar_words(string, 'autonomous'):
                match_status = 'autonomous'
                break
            elif similar_words(string, 'driver'):
                match_status = 'driver'
                break
            elif similar_words(string, 'paused'):
                match_status = 'paused'
                break

        # get match field
        match_field = None
        for i, string in enumerate(strings):
            for fname in fields:
                if similar_words(string, fname):
                    match_field = fname
                    break
        if match_field is None:
            img = orig_img[500:-100]
            img = process_img(img, high_contrast=True)
            text = pytesseract.image_to_string(img)
            strings = text.split()
            for i, string in enumerate(strings):
                for fname in fields:
                    if similar_words(string, fname):
                        match_field = fname
                        break
        
        return secs_left, match_status, match_field
    except Exception as e:
        print(e)
        return None, None, None

class FieldLED():
    # A setup of 450 LEDs arranged in a square
    def __init__(self, port, baudrate, field_name, corner_indices, total_lights=15*30):
        self.ser = pyserial.Serial(port, baudrate)
        self.field_name = field_name
        self.corner_indices = corner_indices
        self.total_lights = total_lights
        self.last_match_info_fetch_time = 0
        self.secs, self.whole_secs, self.match_mode, self.field, self.rate, self.prev_get_info_time = 15, 15, None, None, 0, 0
        self.light_states = np.zeros((total_lights, 3))
    
    def clear(self):
        send_colors_to_pixels(self.ser, (0, self.total_lights), np.array([0, 0, 0]))

    def get_match_info(self):
        call_time = time.time()
        field = None
        td = call_time - self.prev_get_info_time
        self.prev_get_info_time = call_time
        if call_time - self.last_match_info_fetch_time > 0.5:
            self.last_match_info_fetch_time = call_time
            secs_recvd, mode, field = get_match_info_with_ocr()
            if secs_recvd is not None:
                self.whole_secs = secs_recvd
                self.rate = (self.secs - secs_recvd) / 1
                self.match_mode = mode if mode is not None else self.match_mode
        self.secs = self.secs - self.rate * td
        return (self.secs, self.match_mode, field)

    def display_pixels(self, new_light_states):
        # find differences between adjacent pixels
        diffs = np.abs(np.diff(new_light_states, axis=0, prepend=0) != 0).sum(axis=-1)
        delta_nonzero_zero_breaks = np.subtract(new_light_states, self.light_states) != 0
        delta = np.abs(np.diff(delta_nonzero_zero_breaks, axis=0, prepend=0)).sum(axis=-1)
        # print("diffs and delta", self.light_states[95:105, :2].tolist(),
        #       new_light_states[95:105, :2].tolist(), diffs[95:105], delta[95:105])
        # extract contiguous ranges of equal values
        diffs_with_delta = (diffs + delta) > 0
        interval_boundaries = np.nonzero(diffs_with_delta)[0].tolist()
        if len(interval_boundaries) == 0 or interval_boundaries[0] != 0:
            interval_boundaries.insert(0, 0)
        if interval_boundaries[-1] != len(diffs_with_delta) - 1:
            interval_boundaries.append(len(diffs_with_delta) - 1)
        # print(interval_boundaries)
        # print(new_light_states[95:105])
        for i, boundary in enumerate(interval_boundaries[:-1]):
            cur_interval = (interval_boundaries[i], interval_boundaries[i+1])
            cur_start = interval_boundaries[i]
            # print(cur_interval, i, interval_boundaries[i])
            if np.linalg.norm(new_light_states[cur_start] - self.light_states[cur_start]) > 0:
                send_colors_to_pixels(self.ser, cur_interval, new_light_states[cur_start])

        self.light_states = new_light_states

    def display_time(self, time, mode):
        state = np.zeros((self.total_lights, 3))
        timer_bounds = [0, 100]
        state[timer_bounds[0]: timer_bounds[1]] = [255, 0, 0]
        tot_time_for_mode = 105 if mode == 'driver' else 15
        fraction = time / tot_time_for_mode
        divider_location = timer_bounds[1] * fraction
        state[timer_bounds[0]:int(divider_location) + 1] = [0, 255, 0]
        # interpolate colors near divider
        frac = (divider_location - int(divider_location))
        state[int(divider_location)] = [255*(1-frac), 255*frac, 0]
        # print(divider_location, state[90:100, :2])
        # print(state[:100])

        self.display_pixels(state)
        

    def index_to_pos(self, indices):
        return (indices + self.corner_indices[0]) % self.total_lights


if __name__ == '__main__':
    # new thread for get_input
    get_input_thread = threading.Thread(target=get_input)
    get_input_thread.start()

    field = FieldLED('/dev/cu.usbmodem14301', 230400, 'main', [0, 100], total_lights=15*30)
    time.sleep(4)
    field.clear()
    while True:
        if mode == 'm':
            # send_colors_to_pixels(ser, (0, 100), np.array([244, 5, 0 + int(mode=='m')*200]), delay=0.05)
            time_remaining, match_mode, field_name = field.get_match_info()
            field.display_time(time_remaining, match_mode)
            time.sleep(0.1)