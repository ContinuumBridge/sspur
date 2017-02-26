import struct

FUNCTIONS = {
    "include_req": 0x00,
    "include_grant": 0x02,
    "reinclude": 0x04,
    "config": 0x05,
    "send_battery": 0x07,
    "woken_up": 0xAA,
    "acknowledge": 0xAC,
    "alert": 0xAE,
    "battery_status": 0xBA,
    "beacon": 0xBE
}

data = {
    "destination": 1024,
    "function": "woken_up",
    "data": "A bridge too far"
}

source_id = 50000
wakeupInterval = 7200
bridge = True

m = ""
m += struct.pack(">H", data["destination"])
m += struct.pack(">H", source_id)
m+= struct.pack("B", FUNCTIONS[data["function"]])
m+= struct.pack("B", 0)  # Placeholder for length
if bridge:
    m+= struct.pack(">H", wakeupInterval)
if "data" in data:
    m += data["data"]
length = struct.pack("B", len(m))
print ("Length: %s, %s", len(m), length)
print ("Before length: %s", m)
message = m[:5] + length + m[6:]
print ("After length: %s", message)
#print("Payload: %s" %(message[8:]))

# Decode
destination = struct.unpack(">H", message[0:2])
source = struct.unpack(">H", message[2:4])
function = struct.unpack("B", message[4])
length = struct.unpack("B", message[5])
if bridge:
    wakeup = struct.unpack(">H", message[6:8])
    payload = message[8:]
else:
    wakeup = ""
    payload = message[6:]
print("destination: %s, source: %s, function: %s, length: %s, wakeup: %s" %(destination, source, function, length, wakeup))
print("payload: %s" %(payload))
