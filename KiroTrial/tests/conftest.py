"""
PyNVMe Test Configuration and Fixtures

Provides common test fixtures and configuration for NVMe 2.0 queue testing.
"""

import pytest
import logging
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

try:
    import pynvme as d
except ImportError:
    pytest.skip("PyNVMe library not available", allow_module_level=True)


@dataclass
class NVMeControllerInfo:
    """Information about the NVMe controller under test"""
    model: str
    serial: str
    firmware: str
    max_queues: int
    max_queue_entries: int
    nvme_version: str
    
    
class NVMeTestFixture:
    """
    Base test fixture for NVMe controller initialization and cleanup.
    
    Provides common functionality for:
    - Controller initialization and cleanup
    - Test environment validation  
    - Common assertion helpers
    - Error handling utilities
    """
    
    def __init__(self):
        self.controller: Optional[d.Controller] = None
        self.namespace: Optional[d.Namespace] = None
        self.controller_info: Optional[NVMeControllerInfo] = None
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def setup_controller(self, device_path: str = "/dev/nvme0") -> None:
        """
        Initialize NVMe controller for testing.
        
        Args:
            device_path: Path to NVMe device (default: /dev/nvme0)
            
        Raises:
            RuntimeError: If controller initialization fails
        """
        try:
            self.logger.info(f"Initializing NVMe controller: {device_path}")
            self.controller = d.Controller(device_path)
            
            # Get first namespace for I/O operations
            self.namespace = d.Namespace(self.controller, 1)
            
            # Gather controller information
            self._gather_controller_info()
            
            self.logger.info(f"Controller initialized: {self.controller_info.model}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize controller: {e}")
            raise RuntimeError(f"Controller initialization failed: {e}")
    
    def teardown_controller(self) -> None:
        """Clean up controller resources"""
        try:
            if self.namespace:
                self.namespace.close()
                self.namespace = None
                
            if self.controller:
                self.controller.close()
                self.controller = None
                
            self.logger.info("Controller cleanup completed")
            
        except Exception as e:
            self.logger.warning(f"Controller cleanup warning: {e}")
    
    def _gather_controller_info(self) -> None:
        """Gather controller capability information"""
        if not self.controller:
            raise RuntimeError("Controller not initialized")
            
        # Read controller identification data
        id_data = self.controller.id_data()
        
        self.controller_info = NVMeControllerInfo(
            model=id_data[63:24:-1].decode('utf-8').strip(),
            serial=id_data[23:4:-1].decode('utf-8').strip(), 
            firmware=id_data[71:64:-1].decode('utf-8').strip(),
            max_queues=self.controller.cap & 0xFFFF,  # CAP.MQES
            max_queue_entries=(self.controller.cap & 0xFFFF) + 1,
            nvme_version=f"{(self.controller.vs >> 16) & 0xFFFF}.{self.controller.vs & 0xFFFF}"
        )
    
    def assert_nvme_status(self, status: int, expected: int, message: str = "") -> None:
        """
        Assert NVMe completion status matches expected value.
        
        Args:
            status: Actual NVMe status code
            expected: Expected NVMe status code  
            message: Optional error message
        """
        if status != expected:
            error_msg = f"NVMe status mismatch: got 0x{status:04x}, expected 0x{expected:04x}"
            if message:
                error_msg = f"{message}: {error_msg}"
            raise AssertionError(error_msg)
    
    def wait_for_controller_ready(self, timeout: float = 30.0) -> None:
        """
        Wait for controller to become ready (CSTS.RDY = 1).
        
        Args:
            timeout: Maximum wait time in seconds
            
        Raises:
            TimeoutError: If controller doesn't become ready within timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.controller.csts & 0x1:  # CSTS.RDY bit
                return
            time.sleep(0.1)
            
        raise TimeoutError(f"Controller not ready after {timeout}s")


@pytest.fixture(scope="session")
def nvme_device_path():
    """NVMe device path for testing (can be overridden via pytest args)"""
    return "/dev/nvme0"


@pytest.fixture(scope="function") 
def nvme_fixture(nvme_device_path):
    """
    Per-test NVMe controller fixture.
    
    Provides initialized controller for each test with automatic cleanup.
    """
    fixture = NVMeTestFixture()
    
    try:
        fixture.setup_controller(nvme_device_path)
        yield fixture
    finally:
        fixture.teardown_controller()


@pytest.fixture(scope="session")
def nvme_session_fixture(nvme_device_path):
    """
    Session-wide NVMe controller fixture.
    
    Provides shared controller instance for tests that don't modify controller state.
    Use with caution - tests must not interfere with each other.
    """
    fixture = NVMeTestFixture()
    
    try:
        fixture.setup_controller(nvme_device_path)
        yield fixture
    finally:
        fixture.teardown_controller()


def pytest_configure(config):
    """Configure pytest with custom markers and settings"""
    config.addinivalue_line(
        "markers", "hardware: mark test as requiring real NVMe hardware"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add hardware marker to all tests"""
    hardware_marker = pytest.mark.hardware
    for item in items:
        item.add_marker(hardware_marker)