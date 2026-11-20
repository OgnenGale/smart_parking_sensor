"""IoT Smart Parking Sensor - KiCad project generator.

Single source of truth for parts, pins, nets, placement and routing. Writes:
  parking_sensor.kicad_sch / .kicad_pcb / .kicad_pro / .kicad_dru
  parking_sensor.pretty/ (module footprints), parking_sensor.kicad_sym
  bom.csv, bom.json, netlist.csv, netlist.json
then runs ERC, DRC (with schematic parity) and checks the KiCad-exported
netlist against NETS below.

Run with KiCad's bundled Python (it ships the pcbnew module):
  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" generate.py
"""
import csv
import json
import os
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "parking_sensor"
KICAD_BIN = os.path.dirname(sys.executable)
KICAD_CLI = os.path.join(KICAD_BIN, "kicad-cli.exe" if os.name == "nt" else "kicad-cli")
STOCK_FP = os.environ.get("KICAD10_FOOTPRINT_DIR",
                          os.path.join(KICAD_BIN, "..", "share", "kicad", "footprints"))
_NS = uuid.UUID("6f1c2b1e-5a1d-4c3e-9d8f-0a5e5e1c0001")


def uid(s):
    return str(uuid.uuid5(_NS, s))


ROOT_UUID = uid("root")

# --- Board geometry (mm, origin = top-left board corner, +y = down) ----------
BOARD_W, BOARD_H = 62.0, 46.0
OX, OY = 100.0, 50.0          # where the board sits on the KiCad page
ROW_SPACING = 16.5            # SuperMini rows, estimated from photos (2.54 pitch as scale). MEASURE (README).
U1_X = 33.65                  # module centre; left row stays clear of SW1
UL = U1_X - ROW_SPACING / 2   # left header row x
TP_PX = 7.3                   # TP4056 (HW-373) outer pads at +-7.3 mm, B+/B- at +-3.8 mm (from photos)
TP_BX = 3.8
PWR, SIG = 0.6, 0.25          # track widths
POWER_NETS = ["SOLAR_P", "SOLAR_N", "BAT_P", "BAT_N", "VOUT", "VSYS", "+3V3", "GND"]

