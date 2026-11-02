// --- BLE CONFIGURATION CONSTANTS ---
const SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b";
const CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8";
const DEVICE_NAME = "Temp Bridge";

// Your complete configuration object
const fullConfig = {
  ssid: "<wifi username>",
  pass: "<wifi pass>",
  host: "https://queuerx.tail326833.ts.net:8443",
  secret: "<your secret>",
  interval: 60,
  github_token: "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"
};

async function provisionDevice() {
  try {
    console.log("🔍 Requesting Bluetooth Device...");
    
    // Request device matching your branding or advertising service
    const device = await navigator.bluetooth.requestDevice({
      filters: [{ name: DEVICE_NAME }],
      optionalServices: [SERVICE_UUID]
    });

    console.log(`📡 Connecting to device: ${device.name}...`);
    const server = await device.gatt.connect();

    console.log("📂 Getting Primary Service...");
    const service = await server.getPrimaryService(SERVICE_UUID);

    console.log("✍️ Getting Characteristic...");
    const characteristic = await service.getCharacteristic(CHARACTERISTIC_UUID);

    // Serialize the full configuration into a single clean JSON string
    const payload = JSON.stringify({
      ssid: fullConfig.ssid,
      pass: fullConfig.pass,
      host: fullConfig.host,
      secret: fullConfig.secret,
      interval: fullConfig.interval,
      github_token: fullConfig.github_token
    });

    const encoder = new TextEncoder();

    console.log("📤 Sending Complete Configuration Payload...");
    await characteristic.writeValue(encoder.encode(payload));
    console.log("✅ Configuration sent successfully! ESP32 will save and restart.");

    // Disconnect cleanly after a brief moment
    await new Promise(resolve => setTimeout(resolve, 1500));
    if (device.gatt.connected) {
      device.gatt.disconnect();
      console.log("🔌 BLE connection closed.");
    }

  } catch (error) {
    console.error("❌ Provisioning failed: ", error);
  }
}

// Run the function directly in your browser console:
// provisionDevice();
