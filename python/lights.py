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
mode = 'r'
just_switched = False
# note: these must be one word each

timer_lock = Lock()
ret_field = None
ret_time = None
ret_mode = None
last_match_info_fetch_time = 0

secs, whole_secs, match_mode, field, rate, prev_get_info_time = 15, 15, None, None, 0, 0

class Sides:
    FRONT = 0
    LEFT = 1
    RIGHT = 2
    BACK = 3

def get_match_info():
    global prev_get_info_time, whole_secs, rate, secs, match_mode, field
    call_time = time.time()
    field = None
    prev_get_info_time = call_time
    with timer_lock:
        secs_recvd, mode, field = ret_time, ret_mode, ret_field
    if secs_recvd is not None:
        whole_secs = secs_recvd
        match_mode = mode if mode is not None else match_mode
    return (whole_secs, match_mode, field)

def get_input():
    global mode, just_switched
    while True:
        user_input = input("Enter mode: m (matches), r (rainbow), c (red-blue chase), s (field split), b (bright pulsing field split) l (calibrate), o (off): ")
        if user_input in ['m', 'r', 'c', 's', 'b', 'l', 'o']:
            mode = user_input
            just_switched = True

def send_str(ser, str, delay=0.015, num_times=4):
    for _ in range(num_times):
        if ser is not None:
            ser.write(bytes(str, 'utf-8'))
            print(str)
        time.sleep(delay)

def send_colors_to_pixels(ser, pixel_range, colors, delay=0.015):
    if ser is not None:
        colors = colors.astype(int)
        # write colors in order as string
        color_str = str(colors[0] + 1) + " " + str(colors[1] + 1) + " " + str(colors[2] + 1)
        send_str = 'x1 ' + str(pixel_range[0] + 1) + " " + str(pixel_range[1] + 1) + " " + color_str + 'yz'
        print(send_str)
        ser.write(bytes(send_str, 'utf-8'))
    time.sleep(delay)

def similar_words(w1, w2):
    # levenshtein distance
    return nltk.edit_distance(w1.lower(), w2.lower()) <= 2

