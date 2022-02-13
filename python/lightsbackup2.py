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
from threading import Thread, Lock


cur_field = None
mode = 'm'
just_switched = False
fields = ['bb-8', 'c-3po']
# note: these must be one word each

timer_lock = Lock()
ret_field = None
ret_time = None
ret_mode = None
last_match_info_fetch_time = 0

class Sides:
    FRONT = 0
    LEFT = 1
    RIGHT = 2
    BACK = 3

def get_input():
    global mode, just_switched
    while True:
        user_input = input("Enter mode: m (matches), r (rainbow), c (red-blue chase): ")
        if user_input in ['m', 'p', 'tr', 'tb', 'r', 'c']:
            mode = user_input
            just_switched = True

def send_str(ser, str, delay=0.015, num_times=25):
    print("Sending " + str)
    # print stack trace
    for _ in range(num_times):
        ser.write(bytes(str, 'utf-8'))
        time.sleep(delay)

def send_colors_to_pixels(ser, pixel_range, colors, delay=0.015):
    if ser is None:
        time.sleep(delay)
        return
    colors = colors.astype(int)
    # write colors in order as string
    color_str = str(colors[0] + 1) + " " + str(colors[1] + 1) + " " + str(colors[2] + 1)
    send_str = 'x1 ' + str(pixel_range[0] + 1) + " " + str(pixel_range[1] + 1) + " " + color_str + 'yz'
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

    plt.imshow(img, cmap='gray')
    plt.savefig("screenshot.png")

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

def match_info_ocr_thread():
    global ret_field, ret_time, ret_mode, last_match_info_fetch_time
    while True:
        secs_left, match_status, match_field = get_match_info_with_ocr()
        print(secs_left, match_status, match_field)
        if secs_left is not None:
            with timer_lock:
                ret_field = match_field
                ret_time = secs_left
                ret_mode = match_status
                last_match_info_fetch_time = time.time()
        time.sleep(0.1)

class FieldLED():
    # A setup of 450 LEDs arranged in a square
    def __init__(self, port, baudrate, field_name, corner_indices, total_lights=15*30):
        self.ser = None #pyserial.Serial(port, baudrate)
        self.field_name = field_name
        self.corner_indices = corner_indices
        self.total_lights = total_lights
        self.secs, self.whole_secs, self.match_mode, self.field, self.rate, self.prev_get_info_time = 15, 15, None, None, 0, 0
        self.light_states = np.zeros((total_lights, 3), dtype=int)
    
    def clear(self):
        send_colors_to_pixels(self.ser, (0, self.total_lights), np.array([0, 0, 0]))

    def get_match_info(self):
        call_time = time.time()
        field = None
        td = call_time - self.prev_get_info_time
        self.prev_get_info_time = call_time
        with timer_lock:
            lmf = last_match_info_fetch_time
        if call_time - lmf > 0.1:
            with timer_lock:
                secs_recvd, mode, field = ret_time, ret_mode, ret_field
            if secs_recvd is not None:
                self.whole_secs = secs_recvd
                self.rate = (self.secs - secs_recvd) / 1 + 1.5
                if mode is not None and mode != self.match_mode:
                    self.secs = secs_recvd
                    self.rate = 0
                self.match_mode = mode if mode is not None else self.match_mode
        self.secs = self.secs - self.rate * td
        return (self.secs, self.match_mode, field)

    def display_pixels(self, new_light_states, diff=True):
        new_light_states = np.array(new_light_states).astype(int)
        # find differences between adjacent pixels
        diffs = np.abs(np.diff(new_light_states, axis=0, prepend=0) != 0).sum(axis=-1)
        if not diff:
            delta_nonzero_zero_breaks = np.subtract(new_light_states, self.light_states) != 0
            delta = np.abs(np.diff(delta_nonzero_zero_breaks, axis=0, prepend=0)).sum(axis=-1)
            # extract contiguous ranges of equal values
            diffs_with_delta = (diffs + delta) > 0
            interval_boundaries = np.nonzero(diffs_with_delta)[0].tolist()
        else:
            interval_boundaries = np.nonzero(diffs)[0].tolist()

        if len(interval_boundaries) == 0 or interval_boundaries[0] != 0:
            interval_boundaries.insert(0, 0)
        if interval_boundaries[-1] != len(diffs) - 1:
            interval_boundaries.append(len(diffs) - 1)

        for i, boundary in enumerate(interval_boundaries[:-1]):
            cur_interval = (interval_boundaries[i], interval_boundaries[i+1])
            cur_start = interval_boundaries[i]
            if not diff or np.linalg.norm(new_light_states[cur_start] - self.light_states[cur_start]) > 0:
                send_colors_to_pixels(self.ser, cur_interval, new_light_states[cur_start])

        self.light_states = new_light_states

    def display_time(self, time_cur, mode):
        state = np.zeros((self.total_lights, 3))
        timer_bounds = [0, 100]
        state[timer_bounds[0]: timer_bounds[1]] = [100, 0, 100]
        tot_time_for_mode = 105 if mode == 'driver' else 15
        tot_time_for_mode -= 3
        fraction = (time_cur - 1.5) / tot_time_for_mode
        fraction = max(min(fraction, 1), 0)

        divider_location = timer_bounds[1] * fraction
        state[timer_bounds[0]:int(divider_location) + 1] = [255, 255, 255]
        # interpolate colors near divider
        frac = (divider_location - int(divider_location))
        state[int(divider_location)] = [255*frac + 100*(1-frac), 255*frac, 255*frac + 100*(1-frac)]

        if mode == 'driver' and abs(fraction - 30/105) < 0.01:
            black = np.zeros((self.total_lights, 3))
            orange = np.zeros((self.total_lights, 3))
            orange[timer_bounds[0]: timer_bounds[1]] = [255, 165, 0]
            self.display_pixels(orange, diff=False)
            time.sleep(0.2)
            self.display_pixels(black, diff=False)
            time.sleep(0.2)
            self.display_pixels(orange, diff=False)
            time.sleep(0.2)
        elif abs(fraction - 0/105) < 0.01:
            black = np.zeros((self.total_lights, 3))
            red = np.zeros((self.total_lights, 3))
            red[timer_bounds[0]: timer_bounds[1]] = [255, 0, 0]
            self.display_pixels(red, diff=False)
            time.sleep(0.2)
            self.display_pixels(black, diff=False)
            time.sleep(0.2)
            self.display_pixels(red, diff=False)
            time.sleep(0.2)
        else:
            self.display_pixels(state, diff=False)
        
    def initialize_red_blue_lights(self):
        # new_state = np.zeros((self.total_lights, 3))
        # new_state[self.corner_indices[0]:self.corner_indices[1]] = [255, 0, 0]
        # new_state[self.corner_indices[1]:self.corner_indices[2]] = [0, 0, 255]
        # new_state[self.corner_indices[2]:self.corner_indices[3]] = [255, 0, 0]
        # new_state[self.corner_indices[3]:] = [0, 0, 255]

        # self.display_pixels(new_state)
        time.sleep(0.04)
    
    def rotate_lights(self, clockwise=False):
        if clockwise:
            indices = np.roll(self.light_states.copy(), -1, axis=0)
        else:
            indices = np.roll(self.light_states.copy(), 1, axis=0)

        self.display_pixels(indices)
    
    def initialize_red_blue_dim_sides(self):
        # initialize red and blue sides
        send_str(self.ser, 'x2 56 281yz')
        send_str(self.ser, 'x3 56 281yz')

        # self.display_pixels(new_state)
        time.sleep(0.04)

    def throb(self, red=True):
        n = 4 if red else 5
        send_str(self.ser, f'x{n} 56 281yz')

    def rainbow(self):
        send_str(self.ser, 'x6 56 281yz')

    def chase(self):
        send_str(self.ser, 'x7 56 281yz')

    def index_to_pos(self, indices):
        return (indices + self.corner_indices[0]) % self.total_lights


