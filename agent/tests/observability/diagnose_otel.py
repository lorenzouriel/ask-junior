"""
Diagnostic script to check OpenTelemetry connectivity.
"""
import socket
import os
from dotenv import load_dotenv

load_dotenv()

endpoint = os.getenv("OTEL_ENDPOINT", "http://localhost:4317")

# Parse endpoint
if "://" in endpoint:
    protocol, hostport = endpoint.split("://")
else:
    hostport = endpoint

if ":" in hostport:
    host, port = hostport.rsplit(":", 1)
    port = int(port)
else:
    host = hostport
    port = 4317

print("=" * 60)
print("OpenTelemetry Connectivity Diagnostic")
print("=" * 60)
print(f"Endpoint: {endpoint}")
print(f"Host: {host}")
print(f"Port: {port}")
print("=" * 60)

# Test TCP connection
print("\nTesting TCP connection...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((host, port))
    sock.close()

    if result == 0:
        print(f"[OK] Successfully connected to {host}:{port}")
        print("  The OTEL collector is reachable!")
    else:
        print(f"[FAIL] Failed to connect to {host}:{port}")
        print(f"  Error code: {result}")
        print("  The OTEL collector may not be running or not accessible.")
except Exception as e:
    print(f"[ERROR] Error testing connection: {e}")

# Test gRPC port 4317
print("\nTesting gRPC port (4317)...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((host if host != 'localhost' else 'localhost', 4317))
    sock.close()

    if result == 0:
        print(f"[OK] gRPC port 4317 is open")
    else:
        print(f"[FAIL] gRPC port 4317 is not accessible")
except Exception as e:
    print(f"[ERROR] Error: {e}")

# Test HTTP port 4318
print("\nTesting HTTP port (4318)...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((host if host != 'localhost' else 'localhost', 4318))
    sock.close()

    if result == 0:
        print(f"[OK] HTTP port 4318 is open")
    else:
        print(f"[FAIL] HTTP port 4318 is not accessible")
except Exception as e:
    print(f"[ERROR] Error: {e}")

print("\n" + "=" * 60)
print("Recommendations:")
print("=" * 60)
print("1. Ensure OTEL collector is running:")
print("   docker ps | grep otel-collector")
print("\n2. Check collector logs:")
print("   docker logs otel-collector --tail 50")
print("\n3. Verify ports are exposed:")
print("   docker port otel-collector")
print("\n4. If using Docker, ensure host.docker.internal or correct IP")
print("=" * 60)
