# IoT Smart Parking Sensor — PCB v1.0
nSmart parking sensor for my university project.

2-layer board, **62 × 46 mm**, four M3 holes (3.2 mm, NPTH) 3.5 mm in from each corner.
Everything here is produced by `generate.py`, which writes all the files and then checks them:

```powershell
& "C:\Program Files\KiCad\10.0\bin\python.exe" generate.py
```

Results of the last run: **ERC 0 issues, DRC 0 issues (zones refilled, schematic parity checked)**. KiCad's own exported netlist matches the netlist below exactly.

## Read before you order

| # | Item | What I did / what you must check |
|---|------|----------------------------------|
| 1 | **SuperMini row spacing** | Estimated from your photos as **16.5 mm**, using the 2.54 mm pin pitch as the scale. The spec's 17.78 mm and my first guess of 15.24 mm are both wrong. **Measure hole centre to hole centre across the board with calipers** and set `ROW_SPACING` in `generate.py`. |
| 2 | SuperMini pin order | Confirmed from your photos: with USB-C at the bottom (top view), the left column top→bottom is `GPIO0 … GPIO4, 3V3, GND, 5V`. |
| 3 | **TP4056 (HW-373 V1.2.1) pads** | Order confirmed from your photos: `IN-`/`IN+` at the USB end (IN+ on the right), and `OUT-, B-, B+, OUT+` across the other end. Spacing estimated from the photos: outer pads ±7.3 mm, B± at ±3.8 mm. Check with calipers (`TP_PX`, `TP_BX`). |
| 4 | **SS-12D00G3 pitch** | Assumed 2.54 mm. Some clones use 2.0 mm, so check yours. |
| 5 | **Board size** | 50 × 40 mm doesn't fit the three modules, both keep-outs and four corner M3 holes without courtyard collisions, so the board is 62 × 46 mm. |
| 6 | ⚠ **USB while switched on** | The SuperMini `5V` pin is the USB VBUS line. With SW1 ON it connects through the protection MOSFETs straight to the battery, so a USB cable charges the LiPo directly with no current limit. **Turn SW1 OFF before connecting USB**; the silkscreen says so too. |
| 7 | **No boost converter** | The 5V pin gets raw battery voltage (3.0–4.2 V) into the onboard LDO. Below about 3.5 V, Wi‑Fi bursts may brown out. **C2 (100 µF)** at the 5V pin smooths the bursts; also check the battery in firmware before using Wi‑Fi (see below). |
| 7a | ⚠ **TP4056 charge current (rework)** | The HW-373 ships set to 1 A, which is 2.2C for a 450 mAh cell. **Replace its R_PROG** (the 1.2 kΩ resistor marked `122`, on TP4056 pin 2) with **3.0 kΩ**, which gives ~400 mA (0.9C). It's listed in the BOM as `U2 rework`. Solar alone gives only tens of mA, but USB-C charging on the module would use the full setting. |
| 8 | **JST-PH polarity** | It isn't standardized. J1 pin 1 = `+` (square pad). Your 752035 cell has bare leads, so crimp a PH plug with red to pin 1. Your solar panel's **blue** wire is `+`. |
| 9 | JST-XH pitch | Real XH pitch is 2.50 mm (the spec says 2.54); the stock KiCad footprint is used. |

## Netlist (also in `netlist.csv` / `netlist.json`)

| Net | Connections | Width |
|-----|-------------|-------|
| SOLAR_P | J2.1 (+) — U2 IN+ | 0.6 mm |
| SOLAR_N | J2.2 (−) — U2 IN− | 0.6 mm |
| BAT_P | J1.1 (+) — U2 B+ | 0.6 mm |
| BAT_N | J1.2 (−) — U2 B− | 0.6 mm |
| VOUT | U2 OUT+ — SW1.1 | 0.6 mm |
| VSYS | SW1.2 (common) — U1 5V — R1.1 — C2.1 | 0.6 mm |
| +3V3 | U1 3V3 — U3 VCC | 0.6 mm |
| GND | U2 OUT−, U1 GND, U3 GND, R2.2, C1.2, C2.2, D1 K | bottom pour |
| SDA | U1 GPIO8 — U3 SDA | 0.25 mm |
| SCL | U1 GPIO9 — U3 SCL | 0.25 mm |
| VBAT_SENSE | R1.2 — R2.1 — C1.1 — U1 GPIO0 (ADC1_CH0) | 0.25 mm |
| LED_DRV | U1 GPIO1 — R3.1 | 0.25 mm |
| LED_A | R3.2 — D1 A | 0.25 mm |
| *no connect* | U3 DRDY, SW1.3, U1 GPIO2–7/10/20/21 | — |

## Wiring diagram

```
 SOLAR 5-6V            TP4056 + DW01A/FS8205A (U2)
 J2 (+) ───SOLAR_P───► IN+                    OUT+ ──VOUT──► SW1.1 ┐
 J2 (-) ───SOLAR_N───► IN-                    OUT- ──GND          │ SW1 (SS-12D00G3)
                                                                   │
 LIPO 3.7V 450mAh                                     SW1.2 (COM) ◄┘
 J1 (+) ───BAT_P─────► B+                               │ VSYS (switched)
 J1 (-) ───BAT_N─────► B-                               ├──────────────► U1 5V  (onboard LDO)
                                                        │
                                                       R1 100k 1%
                                                        │
                       U1 GPIO0 (ADC1_CH0) ◄────────────┼── VBAT_SENSE  (4.2 V → 2.1 V)
                                                        │
                                                R2 100k ┴ ┬ C1 100nF
                                                        GND
 ESP32-C3 SuperMini (U1)            GY-271 (U3)
   3V3   ────── +3V3 ──────────────► VCC
   GND   ────── GND ───────────────► GND
   GPIO9 ────── SCL ───────────────► SCL
   GPIO8 ────── SDA ───────────────► SDA
                                     DRDY  ✕ (no connect)

   GPIO1 ── LED_DRV ── R3 220R ── LED_A ──► D1 anode   D1 cathode ── GND
```

