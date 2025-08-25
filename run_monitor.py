#!/usr/bin/env python3
"""
Quick start script for the Glucose Monitoring System
"""

import os
import sys
import argparse

def check_config():
    """Check if configuration file exists and is valid"""
    if not os.path.exists('.env'):
        print("❌ Configuration file '.env' not found!")
        print("📋 Please copy .env.example to .env and configure your settings:")
        print("   cp .env.example .env")
        print("   # Then edit .env with your Dexcom credentials")
        return False
    
    # Check if basic required settings exist
    try:
        with open('.env', 'r') as f:
            content = f.read()
            if 'your_dexcom_username' in content or 'DEXCOM_USERNAME=' not in content:
                print("⚠️  Please update your .env file with actual Dexcom credentials")
                return False
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
        return False
    
    print("✅ Configuration file looks good!")
    return True

def main():
    parser = argparse.ArgumentParser(description='Start Glucose Monitoring System')
    parser.add_argument('--mock', action='store_true',
                       help='Use mock data instead of real Dexcom sensor')
    parser.add_argument('--test-recs', action='store_true',
                       help='Run recommendation tests')
    parser.add_argument('--graph', choices=['timeline', 'trend', 'daily'],
                       help='Generate a graph instead of monitoring')
    parser.add_argument('--hours', type=int, default=24,
                       help='Hours of data for graph generation')
    
    args = parser.parse_args()
    
    print("🩸 Glucose Monitoring System")
    print("=" * 50)
    
    # Handle special modes
    if args.test_recs:
        print("🧪 Running recommendation algorithm tests...")
        os.system("pytest tests/test_recommendations.py -v")
        return
    
    if args.graph:
        print(f"📊 Generating {args.graph} graph for last {args.hours} hours...")
        cmd = f"python graph_generator.py --type {args.graph} --hours {args.hours} --stats"
        os.system(cmd)
        return
    
    # Check configuration for monitoring mode
    if not args.mock and not check_config():
        print("\n💡 Use --mock flag to run with simulated data for testing:")
        print("   python run_monitor.py --mock")
        return
    
    # Start monitoring
    if args.mock:
        print("🧪 Starting with mock Dexcom data (for testing)")
        cmd = "python -m src.main --mock"
    else:
        print("📡 Starting with real Dexcom sensor data")
        print("⚠️  Make sure your Dexcom Share is working and credentials are correct")
        cmd = "python -m src.main"
    
    print("\n🏃 Starting glucose monitoring...")
    print("Press Ctrl+C to stop monitoring")
    print("-" * 50)
    
    try:
        os.system(cmd)
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("💡 Try running with --mock flag for testing")

if __name__ == "__main__":
    main()