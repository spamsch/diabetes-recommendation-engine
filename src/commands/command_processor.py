import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of executing a command"""
    success: bool
    data: Dict[str, Any]
    message: str = ""
    error: Optional[str] = None


class CommandProcessor:
    """Centralized command processor handling all business logic"""
    
    def __init__(self, db, settings):
        self.db = db
        self.settings = settings
        self.callbacks = {}
    
    def register_callback(self, event: str, callback: Callable):
        """Register callback for events"""
        self.callbacks[event] = callback
    
    def execute_insulin(self, units: float, insulin_type: str = 'rapid', 
                       notes: Optional[str] = None) -> CommandResult:
        """Execute insulin logging command"""
        try:
            # Validate insulin type
            valid_types = ['rapid', 'long_acting', 'long', 'intermediate']
            if insulin_type.lower() not in valid_types:
                insulin_type = 'rapid'
            elif insulin_type.lower() == 'long':
                insulin_type = 'long_acting'
            
            # Set duration based on type
            if insulin_type == 'rapid':
                duration = self.settings.insulin_duration_rapid
            elif insulin_type == 'long_acting':
                duration = self.settings.insulin_duration_long
            else:
                duration = 240  # 4 hours for intermediate
            
            # Import and create entry
            from ..database import InsulinEntry
            entry = InsulinEntry(
                timestamp=datetime.now(),
                units=units,
                insulin_type=insulin_type,
                duration_minutes=duration,
                notes=notes
            )
            
            entry_id = self.db.insert_insulin_entry(entry)
            
            # Trigger callback
            if 'insulin_logged' in self.callbacks:
                self.callbacks['insulin_logged'](entry)
            
            return CommandResult(
                success=True,
                data={
                    'entry_id': entry_id,
                    'units': units,
                    'insulin_type': insulin_type,
                    'duration': duration,
                    'notes': notes,
                    'timestamp': entry.timestamp
                },
                message=f"Logged {units} units of {insulin_type} insulin"
            )
            
        except ValueError as e:
            return CommandResult(
                success=False,
                data={},
                error=f"Invalid units: {e}"
            )
        except Exception as e:
            logger.error(f"Error logging insulin: {e}")
            return CommandResult(
                success=False,
                data={},
                error=f"Error logging insulin: {e}"
            )
    
    def execute_carbs(self, grams: float, carb_type: str = 'mixed', 
                     notes: Optional[str] = None) -> CommandResult:
        """Execute carbohydrate logging command"""
        try:
            # Validate carb type
            valid_types = ['fast', 'slow', 'mixed']
            if carb_type.lower() not in valid_types:
                carb_type = 'mixed'
            
            # Set absorption time based on type
            if carb_type == 'fast':
                absorption_time = self.settings.carb_absorption_fast
            elif carb_type == 'slow':
                absorption_time = self.settings.carb_absorption_slow
            else:  # mixed
                absorption_time = 120  # 2 hours default
            
            # Import and create entry
            from ..database import CarbEntry
            entry = CarbEntry(
                timestamp=datetime.now(),
                grams=grams,
                carb_type=carb_type,
                absorption_minutes=absorption_time,
                notes=notes
            )
            
            entry_id = self.db.insert_carb_entry(entry)
            
            # Trigger callback
            if 'carbs_logged' in self.callbacks:
                self.callbacks['carbs_logged'](entry)
            
            return CommandResult(
                success=True,
                data={
                    'entry_id': entry_id,
                    'grams': grams,
                    'carb_type': carb_type,
                    'absorption_time': absorption_time,
                    'notes': notes,
                    'timestamp': entry.timestamp
                },
                message=f"Logged {grams}g of {carb_type} carbs"
            )
            
        except ValueError as e:
            return CommandResult(
                success=False,
                data={},
                error=f"Invalid grams: {e}"
            )
        except Exception as e:
            logger.error(f"Error logging carbs: {e}")
            return CommandResult(
                success=False,
                data={},
                error=f"Error logging carbs: {e}"
            )
    
    def execute_iob_override(self, iob_value: float, source: str = 'manual', 
                           notes: Optional[str] = None) -> CommandResult:
        """Execute IOB override command"""
        try:
            # Validate IOB value
            if iob_value < 0:
                return CommandResult(
                    success=False,
                    data={},
                    error="IOB cannot be negative"
                )
            
            if iob_value > 10:
                return CommandResult(
                    success=False,
                    data={},
                    error="IOB seems too high (>10u). Please check value."
                )
            
            # Import and create override
            from ..database import IOBOverride
            override = IOBOverride(
                timestamp=datetime.now(),
                iob_value=iob_value,
                source=source.lower(),
                notes=notes
            )
            
            override_id = self.db.insert_iob_override(override)
            
            # Trigger callback and get enhanced status if available
            enhanced_status = None
            if 'iob_override_set' in self.callbacks:
                enhanced_status = self.callbacks['iob_override_set'](override)
            
            # Prepare base data
            base_data = {
                'override_id': override_id,
                'iob_value': iob_value,
                'source': source,
                'notes': notes,
                'timestamp': override.timestamp
            }
            
            # If we got enhanced status from callback, include it
            if enhanced_status and enhanced_status.get('success'):
                base_data['current_status'] = enhanced_status['data']
                message = f"IOB set to {iob_value:.1f}u (from {source}). {enhanced_status['message']}"
            else:
                message = f"Set IOB to {iob_value:.1f} units (from {source})"
            
            return CommandResult(
                success=True,
                data=base_data,
                message=message
            )
            
        except ValueError as e:
            return CommandResult(
                success=False,
                data={},
                error=f"Invalid IOB value: {e}"
            )
        except Exception as e:
            logger.error(f"Error setting IOB override: {e}")
            return CommandResult(
                success=False,
                data={},
                error=f"Error setting IOB override: {e}"
            )
    
    def execute_status(self) -> CommandResult:
        """Execute status command to show current IOB/COB"""
        try:
            current_time = datetime.now()
            
            # Get active entries
            active_insulin = self.db.get_active_insulin(current_time)
            active_carbs = self.db.get_active_carbs(current_time)
            
            # Calculate totals
            total_iob = sum(entry.units for entry in active_insulin) if active_insulin else 0
            total_cob = sum(entry.grams for entry in active_carbs) if active_carbs else 0
            
            return CommandResult(
                success=True,
                data={
                    'current_time': current_time,
                    'active_insulin': [
                        {
                            'units': entry.units,
                            'insulin_type': entry.insulin_type,
                            'minutes_ago': int((current_time - entry.timestamp).total_seconds() / 60),
                            'notes': entry.notes
                        }
                        for entry in (active_insulin or [])
                    ],
                    'active_carbs': [
                        {
                            'grams': entry.grams,
                            'carb_type': entry.carb_type or 'mixed',
                            'minutes_ago': int((current_time - entry.timestamp).total_seconds() / 60),
                            'notes': entry.notes
                        }
                        for entry in (active_carbs or [])
                    ],
                    'total_iob': total_iob,
                    'total_cob': total_cob
                },
                message="Current status retrieved"
            )
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return CommandResult(
                success=False,
                data={},
                error=f"Error getting status: {e}"
            )
    
    def execute_history(self, hours: int = 6) -> CommandResult:
        """Execute history command to show recent entries"""
        try:
            # Get recent entries
            recent_insulin = self.db.get_recent_insulin_entries(hours)
            recent_carbs = self.db.get_recent_carb_entries(hours)
            
            # Combine and sort by time
            all_entries = []
            for entry in recent_insulin:
                all_entries.append({
                    'type': 'insulin',
                    'timestamp': entry.timestamp,
                    'units': entry.units,
                    'insulin_type': entry.insulin_type,
                    'notes': entry.notes
                })
            for entry in recent_carbs:
                all_entries.append({
                    'type': 'carbs',
                    'timestamp': entry.timestamp,
                    'grams': entry.grams,
                    'carb_type': entry.carb_type or 'mixed',
                    'notes': entry.notes
                })
            
            all_entries.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return CommandResult(
                success=True,
                data={
                    'hours': hours,
                    'entries': all_entries[:10],  # Limit to 10 entries
                    'total_entries': len(all_entries)
                },
                message=f"Retrieved {len(all_entries)} entries from last {hours} hours"
            )
            
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return CommandResult(
                success=False,
                data={},
                error=f"Error getting history: {e}"
            )
    
    def execute_reading(self) -> CommandResult:
        """Execute reading command - show latest sensor reading and recommendations"""
        try:
            # Get the most recent glucose reading
            recent_readings = self.db.get_latest_readings(1)
            if not recent_readings:
                return CommandResult(
                    success=False,
                    data={},
                    error="No glucose readings found in database"
                )
            
            latest_reading = recent_readings[0]
            current_time = datetime.now()
            
            # Calculate how long ago the reading was taken
            time_diff = current_time - latest_reading.timestamp
            minutes_ago = int(time_diff.total_seconds() / 60)
            
            result_data = {
                'reading': {
                    'value': latest_reading.value,
                    'timestamp': latest_reading.timestamp,
                    'minutes_ago': minutes_ago
                }
            }
            
            # Get recent readings for trend analysis
            recent_readings = self.db.get_latest_readings(self.settings.analysis_window_size)
            
            if len(recent_readings) >= 2:
                # Import analyzers
                from ..analysis import TrendAnalyzer, GlucosePredictor, IOBCalculator
                from ..analysis.recommendations import RecommendationEngine
                
                trend_analyzer = TrendAnalyzer(self.settings)
                
                # Analyze trend
                trend_analysis = trend_analyzer.analyze_trend(recent_readings)
                result_data['trend'] = trend_analysis
                
                # Get current IOB/COB data
                active_insulin = self.db.get_active_insulin(current_time)
                active_carbs = self.db.get_active_carbs(current_time)
                iob_override_entry = self.db.get_latest_iob_override(current_time)
                iob_override_value = iob_override_entry.iob_value if iob_override_entry else None
                
                iob_cob_data = None
                if active_insulin or active_carbs or iob_override_value is not None:
                    iob_calculator = IOBCalculator(self.settings)
                    iob_cob_data = iob_calculator.get_iob_cob_summary(
                        current_time, active_insulin, active_carbs, latest_reading.value, iob_override_value
                    )
                    result_data['iob_cob'] = iob_cob_data
                    result_data['iob_override_entry'] = iob_override_entry
                
                # Generate predictions and recommendations
                predictor = GlucosePredictor(self.settings)
                recommendation_engine = RecommendationEngine(self.settings)
                
                # Make prediction
                prediction = predictor.predict_future_value(recent_readings)
                if prediction.get('predicted_value'):
                    result_data['prediction'] = prediction
                
                # Get recommendations
                recommendations = recommendation_engine.get_recommendations(
                    recent_readings, trend_analysis, prediction, iob_cob_data
                )
                
                if recommendations:
                    result_data['recommendations'] = recommendations[:3]  # Top 3
            
            return CommandResult(
                success=True,
                data=result_data,
                message="Latest reading and analysis retrieved"
            )
            
        except Exception as e:
            logger.error(f"Error getting latest reading: {e}")
            return CommandResult(
                success=False,
                data={},
                error=f"Error getting latest reading: {e}"
            )
    
    def execute_next_reading(self) -> CommandResult:
        """Execute next reading command"""
        try:
            # Get callback to sensor client if available
            if 'get_next_reading_time' in self.callbacks:
                next_reading_info = self.callbacks['get_next_reading_time']()
                
                if next_reading_info:
                    return CommandResult(
                        success=True,
                        data=next_reading_info,
                        message="Next reading time retrieved"
                    )
                else:
                    return CommandResult(
                        success=False,
                        data={},
                        error="Next reading time: Unknown"
                    )
            else:
                return CommandResult(
                    success=False,
                    data={},
                    error="Next reading information not available"
                )
                
        except Exception as e:
            logger.error(f"Error getting next reading time: {e}")
            return CommandResult(
                success=False,
                data={},
                error=f"Error getting next reading time: {e}"
            )
    
    
    def execute_debug(self, telegram_config: Dict, message_info: Dict) -> CommandResult:
        """Execute debug command - show diagnostic information"""
        try:
            debug_data = {
                'telegram_config': telegram_config,
                'message_info': message_info,
                'command_count': len(self.callbacks)
            }
            
            return CommandResult(
                success=True,
                data=debug_data,
                message="Debug information retrieved"
            )
            
        except Exception as e:
            logger.error(f"Error getting debug info: {e}")
            return CommandResult(
                success=False,
                data={},
                error=f"Error getting debug info: {e}"
            )
    
    def execute_test(self) -> CommandResult:
        """Execute test command - test various functionality"""
        try:
            test_results = {}
            current_time = datetime.now()
            
            # Test database connection
            try:
                active_insulin = self.db.get_active_insulin(current_time)
                active_carbs = self.db.get_active_carbs(current_time)
                test_results['database'] = {
                    'status': 'connected',
                    'active_insulin_count': len(active_insulin),
                    'active_carbs_count': len(active_carbs)
                }
            except Exception as e:
                test_results['database'] = {
                    'status': 'error',
                    'error': str(e)[:50]
                }
            
            # Test settings
            try:
                test_results['settings'] = {
                    'status': 'loaded',
                    'poll_interval': self.settings.poll_interval_minutes,
                    'prediction_window': self.settings.prediction_minutes_ahead
                }
            except Exception as e:
                test_results['settings'] = {
                    'status': 'error',
                    'error': str(e)[:50]
                }
            
            # Test message processing
            test_results['message_processing'] = {
                'status': 'working'
            }
            
            return CommandResult(
                success=True,
                data=test_results,
                message="System tests completed"
            )
            
        except Exception as e:
            logger.error(f"Error running tests: {e}")
            return CommandResult(
                success=False,
                data={},
                error=f"Error running tests: {e}"
            )
    
    def execute_note(self, note_text: str, note_type: str = 'observation', 
                     glucose_value: Optional[float] = None) -> CommandResult:
        """Execute note command to add a glucose observation note"""
        try:
            # Validate note text
            if not note_text or len(note_text.strip()) == 0:
                return CommandResult(
                    success=False,
                    data={},
                    error="Note text cannot be empty"
                )
            
            if len(note_text) > 500:
                return CommandResult(
                    success=False,
                    data={},
                    error="Note text too long (max 500 characters)"
                )
            
            # Validate note type
            valid_types = ['observation', 'trend', 'recommendation-note']
            if note_type.lower() not in valid_types:
                note_type = 'observation'
            
            # Get current glucose if not provided
            if glucose_value is None:
                recent_readings = self.db.get_latest_readings(1)
                if recent_readings:
                    glucose_value = recent_readings[0].value
            
            # Get context data for the note
            context_data = None
            current_time = datetime.now()
            
            # Get IOB/COB for context
            active_insulin = self.db.get_active_insulin(current_time)
            active_carbs = self.db.get_active_carbs(current_time)
            iob_override_entry = self.db.get_latest_iob_override(current_time)
            
            if active_insulin or active_carbs or iob_override_entry:
                from ..analysis import IOBCalculator
                iob_calculator = IOBCalculator(self.settings)
                
                iob_override_value = iob_override_entry.iob_value if iob_override_entry else None
                iob_cob_data = iob_calculator.get_iob_cob_summary(
                    current_time, active_insulin, active_carbs, glucose_value or 0, iob_override_value
                )
                
                context_data = str({
                    'iob': iob_cob_data.get('iob', {}).get('total_iob', 0),
                    'cob': iob_cob_data.get('cob', {}).get('total_cob', 0),
                    'timestamp': current_time.isoformat()
                })
            
            # Import and create note
            from ..database import GlucoseNote
            note = GlucoseNote(
                timestamp=current_time,
                note_text=note_text.strip(),
                note_type=note_type.lower(),
                glucose_value=glucose_value,
                context_data=context_data
            )
            
            note_id = self.db.insert_glucose_note(note)
            
            # Trigger callback if available
            if 'note_added' in self.callbacks:
                self.callbacks['note_added'](note)
            
            # Create response message
            message = f"Added {note_type} note: '{note_text[:50]}{'...' if len(note_text) > 50 else ''}'"
            if glucose_value:
                message += f" (glucose: {glucose_value:.0f} mg/dL)"
            
            return CommandResult(
                success=True,
                data={
                    'note_id': note_id,
                    'note_text': note_text,
                    'note_type': note_type,
                    'glucose_value': glucose_value,
                    'timestamp': current_time,
                    'context_data': context_data
                },
                message=message
            )
            
        except Exception as e:
            logger.error(f"Error adding note: {e}")
            return CommandResult(
                success=False,
                data={},
                error=f"Error adding note: {e}"
            )
    
    def execute_notes(self, hours: int = 24, note_type: Optional[str] = None) -> CommandResult:
        """Execute notes command to show recent notes"""
        try:
            # Get recent notes
            recent_notes = self.db.get_recent_notes(hours, note_type)
            
            # Format notes for display
            formatted_notes = []
            for note in recent_notes[:10]:  # Limit to 10 most recent
                minutes_ago = int((datetime.now() - note.timestamp).total_seconds() / 60)
                formatted_note = {
                    'note_text': note.note_text,
                    'note_type': note.note_type,
                    'timestamp': note.timestamp,
                    'minutes_ago': minutes_ago,
                    'glucose_value': note.glucose_value
                }
                formatted_notes.append(formatted_note)
            
            filter_text = f" ({note_type})" if note_type else ""
            message = f"Retrieved {len(formatted_notes)} notes{filter_text} from last {hours} hours"
            
            return CommandResult(
                success=True,
                data={
                    'hours': hours,
                    'note_type': note_type,
                    'notes': formatted_notes,
                    'total_notes': len(recent_notes)
                },
                message=message
            )
            
        except Exception as e:
            logger.error(f"Error getting notes: {e}")
            return CommandResult(
                success=False,
                data={},
                error=f"Error getting notes: {e}"
            )