## Board layout (top view, USB-C at the bottom edge)

```
 0                                                           62 mm
 ┌──────────────────────────────────────────────────────────────┐ 0
 │ (H1)   [J2 SOLAR]       PARKING SENSOR v1.0            (H2)   │
 │ ┌─────────────┐                                ┌──────────┐ │
 │ │IN-       IN+│  ┌─── +3V3 trace (y=12) ───┐    │  GY-271  │ │
 │ │             │  │                         │    │   (U3)   │ │
 │ │   TP4056    │  │  ░░ ANTENNA KEEP-OUT ░░ │    │▓ MAG     │ │
 │ │    (U2)     │  │  ░░  no copper, both ░░ │    │▓ KEEP-OUT│ │
 │ │             │  │  ░░  layers           ░░└───►VCC GND SCL SDA DRDY
 │ │             │  │ ┌─┐  ESP32-C3     ┌─┐         ▲   ▲      │
 │ │             │  │ │0│  SuperMini    │ │  SCL ───┘   │      │
 │ │             │  │ │ │  (U1, socket) │ │  SDA ───────┘      │
 │ │OUT- B- B+ OUT+ │ │ │ R1 R2 C1      │ │                    │
 │ └─────────────┘  └─│ │ (under module)│ │                    │
 │  [J1 BATT] [SW1 PWR] │5V   USB-C     └─┘  R3  D1            │
 │ (H3)                 └──────────────┘                (H4)   │
 └──────────────────────────────────────────────────────────────┘ 46
```

The rendered board is in `diagrams/render_top.png` and `render_bottom.png`, the per-layer copper in `pcb_top.svg` and `pcb_bottom.svg`, and the schematic in `diagrams/parking_sensor.svg` and `schematic.pdf`.

## Layout rules as implemented

1. **Magnetometer keep-out**: a rule area on both copper layers under the GY-271 body (x 45–58, y 7.75–20 mm) blocks tracks, vias and pour. Every GY-271 trace comes in from below the header. The battery and charge paths (`BAT±`, `VOUT`, `VSYS`) all stay on the left half, more than 23 mm from the sensor chip. The only trace nearby is `+3V3`, which carries about 1 mA to the sensor.
2. **Antenna keep-out**: a rule area on both layers from the SuperMini's antenna end out to 7.5 mm beyond it (x 24–42, y 16–24.6). It's printed on silkscreen as "ANTENNA KEEP-OUT / NO COPPER".
3. **Track widths**: power nets are 0.6 mm and signals 0.25 mm. Both minimums are enforced by DRC rules in `parking_sensor.kicad_dru`.
4. **GND**: one solid bottom pour (0.3 mm clearance, thermal reliefs) with cut-outs only for the keep-outs. Only one track runs on the bottom layer: a 9.6 mm `LED_DRV` jumper under the ESP32, which lets it cross `VBAT_SENSE`.
5. **Parts under the module**: the SuperMini sits about 8.5 mm up on its female headers, so R1, R2, C1 (0805) and C2 (1210) fit underneath it. The module's courtyard covers only the two header rows.

## Files

| File | What it is |
|------|-----------|
| `parking_sensor.kicad_pro/.kicad_sch/.kicad_pcb` | KiCad 10 project. Open the `.kicad_pro`. EasyEDA Pro can import these via *File → Import → KiCad*. |
| `parking_sensor.pretty/` | Footprints for the SuperMini, TP4056, GY-271 and SS-12D00G3 |
| `parking_sensor.kicad_sym` | Matching schematic symbols |
| `parking_sensor.kicad_dru` | Custom DRC rules (track widths) |
| `bom.csv`, `bom.json` | Bill of materials |
| `netlist.csv`, `netlist.json` | Netlist, one row per pin. `kicad_netlist.xml` is KiCad's own export of it. |
| `gerbers/` | Gerbers, drill file, top placement file. Zip this folder to order boards. |
| `diagrams/` | Schematic SVG/PDF, PCB layer SVGs, 3D renders |
| `erc.json`, `drc.json` | Reports from the last check run |
| `generate.py` | The single source of truth. Edit it and re-run instead of hand-editing the board if you want to keep the checks. |

## Firmware notes

- ADC: use `analogReadMilliVolts(0) * 2` with 11 dB attenuation. 4.2 V reads as 2.1 V, inside the ~2.5 V range. The divider is 100k/100k (~21 µA drain); C1 keeps readings stable, but sample slowly (one reading, or a few ms apart).
- Low battery: read the battery **before** starting Wi‑Fi. Under 3.5 V, skip Wi‑Fi and deep-sleep (e.g. 30 min) until solar recovers it. Lower the transmit power (`WiFi.setTxPower(WIFI_POWER_8_5dBm)`) if the link allows.
- If your SuperMini has an always-on power LED, removing it saves a few mA (days of battery).
- I2C: `Wire.begin(8, 9)` (SDA, SCL). QMC5883L is at 0x0D and HMC5883L at 0x1E, so check which chip your GY-271 has.
- GPIO8 also drives the SuperMini's onboard LED, so it flickers during I2C traffic. That's harmless.
- When charging from solar, the TP4056 current changes the field near the board slightly. Calibrate the empty-spot baseline in firmware rather than relying on one absolute value.