def process_img(img, high_contrast=False):
    img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    if high_contrast:
        gray, img_bin = cv2.threshold(img,220,255,cv2.THRESH_BINARY) # | cv2.THRESH_OTSU
    else:
        gray, img_bin = cv2.threshold(img,127,255,cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    gray = img_bin #cv2.bitwise_not(img_bin)
    kernel = np.ones((2, 1), np.uint8)
    img = cv2.erode(gray, kernel, iterations=1)
    img = cv2.dilate(img, kernel, iterations=1)
    # img = cv2.resize(img, (0, 0), fx=0.5, fy=0.5)
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
    # plt.savefig("screenshot.png")

    # perform OCR on img
    text = pytesseract.image_to_string(img, config='--psm 11')
    # for time left, find the numbers on either side of the colon
    try:
        colon_idx = text.index(':')
        mins, secs = int(text[colon_idx-1]), int(text[colon_idx+1:colon_idx+3])
        secs_left = mins * 60 + secs

        # get match status
        match_status = "autonomous"
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

        # if not (match_status is None and match_status == 'autonomous'):
        #     match_status = match_status           

        # get match field
        match_field = None
        for i, string in enumerate(strings):
            match_field = match_field or field_with_name(fields, string)[1]
        if match_field is None:
            img = orig_img[500:-100]
            img = process_img(img, high_contrast=True)[140:170, 120:250]
            # plt.imshow(img, cmap='gray')
            # plt.savefig("screenshot-sub.png")
            text = pytesseract.image_to_string(img, config='--psm 6')
            strings = text.split()
            for i, string in enumerate(strings):
                match_field = match_field or field_with_name(fields, string)[1]
        
        return secs_left, match_status, match_field
    except Exception as e:
        print(e)
        return None, None, None

def match_info_ocr_thread():
    global ret_field, ret_time, ret_mode, last_match_info_fetch_time
    while True:
        secs_left, match_status, match_field = get_match_info_with_ocr()
        # print(secs_left, match_status, match_field)
        if secs_left is not None:
            with timer_lock:
                ret_field = match_field
                ret_time = secs_left
                ret_mode = match_status
                last_match_info_fetch_time = time.time()
        time.sleep(0.1)

def do_match_info_ocr():
    global ret_field, ret_time, ret_mode, last_match_info_fetch_time
    secs_left, match_status, match_field = get_match_info_with_ocr()
    # print(secs_left, match_status, match_field)
    if secs_left is not None:
        ret_field = match_field
        ret_time = secs_left
        ret_mode = match_status
        last_match_info_fetch_time = time.time()

class FieldLED():
    # A setup of 450 LEDs arranged in a square
    def __init__(self, port, baudrate, field_name, pretend=False):
        self.ser = None if pretend else pyserial.Serial(port, baudrate)
        self.field_name = field_name
        self.name = field_name
    
    def clear(self):
        send_colors_to_pixels(self.ser, (0, self.total_lights), np.array([0, 0, 0]))

    def display_time(self, time_cur, mode):
        tot_time = 105 if mode == 'driver' else 15
        send_str(self.ser, f'x0 {time_cur} {tot_time}yz')

    def initialize_red_blue_osc(self):
        send_str(self.ser, 'x4yz', num_times=5)

    def rainbow(self):
        send_str(self.ser, 'x5yz', num_times=7)

    def chase(self):
        send_str(self.ser, 'x6yz', num_times=7)

    def initialize_red_blue_lights(self):
        send_str(self.ser, 'x7yz', num_times=10)
    
    def calibrate(self):
        send_str(self.ser, 'x8yz', num_times=7)
    
    def clear(self):
        send_str(self.ser, 'x9yz', num_times=7)

def match_words(word_list, target, thresh=2):
    # find closest word
    closest_word, closest_dist = None, float('inf')
    for word in word_list:
        dist = nltk.edit_distance(word, target)
        if dist < closest_dist:
            closest_word, closest_dist = word, dist
    if closest_dist > thresh:
        return None
    return closest_word

def field_with_name(field_list, name):
    if name is None:
        return None, None
    field_names = [field.name for field in field_list]
    closest_field = match_words(field_names, name, thresh=2)
    if closest_field is None:
        return None, None
    return field_list[field_names.index(closest_field)], closest_field

if __name__ == '__main__':
    # new thread for get_input
    get_input_thread = threading.Thread(target=get_input)
    get_input_thread.start()

    fields = [FieldLED('/dev/cu.usbmodem141301', 19200, 'Waymo', pretend=False),
    FieldLED('/dev/cu.usbmodem14301', 19200, 'SpaceX', pretend=True),]
    # FieldLED('/dev/cu.usbmodem14401', 19200, 'R2-D2', [0, 450//4, 450//2, 450*3//4], total_lights=15*30)]

    current_field = None

    time.sleep(1)
    # clear fields
    # for field in fields:
    #     field.clear()

    # start match info thread
    # match_info_thread = threading.Thread(target=match_info_ocr_thread)
    # match_info_thread.start()

    while True:
        if mode == 'm':
            if just_switched:
                for field in fields:
                    field.initialize_red_blue_lights()     
                just_switched = False           
            # send_colors_to_pixels(ser, (0, 100), np.array([244, 5, 0 + int(mode=='m')*200]), delay=0.05)
            try:
                print("starting ocr")
                do_match_info_ocr()
                print('ending ocr')
            except:
                pass
            time_remaining, match_mode, field_name = get_match_info()
            current_field_proposal, current_field_name_proposal = field_with_name(fields, field_name)
            print(time_remaining, match_mode, current_field.name if current_field else None)
            if (current_field_name_proposal and (not current_field or current_field_name_proposal != current_field.name)):
                if current_field:
                    print('switching fields, initializing lights for field:', current_field.name)
                    current_field.initialize_red_blue_lights()
                    time.sleep(0.5)
                    current_field.initialize_red_blue_lights()
                current_field, current_field_name = current_field_proposal, current_field_name_proposal
                current_field.initialize_red_blue_lights()
                match_status = "autonomous"
            if current_field is not None and (match_mode in ['driver', 'autonomous', 'paused'] or \
                time_remaining > 0): #and np.absolute((time_remaining - np.array([15, 105]))).min() > 2):
                current_field.display_time(time_remaining, match_mode)
        elif mode == 'r':
            if just_switched:
                for field in fields:
                    field.rainbow()
                just_switched = False
        elif mode == 'c':
            if just_switched:
                for field in fields:
                    field.chase()
                just_switched = False
        elif mode == 's':
            if just_switched:
                for field in fields:
                    field.initialize_red_blue_lights()
                just_switched = False
        elif mode == 'b':
            if just_switched:
                for field in fields:
                    field.initialize_red_blue_osc()
                just_switched = False
        elif mode == 'l':
            if just_switched:
                for field in fields:
                    field.calibrate()
                just_switched = False
        elif mode == 'o':
            if just_switched:
                for field in fields:
                    field.clear()
                just_switched = False
        time.sleep(0.4)