# --- Parts -------------------------------------------------------------------
# pins: (pad number, pin name, net or None for no-connect, side 'L'/'R' on symbol)
PARTS = [
    dict(ref="U1", value="ESP32-C3 SuperMini", sym="ESP32C3_SuperMini", w=15.24,
         fp="parking_sensor:ESP32-C3_SuperMini_Socketed",
         desc="ESP32-C3 SuperMini dev board on 2x 1x8 2.54mm female headers",
         bom="ESP32-C3 SuperMini + 2x 1x8 female header 2.54mm",
         pins=[("1", "GPIO0", "VBAT_SENSE", "L"), ("2", "GPIO1", "LED_DRV", "L"),
               ("3", "GPIO2", None, "L"), ("4", "GPIO3", None, "L"),
               ("5", "GPIO4", None, "L"), ("6", "3V3", "+3V3", "L"),
               ("7", "GND", "GND", "L"), ("8", "5V", "VSYS", "L"),
               ("9", "GPIO21", None, "R"), ("10", "GPIO20", None, "R"),
               ("11", "GPIO10", None, "R"), ("12", "GPIO9", "SCL", "R"),
               ("13", "GPIO8", "SDA", "R"), ("14", "GPIO7", None, "R"),
               ("15", "GPIO6", None, "R"), ("16", "GPIO5", None, "R")],
         sch=(147.32, 116.84), pcb=(U1_X, 34.75, 0)),
    dict(ref="U2", value="TP4056 + DW01A/FS8205A", sym="TP4056_Module", w=12.7,
         fp="parking_sensor:TP4056_Module_Protected",
         desc="TP4056 1S Li-ion charger module with DW01A + FS8205A protection",
         bom="TP4056 charger module with protection (USB-C or micro-USB)",
         pins=[("1", "IN+", "SOLAR_P", "L"), ("2", "IN-", "SOLAR_N", "L"),
               ("3", "B+", "BAT_P", "L"), ("4", "B-", "BAT_N", "L"),
               ("5", "OUT+", "VOUT", "R"), ("6", "OUT-", "GND", "R")],
         sch=(91.44, 50.8), pcb=(11.0, 21.5, 0)),
    dict(ref="U3", value="GY-271 (QMC5883L/HMC5883L)", sym="GY-271", w=10.16,
         fp="parking_sensor:GY-271_Module",
         desc="GY-271 3-axis magnetometer module, 1x5 2.54mm header",
         bom="GY-271 magnetometer module + 1x5 female header 2.54mm",
         pins=[("1", "VCC", "+3V3", "L"), ("2", "GND", "GND", "L"),
               ("3", "SCL", "SCL", "L"), ("4", "SDA", "SDA", "L"),
               ("5", "DRDY", None, "L")],
         sch=(236.22, 116.84), pcb=(51.5, 15.0, 0)),
    dict(ref="J1", value="LiPo 3.7V 450mAh", sym="Conn_Pwr_2", w=5.08,
         fp="Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal",
         desc="Battery connector, JST-PH 2.0mm right-angle",
         bom="JST PH S2B-PH-K-S right-angle 2-pin",
         pins=[("1", "+", "BAT_P", "R"), ("2", "-", "BAT_N", "R")],
         sch=(50.8, 63.5), pcb=(10.0, 38.6, 0)),
    dict(ref="J2", value="Solar 5-6V", sym="Conn_Pwr_2", w=5.08,
         fp="Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical",
         desc="Solar panel input, JST-XH 2.5mm vertical",
         bom="JST XH B2B-XH-A vertical 2-pin",
         pins=[("1", "+", "SOLAR_P", "R"), ("2", "-", "SOLAR_N", "R")],
         sch=(50.8, 43.18), pcb=(12.5, 4.2, 180)),
    dict(ref="SW1", value="SS-12D00G3", sym="SW_SPDT", w=7.62,
         fp="parking_sensor:SW_Slide_SPDT_SS-12D00G3",
         desc="SPDT slide switch, power disconnect",
         bom="SS-12D00G3 SPDT slide switch",
         pins=[("1", "A", "VOUT", "L"), ("3", "B", None, "L"), ("2", "C", "VSYS", "R")],
         sch=(144.78, 50.8), pcb=(19.14, 42.6, 180)),
    dict(ref="R1", value="100k 1%", sym="R", w=5.08,
         fp="Resistor_SMD:R_0805_2012Metric",
         desc="Battery divider top (100k: ~21uA drain)", bom="100k 1% 0805",
         pins=[("1", "~", "VSYS", "L"), ("2", "~", "VBAT_SENSE", "R")],
         sch=(53.34, 119.38), pcb=(28.0, 40.0, 90)),
    dict(ref="R2", value="100k 1%", sym="R", w=5.08,
         fp="Resistor_SMD:R_0805_2012Metric",
         desc="Battery divider bottom (100k: ~21uA drain)", bom="100k 1% 0805",
         pins=[("1", "~", "VBAT_SENSE", "L"), ("2", "~", "GND", "R")],
         sch=(53.34, 134.62), pcb=(30.5, 36.0, 90)),
    dict(ref="C1", value="100nF", sym="C", w=5.08,
         fp="Capacitor_SMD:C_0805_2012Metric",
         desc="ADC filter", bom="100nF X7R 0805 ceramic",
         pins=[("1", "~", "VBAT_SENSE", "L"), ("2", "~", "GND", "R")],
         sch=(53.34, 149.86), pcb=(33.0, 36.0, 90)),
    dict(ref="C2", value="100uF 6.3V", sym="C", w=5.08,
         fp="Capacitor_SMD:C_1210_3225Metric",
         desc="Bulk cap at ESP32 5V pin, rides through Wi-Fi bursts",
         bom="100uF 6.3V X5R 1210 ceramic (e.g. Murata GRM32ER60J107)",
         pins=[("1", "~", "VSYS", "L"), ("2", "~", "GND", "R")],
         sch=(96.52, 134.62), pcb=(31.0, 43.6, 0)),
    dict(ref="R3", value="220R", sym="R", w=5.08,
         fp="Resistor_SMD:R_0805_2012Metric",
         desc="LED current limit", bom="220R 0805",
         pins=[("1", "~", "LED_DRV", "L"), ("2", "~", "LED_A", "R")],
         sch=(53.34, 172.72), pcb=(45.5, 42.37, 0)),
    dict(ref="D1", value="LED 3mm green", sym="LED", w=5.08,
         fp="LED_THT:LED_D3.0mm",
         desc="Status LED", bom="3mm LED green/blue",
         pins=[("2", "A", "LED_A", "L"), ("1", "K", "GND", "R")],
         sch=(91.44, 172.72), pcb=(51.34, 42.37, 180)),
]
HOLES = [(3.5, 3.5), (BOARD_W - 3.5, 3.5), (3.5, BOARD_H - 3.5), (BOARD_W - 3.5, BOARD_H - 3.5)]

NETS = {}
for _p in PARTS:
    for _num, _name, _net, _side in _p["pins"]:
        if _net:
            NETS.setdefault(_net, []).append((_p["ref"], _num, _name))

