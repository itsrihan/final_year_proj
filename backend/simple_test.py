#!/usr/bin/env python3
"""
Simple test to verify camera-off reset works.
"""

import asyncio
import json
import websockets

WS_URL = "ws://localhost:8001/ws/asl"

async def test_camera_off():
    """Test: Camera OFF sends reset signal"""
    print("\nTesting: Camera OFF = Hard Reset to READY")
    print("-" * 50)
    
    try:
        async with websockets.connect(WS_URL) as ws:
            # Send camera_on=false (simulating camera turned off)
            payload = {
                "frame": None,
                "asl_enabled": True,
                "camera_on": False
            }
            print(f"Sending: {json.dumps(payload, indent=2)}")
            await ws.send(json.dumps(payload))
            
            # Receive response
            response_json = await ws.recv()
            response = json.loads(response_json)
            
            print(f"\nReceived response:")
            print(json.dumps(response, indent=2))
            
            # Verify response
            checks = {
                "text == 'Waiting...'": response.get("text") == "Waiting...",
                "confidence == 0.0": response.get("confidence") == 0.0,
                "asl_capture_state == 'ready'": response.get("asl_capture_state") == "ready",
                "captured_frames == 0": response.get("captured_frames") == 0,
                "required_frames == 45": response.get("required_frames") == 45,
                "hands_detected == False": response.get("hands_detected") == False,
            }
            
            print("\nValidation:")
            all_pass = True
            for check, result in checks.items():
                status = "✓" if result else "✗"
                print(f"  {status} {check}")
                all_pass = all_pass and result
            
            if all_pass:
                print("\n✓ TEST PASSED: Camera-off reset works correctly!")
            else:
                print("\n✗ TEST FAILED: Some checks failed")
            
            return all_pass
            
    except Exception as e:
        print(f"✗ Connection error: {e}")
        print("  Make sure backend is running on localhost:8001")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_camera_off())
    exit(0 if result else 1)
