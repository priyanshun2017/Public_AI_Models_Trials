"""
Data models for NVMe 2.0 queue testing framework.

Provides structured data classes for queue configuration, test commands,
completion validation, and test results.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum
import time


class MemoryType(Enum):
    """Memory allocation type for NVMe queues"""
    CONTIGUOUS = "contiguous"
    NON_CONTIGUOUS = "non_contiguous"


class TestStatus(Enum):
    """Test execution status"""
    PASS = "pass"
    FAIL = "fail" 
    SKIP = "skip"


class QueueType(Enum):
    """NVMe queue types"""
    ADMIN_SUBMISSION = "admin_sq"
    ADMIN_COMPLETION = "admin_cq"
    IO_SUBMISSION = "io_sq"
    IO_COMPLETION = "io_cq"


@dataclass
class QueueConfiguration:
    """
    Configuration parameters for NVMe queue creation.
    
    Encapsulates all parameters needed to create and validate NVMe queues
    according to NVMe 2.0 specification requirements.
    """
    queue_id: int
    queue_size: int
    memory_type: MemoryType = MemoryType.CONTIGUOUS
    interrupt_vector: Optional[int] = None
    polling_mode: bool = False
    queue_type: Optional[QueueType] = None
    
    def validate(self) -> bool:
        """
        Validates configuration against NVMe 2.0 constraints.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        # Queue ID validation (1-65535 for I/O queues, 0 reserved for admin)
        if self.queue_type in [QueueType.IO_SUBMISSION, QueueType.IO_COMPLETION]:
            if not (1 <= self.queue_id <= 65535):
                return False
        elif self.queue_type in [QueueType.ADMIN_SUBMISSION, QueueType.ADMIN_COMPLETION]:
            if self.queue_id != 0:
                return False
                
        # Queue size validation (must be power of 2, minimum 2 entries)
        if self.queue_size < 2 or (self.queue_size & (self.queue_size - 1)) != 0:
            return False
            
        # Interrupt vector validation
        if not self.polling_mode and self.interrupt_vector is None:
            return False
            
        return True
    
    def to_creation_params(self) -> Dict[str, Any]:
        """
        Converts configuration to PyNVMe queue creation parameters.
        
        Returns:
            Dictionary of parameters for PyNVMe queue creation
        """
        params = {
            'qid': self.queue_id,
            'qsize': self.queue_size,
            'pc': 1 if self.memory_type == MemoryType.CONTIGUOUS else 0
        }
        
        if not self.polling_mode and self.interrupt_vector is not None:
            params['iv'] = self.interrupt_vector
            
        return params


@dataclass  
class TestCommand:
    """
    Represents an NVMe command for testing purposes.
    
    Encapsulates command parameters and expected results for validation.
    """
    opcode: int
    command_id: int
    namespace_id: int = 1
    data_buffer: Optional[bytes] = None
    metadata_buffer: Optional[bytes] = None
    expected_status: int = 0  # Success by default
    lba_start: int = 0
    lba_count: int = 1
    
    def to_nvme_command(self) -> Dict[str, Any]:
        """
        Converts to PyNVMe command format.
        
        Returns:
            Dictionary representing NVMe command for PyNVMe
        """
        cmd = {
            'opcode': self.opcode,
            'cid': self.command_id,
            'nsid': self.namespace_id,
            'slba': self.lba_start,
            'nlb': self.lba_count - 1  # NVMe uses 0-based count
        }
        
        if self.data_buffer:
            cmd['data'] = self.data_buffer
            
        if self.metadata_buffer:
            cmd['metadata'] = self.metadata_buffer
            
        return cmd
    
    def is_read_command(self) -> bool:
        """Check if this is a read command (opcode 0x02)"""
        return self.opcode == 0x02
        
    def is_write_command(self) -> bool:
        """Check if this is a write command (opcode 0x01)"""
        return self.opcode == 0x01