# Routing: (net, layer, width, [points]); a point is (x, y) or ("REF", "pad").
# Hand-placed so nothing crosses on F.Cu; LED_DRV hops under VBAT_SENSE on B.Cu.
F, B = "F.Cu", "B.Cu"
ROUTES = [
    ("SOLAR_P", F, PWR, [("J2", "1"), (11.0 + TP_PX, 4.2), ("U2", "1")]),
    ("SOLAR_N", F, PWR, [("J2", "2"), (10.0, 6.8), (11.0 - TP_PX, 6.8), ("U2", "2")]),
    ("BAT_P", F, PWR, [("U2", "3"), (11.0 + TP_BX, 36.5), (10.0, 36.5), ("J1", "1")]),
    ("BAT_N", F, PWR, [("U2", "4"), (11.0 - TP_BX, 41.6), (12.0, 41.6), ("J1", "2")]),
    ("VOUT", F, PWR, [("U2", "5"), (11.0 + TP_PX, 36.5), (21.68, 36.5), ("SW1", "1")]),
    ("VSYS", F, PWR, [("SW1", "2"), (19.14, 44.6), (UL, 44.6), ("U1", "8")]),
    ("VSYS", F, PWR, [("U1", "8"), (28.0, 43.64), ("R1", "1")]),
    ("VSYS", F, PWR, [(28.0, 43.64), ("C2", "1")]),
    ("+3V3", F, PWR, [("U1", "6"), (22.9, 38.56), (22.9, 12.0), (44.0, 12.0), (44.0, 21.0), ("U3", "1")]),
    ("VBAT_SENSE", F, SIG, [("R1", "2"), (28.0, 25.86), ("U1", "1")]),
    ("VBAT_SENSE", F, SIG, [(28.0, 34.0), (30.5, 34.0), ("R2", "1")]),
    ("VBAT_SENSE", F, SIG, [(30.5, 34.0), (33.0, 34.0), ("C1", "1")]),
    ("LED_DRV", B, SIG, [("U1", "2"), (35.0, 28.4)]),
    ("LED_DRV", F, SIG, [(35.0, 28.4), (35.0, 42.37), ("R3", "1")]),
    ("LED_A", F, SIG, [("R3", "2"), ("D1", "2")]),
    ("SCL", F, SIG, [("U1", "12"), (51.5, 33.48), ("U3", "3")]),
    ("SDA", F, SIG, [("U1", "13"), (54.04, 36.02), ("U3", "4")]),
    ("GND", F, PWR, [("R2", "2"), (30.5, 38.4)]),
    ("GND", F, PWR, [("C1", "2"), (33.0, 38.4)]),
    ("GND", F, PWR, [("C2", "2"), (34.0, 43.6)]),
]
VIAS = [("LED_DRV", 35.0, 28.4), ("GND", 30.5, 38.4), ("GND", 33.0, 38.4), ("GND", 34.0, 43.6)]

# Keep-outs (rule areas on both copper layers: no tracks, vias or pour)
ANT_KEEPOUT = (U1_X - 9, 16.0, U1_X + 9, 24.6)     # above U1's antenna end
MAG_KEEPOUT = (45.0, 7.75, 58.0, 20.0)     # under the GY-271 body (chip side)


# =============================================================================
# Footprints for the plug-in modules
# =============================================================================
def _txt(layer, text, x, y, size=1.0):
    return (f'  (fp_text user "{text}" (at {x:.3f} {y:.3f} 0) (layer "{layer}")'
            f' (effects (font (size {size} {size}) (thickness {size * 0.15:.3f}))))\n')


def _rect(layer, x1, y1, x2, y2, w):
    pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
    return "".join(f'  (fp_line (start {a[0]:.3f} {a[1]:.3f}) (end {b[0]:.3f} {b[1]:.3f})'
                   f' (stroke (width {w}) (type solid)) (layer "{layer}"))\n'
                   for a, b in zip(pts, pts[1:]))


def _pad(num, x, y, size, drill, square=False):
    shape = "rect" if square else "circle"
    return (f'  (pad "{num}" thru_hole {shape} (at {x:.3f} {y:.3f}) (size {size} {size})'
            f' (drill {drill}) (layers "*.Cu" "*.Mask"))\n')


def _footprint(name, descr, ref_y, val_y, body):
    return (f'(footprint "{name}"\n  (version 20240108)\n  (generator "parking_sensor_gen")\n'
            f'  (layer "F.Cu")\n  (descr "{descr}")\n'
            f'  (property "Reference" "REF**" (at 0 {ref_y} 0) (layer "F.SilkS")'
            f' (effects (font (size 1 1) (thickness 0.15))))\n'
            f'  (property "Value" "{name}" (at 0 {val_y} 0) (layer "F.Fab")'
            f' (effects (font (size 1 1) (thickness 0.15))))\n'
            f'  (attr through_hole)\n{body})\n')


