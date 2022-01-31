import serial
import time

arduino = serial.Serial(port='/dev/cu.usbmodem14301', baudrate=115200, timeout=.1)
def write_read(x):
    arduino.write(bytes(x + '\n', 'utf-8'))
    arduino.write(bytes(str(int(x) + 1) + '\n', 'utf-8'))
    time.sleep(0.2)
    data = arduino.readline()
    return data
while True:
    num = input("Enter a number: ") # Taking input from user
    value = write_read(num)
    print(value) # printing the value
