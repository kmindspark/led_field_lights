#include <FastLED.h>

//#define FASTLED_ALLOW_INTERRUPTS 1

long tot_len = 450;
int max_led = 440;
// mode: 0 (led lights), 1 (red dull), 2 (blue dull)
// 3 (red pulse), 4 (blue pulse), 5 (rainbow),
// 6 (blue red chase), 7 (field split), 8 (calibrate), 9 (off)
int mode = 7;
int prev_mode = 7;
long t = (long) tot_len;

int startLED = 0;
int endLED = tot_len;

int front_divide = 50;
int back_divide = 100;
int red_pulsing = false;
int blue_pulsing = false;

int blueReadyButtonPin = 11;
int redReadyButtonPin = 12;

int back_left = 71;
int front_left = max_led/4 + back_left - 4;
int front_right = max_led/2 + back_left - 2;
int back_right = max_led*3/4 + back_left - 4;

double alpha = 0.2;
long time_upper;
long time_lower;
long last_bound_update_time;
long cur_input_time;
bool cur_input_time_change = false;
long cur_time = 15000;
long tot_time = 15000;

String prevVals = "";

bool setup_done = false;
CRGB swp;
CRGB leds[450];

void setup()
{
  Serial.begin(19200);
  FastLED.addLeds<WS2812, 3, GRB>(leds, 450);
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

void red_blue_chase(long t){
  int period = (int) (max_led / 2);
  int half_period = (int) (period / 2);
  for (int i = 0; i < tot_len; i++){
    int r = (int) (150.0*abs(((t - i) % period) - half_period)/half_period);
    int b = 150 - r;
    leds[i] = CRGB(r, 0, b);
  }
}

void clear(){
  for (int i = 0; i < tot_len; i++){
    leds[i] = CRGB(0, 0, 0);
  }
}

void calibrate(){
  clear();
  leds[back_left] = CRGB(255, 0, 0);
  leds[front_left] = CRGB(0, 255, 0);
  leds[front_right] = CRGB(0, 0, 255);
  leds[back_right] = CRGB(255, 255, 0);
}

int field_split_brightness_pos(int i, long t, bool simple){
  // int period = (int) (max_led / 16);
  // int half_period = (int) (period / 2);
  // return (int) (245.0*abs(((t - i) % period) - half_period)/half_period) + 10;
  if (simple){
    return 100;
  }

  // if (random(1, 10) > 5){
  //   return 125;
  // }
  return 100;
}

void field_split(long t, bool simple){
  // int intensity = 100;
  // if (osc){
  //   intensity = 120 + 100*sin(((double) t) / ((double) 20));
  // }
  int low_intensity = 0;
  int one_side_leds = max_led / 4;
  // set all to blue
  // for (int i = 0; i < max_led; i++){
  //   leds[i] = CRGB(0, 0, 255);
  // }

  for (int i = back_left; i < front_left; i++){
    leds[i] = CRGB(field_split_brightness_pos(i, t, simple), 0, 0);
  }
  for (int i = front_left; i < (front_right + front_left)/2; i++){
    leds[i] = CRGB(field_split_brightness_pos(i, t, simple), 0, 0);
  }
  for (int i = (front_right + front_left)/2; i < front_right; i++){
    leds[i] = CRGB(0, 0, field_split_brightness_pos(i, t, simple));
  }
  for (int i = front_right; i < back_right; i++){
    leds[i] = CRGB(0, 0, field_split_brightness_pos(i, t, simple));
  }
  for (int i = back_right; i < back_right + one_side_leds/2; i++){
    leds[i % max_led] = CRGB(0, 0, field_split_brightness_pos(i % max_led, t, simple));
    if (i < tot_len){
      leds[i] = CRGB(0, 0, field_split_brightness_pos(i, t, simple));
    }
  }
  for (int i = back_right + one_side_leds/2; i < tot_len + back_left; i++){ //back_right + one_side_leds
    leds[i % max_led] = CRGB(field_split_brightness_pos(i % max_led, t, simple), 0, 0); 
    if (i < tot_len){
      leds[i] = CRGB(0, 0, field_split_brightness_pos(i, t, simple));
    }
  }
}

void rainbow(long t){
  int period = (int) (max_led / 2);
  int half_period = (int) (period / 2);
  for (int i = 0; i < tot_len; i++){
    leds[i] = CHSV(255.0*((t - i) % period)/period, 255, 150);
  }
  // field_split(t);
  // for (int i = 0; i < max_led; i++){
  //   leds[i] = CRGB(100, 100, 100);
  // }
  // for (int i = front_left; i < front_right; i++){
  //   leds[i] = CRGB(255, 0, 255);
  // }
}

void flash_green(long t){
  int brightness = ((t / 3) % 2) * 100;
  for (int i = 0; i < max_led; i++){
    leds[i] = CRGB(0, brightness, 0);
  }
}

void flash_yellow(long t){
  int brightness = ((t / 15) % 2) * 100;
  for (int i = 0; i < max_led; i++){
    leds[i] = CRGB(brightness, brightness, 0);
  }
}

void soft_pulse(bool end){
  CRGB color;
  float brightness;
  int period = 120;
  int half_period = period/2; 
  if (end){
    brightness =  (int) (245.0*abs(((t * 3) % period) - half_period)/half_period) + 0;
    color = CRGB(brightness, brightness, 0);
  }
  else  {
    // brightness =  135 + 120*sin(millis() / 50);
    brightness = (int) (245.0*abs(((t * 15) % period) - half_period)/half_period) + 0;
    color = CRGB(brightness, brightness, 0);
  }
  for (int i = 0; i < tot_len; i++){
    leds[i] = color;
  }
}


void display_time(double fraction){
  if (fraction < 10000/105000 && fraction > 8000/105000 && tot_time == 105000){
    soft_pulse(false);
  }
  else if (fraction < 100/105000){
    soft_pulse(true);
  }
  else{
    int num_lights = front_right - front_left;
    int num_bright = num_lights * fraction;
    // Serial.println((double) (num_lights * fraction) - ((double) ((int) num_lights * fraction)));
    int middle_brightness = 100.0 * (((double) (num_lights * fraction)) - ((int) (num_lights * fraction)));
    // Serial.println(middle_brightness);
    // Serial.println(num_bright);
    for (int i = front_left; i < front_left + num_bright; i++){
      leds[i] = CRGB(0, 100, 0);
    }
    leds[front_left + num_bright] = CRGB(middle_brightness, 0, middle_brightness);
    for (int i = front_left + num_bright + 1; i < front_right; i++){
      leds[i] = CRGB(0, 0, 0);
    }
  }
}


void loop()
{
    while (Serial.available()){
      Serial.println("entering loop");
      Serial.readStringUntil('x');
      String vals = Serial.readStringUntil('z');
      if (vals.length() > 0 && vals.substring(vals.length() - 1).equals("y")){
        vals = vals.substring(0, vals.length() - 1);
        Serial.println(vals);
      }
      else {
        delay(30);
        break;
      }
      int proposedMode = getValue(vals, ' ', 0).toInt();
      if (proposedMode != mode){
        if (vals.equals(prevVals)){
          mode = proposedMode;
        }
      }
      prevVals = vals;
      if (mode > 0){
        // Serial.flush();
        break;
      }
      int offset = 0;
      cur_input_time = (getValue(vals, ' ', offset + 1).toInt()) * 1000;
      cur_input_time_change = true;
      long tot = (getValue(vals, ' ', offset + 2).toInt()) * 1000;
      Serial.println(cur_input_time);
      Serial.println(tot);

      if (tot == 15000 || tot == 105000){
        if (tot_time != tot){
          cur_time = tot;
          time_upper = cur_time;
          time_lower = cur_time - 1000;
        }
        tot_time = tot;
      }
      
      delay(30);
      while(Serial.available() > 0) {
        char dump = Serial.read();
      }
      prevVals = vals;
      break;
    }

    if (mode == 0){
      field_split(0, true);
      long now = millis();
      int delta = now - last_bound_update_time;
      if (cur_input_time != tot_time){
        time_upper -= delta;
        time_lower -= delta;
      }
      else {
        time_lower = tot_time - 1000;
        time_upper = tot_time;
      }

      if (cur_input_time_change){
        time_lower = max(time_lower, cur_input_time);
        time_upper = min(time_upper, cur_input_time);
      }

      // both must be greater than 0
      time_lower = max(0, time_lower);
      time_upper = max(0, time_upper);

      // time_upper = max(time_lower + 20, time_upper);
      // time_upper = min(time_upper, cur_input_time + 1000);
      // time_lower = min(time_upper - 20, time_lower);
      time_upper = max(cur_input_time - 1000, time_upper);

      Serial.println(time_upper);
      cur_time = alpha*cur_time + time_upper*(1-alpha);
      last_bound_update_time = now;

    //   if (abs(cur_time - 10000) <= 1000 && tot_time == 105000){
    //     flash_green(t);
    //   }
    //   else if (abs(cur_time - 0) < 500){
    //     flash_yellow(t);
    //   }
    //   else{
      display_time(((double) cur_time) /((double) tot_time));
    //   }
      FastLED.show();
      
      while(Serial.available() > 0) {
        char dump = Serial.read();
      }
      delay(30);
      t += 1;
    }

    if (mode == 4){
      field_split(t, false);
      FastLED.show();
      t += 1;
      delay(20);
    }
    if (mode == 5){
      rainbow(t);
      FastLED.show();
      t += 1;
      delay(20);
    }
    else if (mode == 6){
      red_blue_chase(t);
      FastLED.show();
      t += 1;
      delay(20);
    }
    else if (mode == 7){
      field_split(t, false);
      FastLED.show();
      t += 1;
      delay(20);
    }
    else if (mode == 8){
      calibrate();
      FastLED.show();
      delay(100);
    }
    else if (mode == 9){
      clear();
      FastLED.show();
      delay(100);
    }

    cur_input_time_change = false;
    prev_mode = mode;
//    if (blueButtonState > 0 || redButtonState > 0){
//      delay(300);
//    }
}