def old_main():
    get_input_thread = threading.Thread(target=get_input)
    get_input_thread.start()

    field = FieldLED('/dev/cu.usbmodem14301', 19200, 'main', [0, 450//4, 450//2, 450*3//4], total_lights=15*30)

    time.sleep(4)
    field.clear()

    # start match info thread
    match_info_thread = threading.Thread(target=match_info_ocr_thread)
    match_info_thread.start()

    while True:
        if mode == 'm':
            # send_colors_to_pixels(ser, (0, 100), np.array([244, 5, 0 + int(mode=='m')*200]), delay=0.05)
            time_remaining, match_mode, field_name = field.get_match_info()
            field.display_time(time_remaining, match_mode)
        elif mode == 'd':
            if just_switched:
                field.initialize_red_blue_lights()
                just_switched = False
        elif mode == 'p':
            if just_switched:
                field.initialize_red_blue_dim_sides()
                just_switched = False
        elif mode == 'tr':
            if just_switched:
                field.throb(red=True)
                just_switched = False
        elif mode == 'tb':
            if just_switched:
                field.throb(red=False)
                just_switched = False
        elif mode == 'r':
            if just_switched:
                field.rainbow()
                just_switched = False
        time.sleep(0.04)

def field_with_name(field_list, name):
    for field in field_list:
        if similar_words(field.name, name):
            return field
    return None

if __name__ == '__main__':
    # new thread for get_input
    get_input_thread = threading.Thread(target=get_input)
    get_input_thread.start()

    field = FieldLED('/dev/cu.usbmodem14201', 19200, 'main', [0, 450//4, 450//2, 450*3//4], total_lights=15*30)
    time.sleep(4)
    # clear fields
    field.clear()

    # start match info thread
    match_info_thread = threading.Thread(target=match_info_ocr_thread)
    match_info_thread.start()

    while True:
        if mode == 'm':
            # send_colors_to_pixels(ser, (0, 100), np.array([244, 5, 0 + int(mode=='m')*200]), delay=0.05)
            time_remaining, match_mode, field_name = field.get_match_info()
            field.display_time(time_remaining, match_mode)
        elif mode == 'd':
            if just_switched:
                field.initialize_red_blue_lights()
                just_switched = False
        elif mode == 'p':
            if just_switched:
                field.initialize_red_blue_dim_sides()
                just_switched = False
        elif mode == 'tr':
            if just_switched:
                field.throb(red=True)
                just_switched = False
        elif mode == 'tb':
            if just_switched:
                field.throb(red=False)
                just_switched = False
        elif mode == 'r':
            if just_switched:
                field.rainbow()
                just_switched = False
        elif mode == 'c':
            field.chase()
        elif mode == 'o':
            field.off()
        time.sleep(0.04)