def write_footprints():
    out = {}
    # ESP32-C3 SuperMini, USB-C toward +y. Courtyard = the two socket rows only:
    # the module sits ~8.5 mm up on sockets, so the 0805 parts fit underneath.
    hx = ROW_SPACING / 2
    ys = [-8.89 + 2.54 * k for k in range(8)]
    b = _rect("F.Fab", -9, -11.25, 9, 11.25, 0.1) + _rect("F.Fab", -4.5, 7.9, 4.5, 11.25, 0.1)
    b += _txt("F.Fab", "USB-C", 0, 9.6, 0.8) + _txt("F.Fab", "ANTENNA", 0, -10.2, 0.8)
    for x in (-hx, hx):
        b += _rect("F.SilkS", x - 1.4, -10.3, x + 1.4, 10.3, 0.12)
        b += _rect("F.CrtYd", x - 1.52, -10.42, x + 1.52, 10.42, 0.05)
    names = [p[1] for p in PARTS[0]["pins"]]
    for k, y in enumerate(ys):
        b += _pad(str(k + 1), -hx, y, 1.7, 1.0, square=(k == 0))
        b += _pad(str(k + 9), hx, y, 1.7, 1.0)
        b += _txt("F.Fab", names[k], -hx + 3.2, y, 0.6) + _txt("F.Fab", names[k + 8], hx - 3.2, y, 0.6)
    b += _txt("F.SilkS", "USB", 0, 7.0, 0.8)
    out["ESP32-C3_SuperMini_Socketed"] = _footprint(
        "ESP32-C3_SuperMini_Socketed",
        f"ESP32-C3 SuperMini on 2x 1x8 2.54mm sockets, row spacing {ROW_SPACING}mm",
        -12.2, 12.2, b)

    # TP4056 module (28 x 17 mm), IN end toward -y. Pad positions: verify on your module.
    tp = {"1": (TP_PX, -12.5, "IN+"), "2": (-TP_PX, -12.5, "IN-"), "6": (-TP_PX, 12.5, "OUT-"),
          "4": (-TP_BX, 12.5, "B-"), "3": (TP_BX, 12.5, "B+"), "5": (TP_PX, 12.5, "OUT+")}
    b = _rect("F.SilkS", -8.75, -14, 8.75, 14, 0.12) + _rect("F.Fab", -8.75, -14, 8.75, 14, 0.1)
    b += _rect("F.CrtYd", -9.0, -14.25, 9.0, 14.25, 0.05)
    b += _txt("F.SilkS", "TP4056", 0, 0, 1.0)
    for num, (x, y, lab) in tp.items():
        b += _pad(num, x, y, 2.0, 1.0, square=(num == "1"))
        b += _txt("F.SilkS", lab, x * 0.85 if abs(x) > 3 else x, y - 2.4 if y > 0 else y + 2.4, 0.8)
    out["TP4056_Module_Protected"] = _footprint(
        "TP4056_Module_Protected", "TP4056 charger module with DW01A/FS8205A, 6 pads",
        -15.2, 15.2, b)

    # GY-271, header along +y edge, VCC..DRDY left to right (top view)
    b = _rect("F.SilkS", -6.5, -7.25, 6.5, 7.25, 0.12) + _rect("F.Fab", -6.5, -7.25, 6.5, 7.25, 0.1)
    b += _rect("F.CrtYd", -6.75, -7.5, 6.75, 7.5, 0.05)
    b += _rect("F.Fab", -1.5, -2.0, 1.5, 1.0, 0.1) + _txt("F.Fab", "IC", 0, -0.5, 0.8)
    b += _txt("F.SilkS", "GY-271", 0, -4.5, 0.9)
    for k, lab in enumerate(["VCC", "GND", "SCL", "SDA", "DRDY"]):
        x = -5.08 + 2.54 * k
        b += _pad(str(k + 1), x, 6.0, 1.7, 1.0, square=(k == 0))
        b += _txt("F.Fab", lab, x, 3.9, 0.55)
    out["GY-271_Module"] = _footprint("GY-271_Module", "GY-271 HMC5883L/QMC5883L module, 1x5 2.54mm",
                                      -8.5, 8.5, b)

    # SS-12D00G3 slide switch, 3 pins 2.54mm, pin 2 = common
    b = _rect("F.SilkS", -4.3, -1.8, 4.3, 1.8, 0.12) + _rect("F.Fab", -4.3, -1.8, 4.3, 1.8, 0.1)
    b += _rect("F.CrtYd", -4.55, -2.05, 4.55, 2.05, 0.05)
    for k in range(3):
        b += _pad(str(k + 1), -2.54 + 2.54 * k, 0, 1.6, 0.9, square=(k == 0))
    out["SW_Slide_SPDT_SS-12D00G3"] = _footprint(
        "SW_Slide_SPDT_SS-12D00G3", "SS-12D00G3 SPDT slide switch, 2.54mm pitch", -3.0, 3.0, b)

    lib = os.path.join(HERE, f"{NAME}.pretty")
    os.makedirs(lib, exist_ok=True)
    for n, text in out.items():
        with open(os.path.join(lib, n + ".kicad_mod"), "w", newline="\n") as f:
            f.write(text)


# =============================================================================
# Schematic
# =============================================================================
FONT = "(effects (font (size 1.27 1.27)))"
FONT_HIDE = "(effects (font (size 1.27 1.27)) (hide yes))"


def _sym_geom(part):
    left = [p for p in part["pins"] if p[3] == "L"]
    right = [p for p in part["pins"] if p[3] == "R"]
    n = max(len(left), len(right), 1)
    top = 1.27 * (n - 1)
    half_w = part["w"] / 2
    half_h = top + 2.54
    pins = []
    for side, lst in (("L", left), ("R", right)):
        for k, p in enumerate(lst):
            x = -(half_w + 2.54) if side == "L" else (half_w + 2.54)
            pins.append((p, x, top - 2.54 * k, 0 if side == "L" else 180))
    return pins, half_w, half_h