@dataclass
class CompletionValidation:
    """
    Validation criteria for NVMe completion queue entries.
    
    Defines expected values for completion validation according to NVMe 2.0.
    """
    expected_cid: int
    expected_sqid: int
    expected_status: int = 0
    phase_tag_expected: bool = True
    validate_sqhd: bool = True
    expected_sqhd: Optional[int] = None
    
    def validate_completion(self, completion_data: bytes) -> 'ValidationResult':
        """
        Validates completion queue entry against expectations.
        
        Args:
            completion_data: Raw 16-byte completion queue entry
            
        Returns:
            ValidationResult with validation outcome and details
        """
        if len(completion_data) != 16:
            return ValidationResult(
                is_valid=False,
                error_message="Invalid completion entry size"
            )
            
        # Parse completion queue entry fields (NVMe 2.0 format)
        # Bytes 0-3: Command specific
        # Bytes 4-7: Reserved  
        # Bytes 8-9: SQ Head Pointer
        # Bytes 10-11: SQ Identifier
        # Bytes 12-13: Command Identifier
        # Bytes 14-15: Status Field and Phase Tag
        
        sqhd = int.from_bytes(completion_data[8:10], 'little')
        sqid = int.from_bytes(completion_data[10:12], 'little') 
        cid = int.from_bytes(completion_data[12:14], 'little')
        status_phase = int.from_bytes(completion_data[14:16], 'little')
        
        status = (status_phase >> 1) & 0x7FFF  # Bits 15:1
        phase_tag = status_phase & 0x1  # Bit 0
        
        errors = []
        
        # Validate Command Identifier
        if cid != self.expected_cid:
            errors.append(f"CID mismatch: got {cid}, expected {self.expected_cid}")
            
        # Validate Submission Queue Identifier  
        if sqid != self.expected_sqid:
            errors.append(f"SQID mismatch: got {sqid}, expected {self.expected_sqid}")
            
        # Validate Status Field
        if status != self.expected_status:
            errors.append(f"Status mismatch: got 0x{status:04x}, expected 0x{self.expected_status:04x}")
            
        # Validate Phase Tag
        phase_valid = bool(phase_tag) == self.phase_tag_expected
        if not phase_valid:
            errors.append(f"Phase tag mismatch: got {phase_tag}, expected {self.phase_tag_expected}")
            
        # Validate SQ Head Pointer if requested
        if self.validate_sqhd and self.expected_sqhd is not None:
            if sqhd != self.expected_sqhd:
                errors.append(f"SQHD mismatch: got {sqhd}, expected {self.expected_sqhd}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            error_message="; ".join(errors) if errors else None,
            completion_fields={
                'cid': cid,
                'sqid': sqid, 
                'sqhd': sqhd,
                'status': status,
                'phase_tag': bool(phase_tag)
            }
        )


@dataclass
class ValidationResult:
    """
    Result of a validation operation.
    
    Contains validation outcome and detailed information for debugging.
    """
    is_valid: bool
    error_message: Optional[str] = None
    completion_fields: Optional[Dict[str, Any]] = None
    additional_info: Optional[Dict[str, Any]] = None


@dataclass
class TestResult:
    """
    Comprehensive test execution result.
    
    Captures all relevant information about test execution for reporting and analysis.
    """
    test_name: str
    status: TestStatus
    execution_time: float
    error_details: Optional[str] = None
    nvme_status_codes: Optional[List[int]] = None
    hardware_info: Optional[Dict[str, Any]] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    def __post_init__(self):
        """Initialize timing fields if not provided"""
        if self.start_time is None:
            self.start_time = time.time()
        if self.end_time is None:
            self.end_time = self.start_time + self.execution_time
    
    def mark_completed(self, status: TestStatus, error_details: Optional[str] = None):
        """
        Mark test as completed with final status.
        
        Args:
            status: Final test status
            error_details: Optional error information
        """
        self.end_time = time.time()
        self.execution_time = self.end_time - (self.start_time or self.end_time)
        self.status = status
        if error_details:
            self.error_details = error_details
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert test result to dictionary for serialization"""
        return {
            'test_name': self.test_name,
            'status': self.status.value,
            'execution_time': self.execution_time,
            'error_details': self.error_details,
            'nvme_status_codes': self.nvme_status_codes,
            'hardware_info': self.hardware_info,
            'start_time': self.start_time,
            'end_time': self.end_time
        }