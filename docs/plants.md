# Plants

The plan for looking after plants with the Pi: a small microcontroller next to each plant reads
its sensors and reports to the hub, and the Pi is the hub that stores, shows and alerts.
Nothing here is built yet. Each phase ends with something that works, and a phase is only
worth starting once the one before it has run for a while.

## How it fits together

```
  plant 1                plant 2                 room
  ┌──────────────┐       ┌──────────────┐        ┌──────────────┐
  │ ESP32-C3     │       │ ESP32-C3     │        │ ESP32-C3     │
  │ soil sensor  │       │ soil sensor  │        │ temp/humidity│
  │ (pump, later)│       │ (pump, later)│        │ light        │
  └──────┬───────┘       └──────┬───────┘        └──────┬───────┘
         │  Wi-Fi: HTTP POST a reading every 15 min     │
         └───────────────────────┬──────────────────────┘
                                 ▼
                 Pi: hub API  →  SQLite  →  Plants page + ntfy alert when dry
```

- **One microcontroller per plant** keeps the wiring short (soil sensors and pumps sit in the
  pot) and lets a plant keep going on its own if the Wi-Fi or the Pi is down.
- **ESP32-C3** boards: a few dollars each, Wi-Fi built in, USB-C, and huge community support.
- **HTTP to the existing API**, not MQTT: no broker container to run and secure. MQTT is worth
  it only with many sensors or when the Pi needs to push commands to them instantly.
- **Decisions about water are made on the microcontroller**, with hard limits (see phase 2).
  The hub sets the targets and shows what happened; it never runs a pump directly.

## Phase 1: Soil moisture for one plant

Goal: a reading every 15 minutes on the hub, and a phone alert when the plant is dry.

Hardware:

| Part | Note |
|---|---|
| ESP32-C3 board (e.g. SuperMini) | Any ESP32 works; the C3 is small and cheap. |
| **Capacitive** soil moisture sensor (v1.2 or v2.0) | Not the two-pronged resistive kind: it corrodes in weeks. |
| USB-C cable and a phone charger | Batteries come later (phase 4). |
| Jumper wires (female–female) | Three wires: 3.3 V, GND, and the signal to an analog pin. |

Steps:

1. **Firmware:** a short Arduino (PlatformIO) or MicroPython sketch: read the analog pin,
   average a few samples, POST `{"sensor": "basil", "moisture_raw": 2140}` to the hub, sleep 15
   minutes. [ESPHome](https://esphome.io) can do the same from a YAML file with no code, if you'd
   rather not write firmware.
2. **Calibrate:** note the raw value with the sensor in dry air (0%) and in a glass of water
   (100%). The hub turns raw values into a percentage with those two numbers.
3. **Hub (the smallest change that works):** a `plants` module like the others: one table of
   readings, a `POST /api/plants/readings` endpoint, and a page with each plant's latest value
   and a simple chart. The page and the module only appear once this phase is built.
4. **Security:** a microcontroller can't do the hub's device sign-in, so each sensor sends a
   secret token in a header, stored hashed like device cookies. The endpoint accepts readings
   only, from the home network, so a leaked token can at worst fake a reading.
5. **Alert:** below a threshold (start at 30%) for an hour, ping your phone through ntfy, the
   same way Trading does. Once per dry spell, not every 15 minutes.

Done when: a week of readings, and you watered the plant because the hub told you to.

## Phase 2: Automated watering

Goal: the plant waters itself, and can never flood the room or burn out the pump.

Hardware:

| Part | Note |
|---|---|
| 5 V mini submersible pump + silicone tube | Cheap and enough for a pot. |
| Logic-level MOSFET module (or a small relay module) | The ESP32's pins can't power a pump directly. |
| Flyback diode across the pump (if the module lacks one) | Protects the board from the motor's voltage spike. |
| Water reservoir (any jar or tank) | |
| Water level sensor (float switch) | So the pump never runs dry. |

Rules on the microcontroller, so they hold even with no Wi-Fi:

- Water only when below the target for two readings in a row (one bad reading does nothing).
- Run the pump for at most a few seconds per go, then wait 30 minutes for the water to soak in
  before checking again.
- At most N runs per day; past that, stop and alert ("the sensor may have fallen out").
- Never run with the reservoir empty; alert to refill instead.

Hub: the target and limits per plant, a log of each watering, and alerts for "reservoir
empty" and "hit the daily limit".

Test the whole thing over a bucket or a sink before any plant gets it.

## Phase 3: Climate and more sensors

One sensor per room, not per plant: temperature, humidity and light are the same for every
plant on a shelf.

| Sensor | Measures | Note |
|---|---|---|
| SHT40 or SHT31 (I²C) | Temperature, humidity | Far more accurate than the common DHT22. |
| BH1750 (I²C) | Light (lux) | Shows whether a spot gets enough light. |

Both share the same two I²C wires, so one ESP32 reads both. Hub: the room's values on the
Plants page, and alerts for too cold, too hot or too dry air.

## Phase 4: Ideas for later

Roughly in order of value for the effort:

- **Plant care log:** species, photo, when you fertilised or repotted, with reminders.
- **Battery power:** deep sleep between readings lets an ESP32 run for months on an 18650 cell,
  so plants don't need to sit near a socket.
- **Timelapse:** a Pi Camera Module 3 (or an ESP32-CAM) takes a photo a day; the hub makes a
  monthly timelapse.
- **Per-species targets:** pick the species and get a sensible moisture range and light need.
- **Over-the-air updates** for the microcontrollers, so you never unplug one to change its code.
- **Grow light** on a smart plug, switched on when the light sensor reads too low in winter.

## Starter shopping list (phase 1 and 2, one plant)

- 2 × ESP32-C3 boards (one spare)
- 2 × capacitive soil moisture sensors
- 1 × 5 V mini submersible pump with tube
- 1 × MOSFET module, 1 × 1N4007 diode (or a module with one built in)
- 1 × float switch
- A breadboard and a pack of jumper wires
- USB-C cable and charger
