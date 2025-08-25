#!/usr/bin/env python3
"""
Debug script to inspect the pydexcom GlucoseReading object structure
"""

import os
from src.config import Settings
from pydexcom import Dexcom

def main():
    try:
        # Load settings
        settings = Settings()
        
        # Connect to Dexcom
        dexcom = Dexcom(
            username=settings.dexcom_username,
            password=settings.dexcom_password,
            ous=settings.dexcom_ous
        )
        
        print("🔍 Connected to Dexcom, inspecting glucose reading structure...")
        
        # Get a reading
        bg = dexcom.get_current_glucose_reading()
        
        if bg is None:
            print("❌ No glucose reading available")
            return
        
        print(f"📊 Raw glucose reading object: {bg}")
        print(f"📊 Object type: {type(bg)}")
        print(f"📊 Available attributes: {dir(bg)}")
        
        # Try different attribute names
        print("\n🔎 Trying different attribute names:")
        
        attrs_to_check = [
            'datetime', 'time', 'timestamp',
            'value', 'mg_dl', 'glucose', 'level',
            'trend_description', 'trend', 'direction',
            'mmol_l'  # Some regions use mmol/L
        ]
        
        for attr in attrs_to_check:
            try:
                val = getattr(bg, attr, 'NOT_FOUND')
                if val != 'NOT_FOUND':
                    print(f"  ✅ {attr}: {val} ({type(val)})")
            except Exception as e:
                print(f"  ❌ {attr}: Error - {e}")
        
        # Also check if it's iterable or has other methods
        print(f"\n📋 String representation: {str(bg)}")
        print(f"📋 Repr: {repr(bg)}")
        
    except Exception as e:
        print(f"❌ Error debugging Dexcom: {e}")
        print(f"💡 Make sure your .env file has correct DEXCOM_USERNAME and DEXCOM_PASSWORD")

if __name__ == "__main__":
    main()