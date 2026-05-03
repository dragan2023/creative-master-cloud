"""专项检测器"""
from .duplicate_submit import DuplicateSubmitDetector
from .input_validation import InputValidationDetector
from .error_handling import ErrorHandlingDetector
from .performance_monitor import PerformanceMonitor
from .ux_flow import UXFlowDetector

__all__ = ['DuplicateSubmitDetector', 'InputValidationDetector', 
           'ErrorHandlingDetector', 'PerformanceMonitor', 'UXFlowDetector']
