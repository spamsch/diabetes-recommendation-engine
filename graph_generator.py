#!/usr/bin/env python3
"""
Standalone script for generating glucose graphs from stored data
"""

import argparse
import sys
from datetime import datetime, timedelta
from src.config import Settings
from src.database import GlucoseDatabase
from src.visualization import GlucoseGrapher

def main():
    parser = argparse.ArgumentParser(description='Generate glucose graphs')
    parser.add_argument('--hours', type=int, default=24,
                       help='Number of hours of data to include (default: 24)')
    parser.add_argument('--type', choices=['timeline', 'trend', 'daily'], 
                       default='timeline',
                       help='Type of graph to generate')
    parser.add_argument('--output', type=str,
                       help='Output file path (optional, will display if not provided)')
    parser.add_argument('--env-file', default='.env',
                       help='Environment file path')
    parser.add_argument('--stats', action='store_true',
                       help='Show statistical summary')
    
    args = parser.parse_args()
    
    try:
        # Initialize components
        settings = Settings(args.env_file)
        db = GlucoseDatabase(settings.database_path)
        grapher = GlucoseGrapher(settings)
        
        # Get readings from specified time period
        since_time = datetime.now() - timedelta(hours=args.hours)
        readings = db.get_readings_since(since_time)
        
        if not readings:
            print(f"No readings found in the last {args.hours} hours")
            return
        
        print(f"Found {len(readings)} readings from the last {args.hours} hours")
        
        # Show statistics if requested
        if args.stats:
            stats = grapher.create_statistics_summary(readings)
            print("\nStatistical Summary:")
            print(f"  Count: {stats['count']} readings")
            print(f"  Mean: {stats['mean']:.1f} mg/dL")
            print(f"  Range: {stats['min']:.0f} - {stats['max']:.0f} mg/dL")
            print(f"  Time in Range: {stats['target_range_percentage']:.1f}%")
            print(f"  Time Below Range: {stats['low_percentage']:.1f}%")
            print(f"  Time Above Range: {stats['high_percentage']:.1f}%")
            print()
        
        # Generate graph
        if args.type == 'timeline':
            result = grapher.create_glucose_timeline(readings, save_path=args.output)
        elif args.type == 'trend':
            # Need trend analysis for trend graph
            from src.analysis import TrendAnalyzer
            analyzer = TrendAnalyzer(settings)
            trend_analysis = analyzer.analyze_trend(readings[:10])  # Use recent readings
            result = grapher.create_trend_analysis_graph(readings, trend_analysis, args.output)
        elif args.type == 'daily':
            result = grapher.create_daily_summary(readings, save_path=args.output)
        
        if result:
            if args.output:
                print(f"Graph saved to: {result}")
            else:
                print("Graph displayed")
        else:
            print("Failed to generate graph")
    
    except Exception as e:
        print(f"Error generating graph: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()