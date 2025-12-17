# -*- coding: utf-8 -*-
"""
PyNVMe Test Configuration
Shared fixtures for NVMe 2.0 queue validation test suite
"""

import pytest
import logging
import nvme as d

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Default PCIe address - modify as needed for your test environment
DEFAULT_PCIE_ADDR = '01:00.0'


@pytest.fixture(scope="session")
def pcie():
    """
    PCIe device fixture
    
    Provides access to the PCIe interface of the NVMe device.
    Scope: session - created once per test session
    
    Returns:
        Pcie: PCIe object for NVMe device access
    """
    pcie_dev = d.Pcie(DEFAULT_PCIE_ADDR)
    yield pcie_dev
    pcie_dev.close()


@pytest.fixture(scope="function")
def nvme0(pcie):
    """
    NVMe Controller fixture
    
    Creates and initializes NVMe controller with default initialization.
    Scope: function - new controller instance for each test
    
    NVMe 2.0 Reference: Controller initialization per spec §7.6.1
    
    Args:
        pcie: PCIe device fixture
        
    Returns:
        Controller: Initialized NVMe controller object
    """
    # Create controller with default initialization (nvme_init_func=None)
    ctrl = d.Controller(pcie)
    
    # Log controller capabilities
    cap = ctrl[0]  # Read CAP register (offset 0x00)
    mqes = cap & 0xFFFF  # Maximum Queue Entries Supported
    logging.info(f"Controller CAP: 0x{cap:016x}")
    logging.info(f"Maximum Queue Entries Supported (MQES): {mqes}")
    
    # Log controller status
    csts = ctrl[0x1c]  # Read CSTS register (offset 0x1C)
    logging.info(f"Controller Status (CSTS): 0x{csts:08x}")
    logging.info(f"Controller Ready (RDY): {(csts & 0x1)}")
    
    yield ctrl
    
    # Cleanup: no explicit close needed for controller


@pytest.fixture(scope="function")
def nvme0n1(nvme0):
    """
    NVMe Namespace fixture
    
    Creates namespace object for I/O operations on namespace 1.
    Scope: function - new namespace instance for each test
    
    NVMe 2.0 Reference: Namespace management per spec §5.15
    
    Args:
        nvme0: NVMe controller fixture
        
    Returns:
        Namespace: Namespace object for I/O operations
    """
    ns = d.Namespace(nvme0, nsid=1)
    
    # Log namespace information
    nsze = ns.id_data(7, 0)  # Namespace Size (NSZE) - bytes 0-7
    ncap = ns.id_data(15, 8)  # Namespace Capacity (NCAP) - bytes 8-15
    logging.info(f"Namespace 1 Size (NSZE): {nsze} blocks")
    logging.info(f"Namespace 1 Capacity (NCAP): {ncap} blocks")
    
    yield ns
    
    ns.close()


@pytest.fixture(scope="function")
def qpair(nvme0):
    """
    I/O Queue Pair fixture
    
    Creates a basic I/O Submission Queue and Completion Queue pair.
    Scope: function - new queue pair for each test
    
    NVMe 2.0 Reference: Queue creation per spec §5.3, §5.4
    
    Args:
        nvme0: NVMe controller fixture
        
    Returns:
        Qpair: I/O queue pair object (SQ + CQ)
    """
    # Create queue pair with depth=8, interrupt enabled
    q = d.Qpair(nvme0, depth=8)
    
    logging.info(f"Created I/O Queue Pair with SQID: {q.sqid}")
    
    yield q
    
    # Cleanup: delete queue pair
    # NVMe 2.0 spec requires deleting SQ before CQ (handled by Qpair.delete())
    q.delete()


@pytest.fixture(scope="function")
def buf():
    """
    DMA Buffer fixture
    
    Creates a 4KB DMA-capable buffer for data transfers.
    Scope: function - new buffer for each test
    
    NVMe 2.0 Reference: Physical Region Pages (PRP) per spec §4.1.1
    
    Returns:
        Buffer: 4KB DMA buffer
    """
    buffer = d.Buffer(4096)  # Default 4KB page size
    
    logging.debug(f"Created DMA buffer at physical address: 0x{buffer.phys_addr:x}")
    
    yield buffer
    
    # Buffer cleanup is automatic


@pytest.fixture(scope="function")
def large_buf():
    """
    Large DMA Buffer fixture
    
    Creates a 128KB DMA-capable buffer for large data transfers.
    Scope: function - new buffer for each test
    
    Useful for testing PRP lists and large transfer scenarios.
    
    Returns:
        Buffer: 128KB DMA buffer
    """
    buffer = d.Buffer(128 * 1024)  # 128KB
    
    logging.debug(f"Created large DMA buffer at physical address: 0x{buffer.phys_addr:x}")
    
    yield buffer


@pytest.fixture(scope="function")
def nvme0_no_init(pcie):
    """
    NVMe Controller fixture without automatic initialization
    
    Creates controller without running standard initialization process.
    Useful for testing low-level initialization sequences.
    Scope: function - new controller instance for each test
    
    Args:
        pcie: PCIe device fixture
        
    Returns:
        Controller: Uninitialized NVMe controller object
    """
    # nvme_init_func=True means skip initialization
    ctrl = d.Controller(pcie, nvme_init_func=True)
    
    yield ctrl


# Helper function to get maximum supported queue count
def get_max_queue_count(nvme0):
    """
    Query maximum number of I/O queues supported by controller
    
    Uses Get Features command with Feature ID 07h (Number of Queues).
    NVMe 2.0 Reference: Feature Identifier 07h per spec §5.27.1.7
    
    Args:
        nvme0: NVMe controller object
        
    Returns:
        int: Maximum number of I/O queues supported (minimum of SQ and CQ limits)
    """
    result = {'num_queues': 0}
    
    def get_features_cb(cdw0, status1):
        """Callback to capture CDW0 from Get Features completion"""
        # CDW0 contains: bits[15:0] = NCQR, bits[31:16] = NSQR
        ncqr = (cdw0 & 0xFFFF) + 1  # Number of CQs requested (0-based)
        nsqr = ((cdw0 >> 16) & 0xFFFF) + 1  # Number of SQs requested (0-based)
        result['num_queues'] = min(ncqr, nsqr)
    
    # Get Features: Feature ID 07h
    nvme0.getfeatures(0x07, cb=get_features_cb).waitdone()
    
    return result['num_queues']


# Pytest configuration hooks
def pytest_configure(config):
    """
    Pytest configuration hook
    
    Registers custom markers for test categorization.
    """
    config.addinivalue_line(
        "markers", "positive: positive test cases that should succeed"
    )
    config.addinivalue_line(
        "markers", "negative: negative test cases that should fail with expected errors"
    )
    config.addinivalue_line(
        "markers", "edge: edge case test scenarios"
    )
    config.addinivalue_line(
        "markers", "admin_queue: tests for admin queue validation"
    )
    config.addinivalue_line(
        "markers", "io_queue: tests for I/O queue operations"
    )