def lib_symbol(part, prefixed):
    name = part["sym"]
    pins, hw, hh = _sym_geom(part)
    small = len(part["pins"]) <= 3
    full = f"{NAME}:{name}" if prefixed else name
    s = f'  (symbol "{full}"\n'
    s += (f'    (pin_names (offset 1.016){" (hide yes)" if part["sym"] in ("R", "C") else ""})\n'
          '    (exclude_from_sim no) (in_bom yes) (on_board yes)\n')
    ref_prefix = "".join(c for c in part["ref"] if c.isalpha())
    s += f'    (property "Reference" "{ref_prefix}" (at 0 {hh + 1.27:.2f} 0) {FONT})\n'
    s += f'    (property "Value" "{name}" (at 0 {-hh - 1.27:.2f} 0) {FONT})\n'
    s += f'    (property "Footprint" "" (at 0 0 0) {FONT_HIDE})\n'
    s += f'    (property "Datasheet" "~" (at 0 0 0) {FONT_HIDE})\n'
    s += f'    (property "Description" "{part["desc"]}" (at 0 0 0) {FONT_HIDE})\n'
    s += (f'    (symbol "{name}_0_1" (rectangle (start {-hw:.2f} {hh:.2f}) (end {hw:.2f} {-hh:.2f})'
          ' (stroke (width 0.254) (type default)) (fill (type background))))\n')
    s += f'    (symbol "{name}_1_1"\n'
    for (num, pname, _net, _side), x, y, ang in pins:
        s += (f'      (pin passive line (at {x:.2f} {y:.2f} {ang}) (length 2.54)'
              f' (name "{pname}" {FONT}) (number "{num}" {FONT}))\n')
    s += "    )\n    (embedded_fonts no)\n  )\n"
    return s


def write_schematic():
    seen, libsyms, plain = set(), "", ""
    for p in PARTS:
        if p["sym"] not in seen:
            seen.add(p["sym"])
            libsyms += lib_symbol(p, True)
            plain += lib_symbol(p, False)
    with open(os.path.join(HERE, f"{NAME}.kicad_sym"), "w", newline="\n") as f:
        f.write(f'(kicad_symbol_lib (version 20241209) (generator "parking_sensor_gen")\n{plain})\n')

    body = ""
    for p in PARTS:
        X, Y = p["sch"]
        pins, hw, hh = _sym_geom(p)
        su = uid("sym" + p["ref"])
        body += (f'(symbol (lib_id "{NAME}:{p["sym"]}") (at {X:.2f} {Y:.2f} 0) (unit 1)\n'
                 '  (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)\n'
                 f'  (uuid "{su}")\n'
                 f'  (property "Reference" "{p["ref"]}" (at {X:.2f} {Y - hh - 1.27:.2f} 0) {FONT})\n'
                 f'  (property "Value" "{p["value"]}" (at {X:.2f} {Y + hh + 1.27:.2f} 0) {FONT})\n'
                 f'  (property "Footprint" "{p["fp"]}" (at {X:.2f} {Y:.2f} 0) {FONT_HIDE})\n'
                 f'  (property "Datasheet" "~" (at {X:.2f} {Y:.2f} 0) {FONT_HIDE})\n'
                 f'  (property "Description" "{p["desc"]}" (at {X:.2f} {Y:.2f} 0) {FONT_HIDE})\n')
        for (num, *_r), *_g in pins:
            body += f'  (pin "{num}" (uuid "{uid("pin" + p["ref"] + num)}"))\n'
        body += (f'  (instances (project "{NAME}" (path "/{ROOT_UUID}"'
                 f' (reference "{p["ref"]}") (unit 1))))\n)\n')
        # every pin gets a global label (or a no-connect flag) at its endpoint
        for (num, _pn, net, side), x, y, _a in pins:
            px, py = X + x, Y - y
            if net is None:
                body += f'(no_connect (at {px:.2f} {py:.2f}) (uuid "{uid("nc" + p["ref"] + num)}"))\n'
                continue
            ang, just = (180, "right") if side == "L" else (0, "left")
            body += (f'(global_label "{net}" (shape passive) (at {px:.2f} {py:.2f} {ang})'
                     ' (fields_autoplaced yes)'
                     f' (effects (font (size 1.27 1.27)) (justify {just}))'
                     f' (uuid "{uid("gl" + p["ref"] + num)}")'
                     f' (property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {px:.2f} {py:.2f} 0)'
                     f' {FONT_HIDE}))\n')

    notes = [
        (25.4, 25.4, "POWER: solar -> TP4056 (charger + DW01A/FS8205A protection) -> SW1 -> ESP32-C3 5V pin"),
        (25.4, 101.6, "BATTERY SENSE: 1:2 divider (100k/100k, ~21uA) after SW1. 4.2V -> 2.1V on GPIO0 / ADC1_CH0"),
        (25.4, 162.56, "STATUS LED on GPIO1"),
        (25.4, 29.21, "U2 REWORK: replace the module R_PROG (1.2k, marked 122, on TP4056 pin 2) with 3.0k"),
        (25.4, 33.02, "-> 400 mA charge = 0.9C for the 450 mAh cell (stock 1 A = 2.2C)."),
        (25.4, 36.83, "USB on the SuperMini back-feeds the battery: switch SW1 OFF before plugging in USB."),
        (83.82, 125.73, "C2: bulk cap at ESP32 5V pin"),
        (200.66, 91.44, "MAGNETOMETER on I2C: SDA=GPIO8, SCL=GPIO9"),
        (200.66, 95.25, "(GY-271 has on-board pull-ups)"),
        (119.38, 154.94, "All connections are by net label. GPIO8/GPIO9 are strapping pins:"),
        (119.38, 158.75, "the GY-271 pull-ups hold them high, which is the normal-boot state."),
    ]
    for x, y, t in notes:
        body += (f'(text "{t}" (exclude_from_sim no) (at {x} {y} 0)'
                 f' (effects (font (size 1.524 1.524)) (justify left)) (uuid "{uid("txt" + t)}"))\n')

    sch = ('(kicad_sch (version 20250114) (generator "eeschema") (generator_version "9.0")\n'
           f'(uuid "{ROOT_UUID}")\n(paper "A4")\n'
           '(title_block (title "IoT Smart Parking Sensor") (date "2026-11-20") (rev "1.0")'
           ' (comment 1 "ESP32-C3 SuperMini + GY-271 + TP4056, solar/LiPo powered"))\n'
           f'(lib_symbols\n{libsyms})\n{body}'
           '(sheet_instances (path "/" (page "1")))\n(embedded_fonts no)\n)\n')
    with open(os.path.join(HERE, f"{NAME}.kicad_sch"), "w", newline="\n") as f:
        f.write(sch)


