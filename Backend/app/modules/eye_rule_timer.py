"""20-20-20 eye rule timer module"""

import time

class EyeRuleTimer:
    """Implements the 20-20-20 eye health rule timer"""
    
    def __init__(self):
        # 20-20-20 rule: Every 20 minutes, look at something 20 feet away for 20 seconds
        self.interval = 20 * 60  # 20 minutes in seconds
        self.break_duration = 20  # 20 seconds
        self.start_time = None
        self.last_alert_time = None
        self.alert_active = False
    
    def reset(self):
        """Reset timer"""
        self.start_time = time.time()
        self.last_alert_time = None
        self.alert_active = False
    
    def get_status(self):
        """Get current timer status"""
        if self.start_time is None:
            self.start_time = time.time()
        
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Calculate time until next break
        if self.last_alert_time:
            time_since_alert = current_time - self.last_alert_time
            if time_since_alert < self.break_duration:
                # Currently in break period
                return {
                    'alert': True,
                    'next_break': 0,
                    'message': f'Take a break! Look away for {self.break_duration - int(time_since_alert)} seconds'
                }
            else:
                # Break completed, reset for next cycle
                self.start_time = current_time
                self.last_alert_time = None
                self.alert_active = False
                elapsed = 0
        
        # Check if it's time for a break
        if elapsed >= self.interval:
            if not self.alert_active:
                self.last_alert_time = current_time
                self.alert_active = True
            
            return {
                'alert': True,
                'next_break': 0,
                'message': f'20-20-20 Rule: Look at something 20 feet away for {self.break_duration} seconds!'
            }
        
        # Normal operation
        time_remaining = self.interval - elapsed
        minutes_remaining = int(time_remaining / 60)
        seconds_remaining = int(time_remaining % 60)
        
        return {
            'alert': False,
            'next_break': time_remaining,
            'message': f'Next break in {minutes_remaining}m {seconds_remaining}s'
        }
    
    def acknowledge_break(self):
        """User acknowledges the break (for future interactive feature)"""
        self.start_time = time.time()
        self.last_alert_time = None
        self.alert_active = False
