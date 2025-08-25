import logging
import threading
import sys
from datetime import datetime
from typing import Optional, Callable, Dict
from ..database import GlucoseDatabase
from ..config import Settings
from ..commands import CommandProcessor
from ..commands.formatters import TerminalFormatter

logger = logging.getLogger(__name__)

class UserInputHandler:
    """Handles interactive terminal input for logging insulin and carbs"""
    
    def __init__(self, db: GlucoseDatabase, settings: Settings):
        self.db = db
        self.settings = settings
        self.running = False
        self.input_thread = None
        self.callbacks = {}
        
        # Initialize command processor and formatter
        self.command_processor = CommandProcessor(db, settings)
        self.formatter = TerminalFormatter(settings)
        
        # Command mapping
        self.commands = {
            'insulin': self._handle_insulin_command,
            'i': self._handle_insulin_command,
            'carbs': self._handle_carbs_command,
            'c': self._handle_carbs_command,
            'iob': self._handle_iob_override_command,
            'setiob': self._handle_iob_override_command,
            'status': self._handle_status_command,
            's': self._handle_status_command,
            'help': self._handle_help_command,
            'h': self._handle_help_command,
            'history': self._handle_history_command,
            'reading': self._handle_reading_command,
            'next': self._handle_next_reading_command,
            'n': self._handle_next_reading_command,
            'quit': self._handle_quit_command,
            'q': self._handle_quit_command
        }
    
    def start(self):
        """Start the input handler in a separate thread"""
        if self.running:
            return
        
        self.running = True
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.input_thread.start()
        logger.info("User input handler started")
        
        # Show initial help
        self._show_quick_help()
    
    def stop(self):
        """Stop the input handler"""
        self.running = False
        if self.input_thread and self.input_thread.is_alive():
            self.input_thread.join(timeout=1.0)
        logger.info("User input handler stopped")
    
    def register_callback(self, event: str, callback: Callable):
        """Register callback for events (e.g., 'insulin_logged', 'carbs_logged')"""
        self.callbacks[event] = callback
        # Also register with command processor
        self.command_processor.register_callback(event, callback)
    
    def _input_loop(self):
        """Main input loop running in separate thread"""
        while self.running:
            try:
                # Use input() with prompt
                command_line = input("\nEnter command (h for help): ").strip()
                
                if not command_line:
                    continue
                
                self._process_command(command_line)
                
            except (EOFError, KeyboardInterrupt):
                # Handle Ctrl+C or Ctrl+D gracefully
                break
            except Exception as e:
                logger.error(f"Error in input loop: {e}")
                print(f"Error processing command: {e}")
    
    def _process_command(self, command_line: str):
        """Process a command line"""
        parts = command_line.split()
        if not parts:
            return
        
        command = parts[0].lower()
        args = parts[1:]
        
        if command in self.commands:
            try:
                self.commands[command](args)
            except Exception as e:
                print(f"Error executing command: {e}")
        else:
            print(f"Unknown command: {command}. Type 'h' or 'help' for available commands.")
    
    def _handle_insulin_command(self, args):
        """Handle insulin logging command"""
        if not args:
            print("Log insulin dose")
            print("Usage: insulin <units> [type] [notes]")
            print("       i <units> [type] [notes]")
            print("Example: insulin 2.5 rapid 'correction dose'")
            print("Types: rapid (default), long, intermediate")
            return
        
        try:
            units = float(args[0])
            insulin_type = args[1] if len(args) > 1 else 'rapid'
            notes = ' '.join(args[2:]) if len(args) > 2 else None
            
            result = self.command_processor.execute_insulin(units, insulin_type, notes)
            print(self.formatter.format_insulin_result(result))
            
        except ValueError:
            print("Invalid units. Please enter a number (e.g., 2.5)")
        except Exception as e:
            print(f"Error logging insulin: {e}")
    
    def _handle_carbs_command(self, args):
        """Handle carbohydrate logging command"""
        if not args:
            print("Log carbohydrate intake")
            print("Usage: carbs <grams> [type] [notes]")
            print("       c <grams> [type] [notes]")
            print("Example: carbs 45 fast 'orange juice'")
            print("Types: fast, slow, mixed (default)")
            return
        
        try:
            grams = float(args[0])
            carb_type = args[1] if len(args) > 1 else 'mixed'
            notes = ' '.join(args[2:]) if len(args) > 2 else None
            
            result = self.command_processor.execute_carbs(grams, carb_type, notes)
            print(self.formatter.format_carbs_result(result))
                
        except ValueError:
            print("Invalid grams. Please enter a number (e.g., 30)")
        except Exception as e:
            print(f"Error logging carbs: {e}")
    
    def _handle_iob_override_command(self, args):
        """Handle IOB override command (for Omnipod/pump readings)"""
        if not args:
            print("Set current IOB from pump/Omnipod")
            print("Usage: iob <units> [source] [notes]")
            print("       setiob <units> [source] [notes]")
            print("Example: iob 0.2 omnipod")
            print("Sources: omnipod, pump, manual (default)")
            return
        
        try:
            iob_value = float(args[0])
            source = args[1] if len(args) > 1 else 'manual'
            notes = ' '.join(args[2:]) if len(args) > 2 else None
            
            result = self.command_processor.execute_iob_override(iob_value, source, notes)
            print(self.formatter.format_iob_override_result(result))
            
        except ValueError:
            print("Invalid IOB value. Please enter a number (e.g., 0.2)")
        except Exception as e:
            print(f"Error setting IOB override: {e}")
    
    def _handle_status_command(self, args):
        """Handle status command to show current IOB/COB"""
        try:
            result = self.command_processor.execute_status()
            print(self.formatter.format_status_result(result))
        except Exception as e:
            print(f"Error getting status: {e}")
    
    def _handle_history_command(self, args):
        """Handle history command to show recent entries"""
        try:
            hours = 6
            if args:
                try:
                    hours = int(args[0])
                except ValueError:
                    hours = 6
            
            result = self.command_processor.execute_history(hours)
            print(self.formatter.format_history_result(result))
                        
        except Exception as e:
            print(f"Error getting history: {e}")
    
    def _handle_next_reading_command(self, args):
        """Handle next reading command to show time until next sensor value"""
        try:
            result = self.command_processor.execute_next_reading()
            if result.success:
                print(self.formatter.format_next_reading_result(result))
            else:
                print(result.error)
                print("This feature requires the sensor client to be running")
                
        except Exception as e:
            print(f"Error getting next reading time: {e}")
    
    def _handle_reading_command(self, args):
        """Handle reading command to show latest sensor reading and recommendations"""
        try:
            result = self.command_processor.execute_reading()
            print(self.formatter.format_reading_result(result))
        except Exception as e:
            print(f"Error getting latest reading: {e}")
    
    def _handle_help_command(self, args):
        """Handle help command"""
        print(self.formatter.format_help())
    
    def _show_quick_help(self):
        """Show quick help message"""
        print("\nInteractive Terminal Ready!")
        print("   Type 'i 2.5' to log insulin")
        print("   Type 'c 30' to log carbs")
        print("   Type 'reading' for latest glucose")
        print("   Type 's' for status")
        print("   Type 'h' for full help")
    
    def _handle_quit_command(self, args):
        """Handle quit command"""
        print("Exiting glucose monitor...")
        self.running = False
        # Signal main application to quit
        if 'quit_requested' in self.callbacks:
            self.callbacks['quit_requested']()
        else:
            # Fallback - raise KeyboardInterrupt
            import os
            os.kill(os.getpid(), 2)  # Send SIGINT