# =============================================================================
# PCB
# =============================================================================
def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def write_pcb():
    board = pcbnew.CreateEmptyBoard()
    nets = {}
    for n in NETS:
        nets[n] = pcbnew.NETINFO_ITEM(board, n)
        board.Add(nets[n])

    fps = {}
    for p in PARTS:
        lib, fpname = p["fp"].split(":")
        libpath = (os.path.join(HERE, f"{NAME}.pretty") if lib == NAME
                   else os.path.join(STOCK_FP, lib + ".pretty"))
        fp = pcbnew.FootprintLoad(libpath, fpname)
        assert fp, f"footprint not found: {p['fp']}"
        fp.SetFPIDAsString(p["fp"])
        board.Add(fp)
        fp.SetReference(p["ref"])
        fp.SetValue(p["value"])
        x, y, rot = p["pcb"]
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(mm(x, y))
        fp.SetPath(pcbnew.KIID_PATH(f"/{uid('sym' + p['ref'])}"))
        try:
            fp.SetSheetfile(f"{NAME}.kicad_sch")
            fp.SetSheetname("/")
        except AttributeError:
            pass
        fp.GetField(pcbnew.FIELD_T_DESCRIPTION).SetText(p["desc"])
        for num, pname, net, _s in p["pins"]:
            # NC pads get the same "unconnected-(...)" net eeschema gives them
            net = net or f"unconnected-({p['ref']}-{pname}-Pad{num})"
            if net not in nets:
                nets[net] = pcbnew.NETINFO_ITEM(board, net)
                board.Add(nets[net])
            fp.FindPadByNumber(num).SetNet(nets[net])
        ref = fp.Reference()
        if p["ref"] in ("R1", "R2", "C1", "C2"):      # under the ESP32 module: label on Fab only
            ref.SetLayer(pcbnew.F_Fab)
        elif p["ref"] in ("J1", "J2", "SW1"):   # labelled by board text instead
            ref.SetVisible(False)
        elif p["ref"] == "U2":                  # default spot collides with J2
            ref.SetPosition(mm(11.0, 23.4))
        fps[p["ref"]] = fp

    # 2-pad parts whose pad 1 must face a given direction for the routes above
    def face(ref, pad1_dir):
        fp = fps[ref]
        a, b = fp.FindPadByNumber("1").GetPosition(), fp.FindPadByNumber("2").GetPosition()
        bad = {"down": a.y < b.y, "up": a.y > b.y, "left": a.x > b.x}[pad1_dir]
        if bad:
            fp.SetOrientationDegrees(fp.GetOrientationDegrees() + 180)
    face("R1", "down")
    face("R2", "up")
    face("C1", "up")
    face("R3", "left")
    face("C2", "left")

    for i, (hx, hy) in enumerate(HOLES):
        h = pcbnew.FootprintLoad(os.path.join(STOCK_FP, "MountingHole.pretty"), "MountingHole_3.2mm_M3")
        h.SetFPIDAsString("MountingHole:MountingHole_3.2mm_M3")
        board.Add(h)
        h.SetReference(f"H{i + 1}")
        h.SetValue("M3")
        h.SetPosition(mm(hx, hy))
        h.Reference().SetVisible(False)
        h.SetBoardOnly(True)
        h.SetExcludedFromBOM(True)
        h.SetExcludedFromPosFiles(True)

    # outline
    corners = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H), (0, 0)]
    for a, b in zip(corners, corners[1:]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(mm(*a))
        s.SetEnd(mm(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(pcbnew.FromMM(0.1))
        board.Add(s)

    layer = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}

    def pt(q):
        if isinstance(q[0], str):
            return fps[q[0]].FindPadByNumber(q[1]).GetPosition()
        return mm(*q)

    for net, lay, w, pts in ROUTES:
        ps = [pt(q) for q in pts]
        for a, b in zip(ps, ps[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(a)
            t.SetEnd(b)
            t.SetWidth(pcbnew.FromMM(w))
            t.SetLayer(layer[lay])
            t.SetNet(nets[net])
            board.Add(t)
    for net, x, y in VIAS:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(mm(x, y))
        v.SetDrill(pcbnew.FromMM(0.4))
        v.SetWidth(pcbnew.FromMM(0.8))
        v.SetNet(nets[net])
        board.Add(v)

    def rect_outline(z, x1, y1, x2, y2):
        ol = z.Outline()
        ol.NewOutline()
        for x, y in [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]:
            p = mm(x, y)
            ol.Append(p.x, p.y)

    # bottom GND pour (thermal reliefs are the zone default)
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.B_Cu)
    z.SetNet(nets["GND"])
    z.SetZoneName("GND_BOTTOM")
    z.SetLocalClearance(pcbnew.FromMM(0.3))
    z.SetMinThickness(pcbnew.FromMM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    rect_outline(z, 0.3, 0.3, BOARD_W - 0.3, BOARD_H - 0.3)
    board.Add(z)

    for name, (x1, y1, x2, y2) in (("ANTENNA_KEEPOUT", ANT_KEEPOUT), ("MAGNETOMETER_KEEPOUT", MAG_KEEPOUT)):
        k = pcbnew.ZONE(board)
        k.SetIsRuleArea(True)
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.F_Cu)
        ls.AddLayer(pcbnew.B_Cu)
        k.SetLayerSet(ls)
        k.SetZoneName(name)
        k.SetDoNotAllowTracks(True)
        k.SetDoNotAllowVias(True)
        k.SetDoNotAllowZoneFills(True)
        k.SetDoNotAllowPads(False)
        k.SetDoNotAllowFootprints(False)
        rect_outline(k, x1, y1, x2, y2)
        board.Add(k)

    def text(s, x, y, size=1.0, lay=pcbnew.F_SilkS):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(s)
        t.SetPosition(mm(x, y))
        t.SetLayer(lay)
        t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
        t.SetTextThickness(pcbnew.FromMM(size * 0.15))
        board.Add(t)

    text("ANTENNA KEEP-OUT", 33.0, 18.0, 0.9)
    text("NO COPPER", 33.0, 19.6, 0.9)
    text("SW1 OFF BEFORE USB!", U1_X, 14.6, 0.9)
    text("PARKING SENSOR v1.0", 33.0, 3.0, 1.2)
    text("J2 SOLAR", 19.5, 1.6, 0.8)
    text("J1 BATT", 4.6, 37.6, 0.8)
    text("SW1 PWR", 18.4, 39.6, 0.8)
    text("MAG KEEP-OUT (both layers)", 51.5, 13.5, 0.6, pcbnew.F_Fab)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(os.path.join(HERE, f"{NAME}.kicad_pcb"), board)


# =============================================================================
# Project files, BOM, netlist
# =============================================================================
def write_project_files():
    pro = os.path.join(HERE, f"{NAME}.kicad_pro")
    data = {}
    if os.path.exists(pro):
        with open(pro) as f:
            data = json.load(f)
    data.setdefault("meta", {})["filename"] = f"{NAME}.kicad_pro"
    data["sheets"] = [[ROOT_UUID, "Root"]]
    with open(pro, "w", newline="\n") as f:
        json.dump(data, f, indent=2)

    with open(os.path.join(HERE, "fp-lib-table"), "w", newline="\n") as f:
        f.write(f'(fp_lib_table\n  (version 7)\n  (lib (name "{NAME}")(type "KiCad")'
                f'(uri "${{KIPRJMOD}}/{NAME}.pretty")(options "")(descr "Module footprints"))\n)\n')
    with open(os.path.join(HERE, "sym-lib-table"), "w", newline="\n") as f:
        f.write(f'(sym_lib_table\n  (version 7)\n  (lib (name "{NAME}")(type "KiCad")'
                f'(uri "${{KIPRJMOD}}/{NAME}.kicad_sym")(options "")(descr "Module symbols"))\n)\n')

    cond = " || ".join(f"A.NetName == '{n}'" for n in POWER_NETS)
    with open(os.path.join(HERE, f"{NAME}.kicad_dru"), "w", newline="\n") as f:
        f.write('(version 1)\n'
                f'(rule "Power tracks >= 0.6mm"\n  (condition "A.Type == \'Track\' && ({cond})")\n'
                '  (constraint track_width (min 0.6mm)))\n'
                '(rule "Signal tracks >= 0.25mm"\n  (condition "A.Type == \'Track\'")\n'
                '  (constraint track_width (min 0.25mm)))\n')


def write_bom_netlist():
    groups = {}
    for p in PARTS:
        key = (p["value"], p["fp"], p["bom"])
        groups.setdefault(key, []).append(p["ref"])
    rows = [dict(refs=",".join(r), qty=len(r), value=v, footprint=fp, part=b)
            for (v, fp, b), r in groups.items()]
    rows.append(dict(refs="U2 rework", qty=1, value="3.0k 1%", footprint="0603 (on the TP4056 module)",
                     part="Replaces the module R_PROG 1.2k -> 400 mA charge current"))
    rows.append(dict(refs="H1-H4", qty=4, value="M3", footprint="MountingHole:MountingHole_3.2mm_M3",
                     part="M3 screw/standoff (hole only, nothing to solder)"))
    with open(os.path.join(HERE, "bom.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(HERE, "bom.json"), "w") as f:
        json.dump(rows, f, indent=2)

    nl = {n: [dict(ref=r, pad=num, pin=name) for r, num, name in nodes] for n, nodes in NETS.items()}
    with open(os.path.join(HERE, "netlist.json"), "w") as f:
        json.dump(nl, f, indent=2)
    with open(os.path.join(HERE, "netlist.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["net", "ref", "pad", "pin"])
        for n, nodes in NETS.items():
            for r, num, name in nodes:
                w.writerow([n, r, num, name])


# =============================================================================
# Verification
# =============================================================================
def cli(*args):
    r = subprocess.run([KICAD_CLI, *args], capture_output=True, text=True, cwd=HERE)
    if r.returncode not in (0, 5):   # 5 = violations found (reported separately)
        sys.exit(f"kicad-cli {' '.join(args)} failed:\n{r.stdout}\n{r.stderr}")
    return r


def verify():
    cli("sch", "erc", "--severity-all", "--format", "json", "-o", "erc.json", f"{NAME}.kicad_sch")
    cli("pcb", "drc", "--schematic-parity", "--refill-zones", "--severity-all", "--format", "json",
        "-o", "drc.json", f"{NAME}.kicad_pcb")
    cli("sch", "export", "netlist", "--format", "kicadxml", "-o", "kicad_netlist.xml", f"{NAME}.kicad_sch")

    # self-check: KiCad's own netlist must equal NETS
    got = {}
    for net in ET.parse(os.path.join(HERE, "kicad_netlist.xml")).getroot().iter("net"):
        nodes = {(n.get("ref"), n.get("pin")) for n in net.iter("node")}
        name = net.get("name").lstrip("/")
        if not name.startswith("unconnected-"):
            got[name] = nodes
    want = {n: {(r, num) for r, num, _ in nodes} for n, nodes in NETS.items()}
    assert got == want, f"netlist mismatch:\n got  {got}\n want {want}"

    def summary(path, key):
        with open(os.path.join(HERE, path)) as f:
            d = json.load(f)
        items = []
        for section in [d] + d.get("sheets", []):
            for k in key:
                items += section.get(k, [])
        return items

    erc = summary("erc.json", ["violations"])
    drc = summary("drc.json", ["violations", "unconnected_items", "schematic_parity"])
    for v in erc + drc:
        print(f'  [{v["severity"]}] {v["type"]}: {v["description"]}',
              "|", "; ".join(i.get("description", "") for i in v.get("items", [])))
    print(f"netlist OK ({len(want)} nets). ERC: {len(erc)} issue(s). DRC: {len(drc)} issue(s).")


def export():
    pcb = f"{NAME}.kicad_pcb"
    cli("sch", "export", "svg", "-o", "diagrams", "--exclude-drawing-sheet", f"{NAME}.kicad_sch")
    cli("sch", "export", "pdf", "-o", "diagrams/schematic.pdf", f"{NAME}.kicad_sch")
    for name, layers in (("pcb_top", "F.Cu,F.SilkS,Edge.Cuts,User.Drawings"),
                         ("pcb_bottom", "B.Cu,Edge.Cuts"),
                         ("pcb_assembly", "F.Fab,F.SilkS,F.CrtYd,Edge.Cuts")):
        cli("pcb", "export", "svg", "-l", layers, "--mode-single", "--exclude-drawing-sheet",
            "--fit-page-to-board", "-o", f"diagrams/{name}.svg", pcb)
    cli("pcb", "render", "--side", "top", "-w", "1600", "-h", "1200", "-o", "diagrams/render_top.png", pcb)
    cli("pcb", "render", "--side", "bottom", "-w", "1600", "-h", "1200", "-o", "diagrams/render_bottom.png", pcb)
    cli("pcb", "export", "gerbers", "-l", "F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,F.Paste,Edge.Cuts",
        "-o", "gerbers/", pcb)
    cli("pcb", "export", "drill", "-o", "gerbers/", pcb)
    cli("pcb", "export", "pos", "--side", "front", "--units", "mm", "--format", "csv",
        "-o", "gerbers/positions_top.csv", pcb)


if __name__ == "__main__":
    write_footprints()
    write_schematic()
    write_project_files()
    write_pcb()
    write_bom_netlist()
    verify()
    export()
