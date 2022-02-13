#include <FastLED.h>

//#define FASTLED_ALLOW_INTERRUPTS 1

int tot_len = 450;
// mode: 0 (led lights), 1 (red dull), 2 (blue dull)
// 3 (red pulse), 4 (blue pulse), 5 (rainbow),
// 6 (blue red chase)
int mode = 5;
int prev_mode = 0;
long t = 0;

int startLED = 0;
int endLED = tot_len;

int front_divide = 50;
int back_divide = 100;
int red_pulsing = false;
int blue_pulsing = false;

int blueReadyButtonPin = 11;
int redReadyButtonPin = 12;

bool setup_done = false;
CRGB swp;
CRGB leds[450];

void setup()
{
  Serial.begin(19200);
  Serial.setTimeout(5);
  FastLED.addLeds<WS2812, 2, GRB>(leds, 450);
  pinMode(blueReadyButtonPin, INPUT_PULLUP);
  pinMode(redReadyButtonPin, INPUT_PULLUP);
}

CRGB clip_rgb(float rf, float gf, float bf) {
  int r = (int) rf;
  int g = (int) gf;
  int b = (int) bf;
  return CRGB(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)));
}

String getValue(String data, char separator, int index)
{
    int found = 0;
    int strIndex[] = { 0, -1 };
    int maxIndex = data.length() - 1;

    for (int i = 0; i <= maxIndex && found <= index; i++) {
        if (data.charAt(i) == separator || i == maxIndex) {
            found++;
            strIndex[0] = strIndex[1] + 1;
            strIndex[1] = (i == maxIndex) ? i+1 : i;
        }
    }
    return found > index ? data.substring(strIndex[0], strIndex[1]) : "";
}

void red_blue_chase(int t){
  for (int i = 0; i < tot_len; i++){
    leds[i] = CRGB(255.0*abs(((t + i) % 360) - 180)/180, 0, 255.0*abs(((t + i + 180) % 360) - 180)/180);
  }
}

void rainbow(int t){
  for (int i = 0; i < tot_len; i++){
    leds[i] = CHSV(255.0*abs(((t + i) % 360) - 180)/180, 255, 255);
  }
}

void pulse(int t, bool red, bool blue){
  bool blue_side = false;
  for (int i = 0; i < tot_len; i++){
    blue_side = i > front_divide && i < back_divide;
    float value = 255.0*abs(((t + i) % 36) - 18)/18;
    if (blue && blue_side){
      leds[i] = CRGB(0, 0, value);
    }
    else if (!blue && blue_side){
      leds[i] = CRGB(0, 0, 50); 
    }
    else if (red && !blue_side) {
      leds[i] = CRGB(value, 0, 0);
    }
    else if (!red && !blue_side) {
      leds[i] = CRGB(50, 0, 0);
    }
  }
}

void dull(bool blue){
  for (int i = 0; i < tot_len; i++){
    if (blue == (i > front_divide && i < back_divide)){
      if (blue){
        leds[i] = CRGB(0, 0, 50); 
      }
      else {
        leds[i] = CRGB(50, 0, 0);
      }
    }
  }
}

void loop()
{
    while (Serial.available()){
      Serial.readStringUntil('x');
      String vals = Serial.readStringUntil('z');
      if (vals.substring(vals.length() - 1).equals("y")){
        vals = vals.substring(0, vals.length() - 1);
      }
      else {
        delay(30);
        break;
      }
      mode = getValue(vals, ' ', 0).toInt() - 1;
      int offset = 1;
      startLED = getValue(vals, ' ', offset + 0).toInt() - 1;
      endLED = getValue(vals, ' ', offset + 1).toInt() - 1;
      if (mode > 0){
        break;
      }
      int r = getValue(vals, ' ', offset + 2).toInt() - 1;
      int g = getValue(vals, ' ', offset + 3).toInt() - 1;
      int b = getValue(vals, ' ', offset + 4).toInt() - 1;
      for (int i = startLED; i < endLED; i++){
        leds[i] = CRGB(r, g, b);
      }
      if (!Serial.available()){
        FastLED.show();
      }
    }

    if (mode != prev_mode){
      prev_mode = mode;
      if (mode == 1){
        red_pulsing = false;
        front_divide = startLED;
        back_divide = endLED;
        dull(false);
        FastLED.show();
      }
      else if (mode == 2){
        blue_pulsing = false;
        front_divide = startLED;
        back_divide = endLED;
        dull(true);
        FastLED.show();
      }
      else if (mode == 3){
        red_pulsing = true;
        front_divide = startLED;
        back_divide = endLED;
      }
      else if (mode == 4){
        blue_pulsing = true;
        front_divide = startLED;
        back_divide = endLED;
      }
    }

    if (mode == 5){
      rainbow(t);
      FastLED.show();
      t += 1;
    }
    else if (mode == 6){
      red_blue_chase(t);
      FastLED.show();
      t += 1;
    }
    else if (mode > 0) {
      if (blue_pulsing || red_pulsing){
        pulse(t, red_pulsing, blue_pulsing);
        FastLED.show();
        t += 1;
      }
    }


    int blueButtonState = digitalRead(blueReadyButtonPin);
    int redButtonState = digitalRead(redReadyButtonPin);
    if (blueButtonState == 0){
      blue_pulsing = !blue_pulsing;
      if (!blue_pulsing){
        dull(true);
        FastLED.show();
      }
      delay(200);
    }
    else if (redButtonState == 0){
      red_pulsing = !red_pulsing;
      if (!red_pulsing){
        dull(false);
        FastLED.show();
      }
      delay(200);
    }
//    if (blueButtonState > 0 || redButtonState > 0){
//      delay(300);
//    }
}