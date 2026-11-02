#!/usr/bin/env python3
"""
flash_device.py
Production flashing script for QueueRX ESP32-S3 e-Paper devices.
Flashes factory firmware (Bootloader + Partitions + OTA data + App) in one command.
Supports single-shot flashing or continuous batch flashing for multiple devices.
"""

import os
import sys
import time
import argparse
import shutil
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist")
FACTORY_BIN = os.path.join(DIST_DIR, "factory_firmware_16MB.bin")
APP_BIN = os.path.join(DIST_DIR, "firmware.bin")

try:
    import serial.tools.list_ports
except ImportError:
    serial = None

def find_esptool():
    """Find a functional esptool executable or module that has all dependencies (including intelhex)."""
    # 1. Check if current sys.executable has esptool and intelhex
    try:
        import esptool
        import intelhex
        return [sys.executable, "-m", "esptool"]
    except ImportError:
        pass

    # 2. Check candidate Python environments that have esptool & intelhex installed
    candidates = [
        "/opt/anaconda3/bin/python3",
        "/opt/anaconda3/bin/python",
        os.path.expanduser("~/.platformio/penv/bin/python"),
        shutil.which("python3"),
        shutil.which("python"),
    ]
    for py in candidates:
        if py and os.path.exists(py):
            try:
                res = subprocess.run(
                    [py, "-c", "import esptool, intelhex; print('OK')"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=2
                )
                if res.returncode == 0 and "OK" in res.stdout:
                    return [py, "-m", "esptool"]
            except Exception:
                continue

    # 3. Check standalone esptool CLI in PATH
    for cmd in ["esptool.py", "esptool"]:
        p = shutil.which(cmd)
        if p:
            return [p]

    # 4. Check PlatformIO tool package using penv python if present
    pio_esptool = os.path.expanduser("~/.platformio/packages/tool-esptoolpy/esptool.py")
    penv_py = os.path.expanduser("~/.platformio/penv/bin/python")
    if os.path.exists(pio_esptool):
        if os.path.exists(penv_py):
            return [penv_py, pio_esptool]
        return [sys.executable, pio_esptool]

    return [sys.executable, "-m", "esptool"]

def list_candidate_ports():
    """List available serial ports that resemble ESP32 devices."""
    if not serial:
        return []
    
    candidates = []
    for port in serial.tools.list_ports.comports():
        desc = (port.description or "").lower()
        hwid = (port.hwid or "").lower()
        dev = port.device
        
        # Match ESP32 USB CDC, CP210x, CH340, FTDI, usbmodem, ttyACM
        if any(keyword in dev.lower() for keyword in ["usbmodem", "usbserial", "ttyacm", "ttyusb"]) or \
           any(keyword in desc for keyword in ["esp32", "usb jtag", "serial", "uart", "cp210", "ch340"]) or \
           "303a:" in hwid:  # Espressif Vendor ID 0x303A
            candidates.append(port.device)
            
    return candidates

def detect_single_port():
    """Auto-detect the first connected ESP32-S3 port."""
    ports = list_candidate_ports()
    if not ports:
        return None
    return ports[0]

def flash_target(port, baud, erase=False, app_only=False):
    """Flash firmware to target board on given port."""
    esptool = find_esptool()
    
    bootloader_bin = os.path.join(DIST_DIR, "bootloader.bin")
    partitions_bin = os.path.join(DIST_DIR, "partitions.bin")
    boot_app0_bin = os.path.join(DIST_DIR, "boot_app0.bin")
    app_bin = APP_BIN
    factory_bin = FACTORY_BIN

    # Check for individual partition files (matches PlatformIO upload exactly)
    individual_files_exist = all(os.path.exists(p) for p in [bootloader_bin, partitions_bin, app_bin])

    if app_only:
        mode_desc = "App-Only Firmware (0x10000)"
        flash_args = ["0x10000", app_bin]
    elif individual_files_exist:
        mode_desc = "Complete System Partitions (0x0, 0x8000, 0xe000, 0x10000)"
        flash_args = [
            "0x0000", bootloader_bin,
            "0x8000", partitions_bin
        ]
        if os.path.exists(boot_app0_bin):
            flash_args.extend(["0xe000", boot_app0_bin])
        flash_args.extend(["0x10000", app_bin])
    elif os.path.exists(factory_bin):
        mode_desc = "Full Merged Factory Image (0x0)"
        flash_args = ["0x0", factory_bin]
    else:
        print(f"\n❌ Target binaries not found in {DIST_DIR}!")
        print("💡 Run './build_and_package.sh' or 'python package_firmware.py' first!")
        return False

    print("\n" + "-" * 55)
    print(f" 🔌 Target Port:  {port}")
    print(f" ⚡ Baud Rate:    {baud}")
    print(f" 📦 Flash Mode:   {mode_desc}")
    print(f" ⚙️  SPI Mode:     DIO @ 80MHz (Required for dio_opi Octal PSRAM)")
    print("-" * 55)

    # 1. Optional complete chip erase
    if erase:
        print("\n🧹 Erasing entire flash chip (clearing NVS & all data)...")
        erase_cmd = esptool + [
            "--chip", "esp32s3",
            "--port", port,
            "--baud", str(baud),
            "erase_flash"
        ]
        res = subprocess.run(erase_cmd)
        if res.returncode != 0:
            print("❌ Erase failed.")
            return False

    # 2. Write flash
    # CRITICAL: Waveshare ESP32-S3 e-Paper uses DIO Flash + Octal PSRAM (dio_opi).
    # Flash mode MUST be 'dio', NEVER 'qio', or the device will brownout/crash on boot!
    print(f"\n🚀 Writing flash partitions...")
    flash_cmd = esptool + [
        "--chip", "esp32s3",
        "--port", port,
        "--baud", str(baud),
        "--before", "default_reset",
        "--after", "hard_reset",
        "write_flash",
        "-z",
        "--flash_mode", "dio",
        "--flash_freq", "80m",
        "--flash_size", "16MB",
    ] + flash_args

    start_time = time.time()
    res = subprocess.run(flash_cmd)
    elapsed = time.time() - start_time

    if res.returncode == 0:
        print("\n" + "=" * 55)
        print(f" ✅ Flashing SUCCESSFUL! (Took {elapsed:.1f}s)")
        print(f" 🔄 Device reset and booting firmware.")
        print("=" * 55)
        return True
    else:
        print("\n" + "=" * 55)
        print(" ❌ Flashing FAILED!")
        print(" 💡 Tips:")
        print("    1. Close any open Serial Monitor or Terminal on this port.")
        print("    2. Hold BOOT button on the ESP32 while plugging in to force download mode.")
        print("=" * 55)
        return False

def run_batch_mode(baud, erase=False, app_only=False):
    """Continuously monitor USB ports and flash devices sequentially."""
    print("=" * 60)
    print(" 🔄 BATCH FLASHING MODE ACTIVE")
    print(" Plug in an ESP32-S3 device to flash automatically.")
    print(" Press Ctrl+C at any time to exit.")
    print("=" * 60)

    flashed_ports = set()
    device_count = 0

    try:
        while True:
            current_ports = set(list_candidate_ports())

            # Detect newly plugged ports
            new_ports = current_ports - flashed_ports

            # Remove disconnected ports from flashed tracker so they can be reflashed if replugged
            disconnected = flashed_ports - current_ports
            if disconnected:
                for p in disconnected:
                    flashed_ports.remove(p)

            if new_ports:
                port = list(new_ports)[0]
                print(f"\n[+] Detected new device on {port}!")
                time.sleep(1.0)  # Wait for USB enumeration to stabilize

                success = flash_target(port, baud, erase=erase, app_only=app_only)
                flashed_ports.add(port)

                if success:
                    device_count += 1
                    print(f"\n🎉 Total Devices Flashed: {device_count}")
                    print("➡️  Unplug this device and plug in the next one...")
                else:
                    print("⚠️  Device flashing failed. Please replug or check port.")

            time.sleep(0.8)

    except KeyboardInterrupt:
        print(f"\n\nExiting Batch Mode. Total devices flashed: {device_count}")

def main():
    parser = argparse.ArgumentParser(description="QueueRX ESP32-S3 Production Flasher")
    parser.add_argument("-p", "--port", help="Serial port (e.g. /dev/cu.usbmodem1101, COM3)")
    parser.add_argument("-b", "--baud", type=int, default=921600, help="Baud rate (default: 921600)")
    parser.add_argument("-e", "--erase", action="store_true", help="Erase entire flash chip before writing")
    parser.add_argument("-a", "--app-only", action="store_true", help="Flash only firmware.bin (offset 0x10000)")
    parser.add_argument("--batch", action="store_true", help="Batch mode: flash devices continuously on plug-in")

    args = parser.parse_args()

    # Ensure binaries exist
    bootloader_bin = os.path.join(DIST_DIR, "bootloader.bin")
    has_binaries = os.path.exists(FACTORY_BIN) or os.path.exists(APP_BIN) or os.path.exists(bootloader_bin)
    if not has_binaries:
        pkg_script = os.path.join(PROJECT_DIR, "package_firmware.py")
        if os.path.exists(pkg_script):
            print(f"⚠️  Binaries not found in {DIST_DIR}. Running packaging script first...")
            subprocess.run([sys.executable, pkg_script])
        else:
            print(f"❌ Error: No firmware binaries found in '{DIST_DIR}'!")
            print(f"   Please ensure the 'dist/' folder containing firmware files is present.")
            sys.exit(1)

    if args.batch:
        run_batch_mode(args.baud, erase=args.erase, app_only=args.app_only)
        return

    # Single-shot mode
    port = args.port or detect_single_port()
    if not port:
        print("❌ No ESP32 device detected! Please connect your board via USB-C.")
        print("   If already connected, specify the port manually with: -p <PORT>")
        sys.exit(1)

    success = flash_target(port, args.baud, erase=args.erase, app_only=args.app_only)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

