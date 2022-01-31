#include <FastLED.h>

int tot_len = 450;
int num_steps_rot = 4;
int cur_step_rot = 0;
bool setup_done = false;
CRGB swp;
CRGB leds[450];

void setup()
{
  Serial.begin(230400);
  Serial.setTimeout(8);
  FastLED.addLeds<WS2812, 2, GRB>(leds, 450);
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

void loop()
{
    while (Serial.available()){
//      Serial.println("HERE");
      Serial.readStringUntil('x');
        // read the incoming byte:
      String vals = Serial.readStringUntil('y');
//      Serial.println(vals);
//      if (vals.length() < 2){ break; }
      int startLED = getValue(vals, ' ', 0).toInt() - 1;
      int endLED = getValue(vals, ' ', 1).toInt() - 1;
      int r = getValue(vals, ' ', 2).toInt() - 1;
      int g = getValue(vals, ' ', 3).toInt() - 1;
      int b = getValue(vals, ' ', 4).toInt() - 1;
      for (int i = startLED; i < endLED; i++){
        leds[i] = CRGB(r, g, b);
      }
      if (!Serial.available()){
        FastLED.show();
      }
    }
    
  // red and blue chasing
//  if (!setup_done) {
//    for (int i = 0; i < tot_len; i++) {
//      leds[i] = clip_rgb(
//                  setup_done = true;
//    }
//  }
//  else {
//    swp = leds[tot_len - 1];
//    for (int i = tot_len - 1; i > 0; i--) {
//      leds[i] = leds[i - 1];
//    }
//    leds[0] = swp;
//  }
//  FastLED.show();
//    delay(1);
}
