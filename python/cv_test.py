
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

if __name__ == "__main__":
    time.sleep(2)
    cur_time = time.time()
    with mss.mss() as sct:
        # The screen part to capture
        # region = {'top': 60, 'left': 210, 'width': 100, 'height': 80}
        region = {'top': 30, 'left': 150, 'width': 200, 'height': 450}
        # Grab the data
        myScreenshot = sct.grab(region)
    # convert image to numpy
    img = np.array(myScreenshot)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray, img_bin = cv2.threshold(img,128,255,cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    gray = cv2.bitwise_not(img_bin)
    kernel = np.ones((2, 1), np.uint8)
    img = cv2.erode(gray, kernel, iterations=1)
    img = cv2.dilate(img, kernel, iterations=1)

    img = cv2.resize(img, (0, 0), fx=0.5, fy=0.5)
    # add padding to the image
    # small_img = cv2.copyMakeBorder(small_img, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=[0, 0, 0])
    # plt.imshow(img)
    # plt.show()

    # perform OCR on img
    text = pytesseract.image_to_string(img)
    print(time.time() - cur_time)
    # print the text
    print(text)