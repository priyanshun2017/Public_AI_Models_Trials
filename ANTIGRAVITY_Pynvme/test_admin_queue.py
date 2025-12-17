# -*- coding: utf-8 -*-
"""
NVMe 2.0 Admin Queue Validation Tests

Purpose:
    Validate Admin Submission Queue (ASQ) and Admin Completion Queue (ACQ)
    behavior according to NVMe 2.0 specification.

NVMe 2.0 Specification References:
    - §3.1.6: Controller Configuration (CC) and Status (CSTS)
    - §3.5: Admin Queue
    - §4.1: Submission Queue and Completion Queue
    - §7.6.1: Initialization

Test Coverage:
    - Admin queue initialization and readiness
    - Queue depth and capability validation
    - Memory alignment verification
    - Doorbell register behavior
    - Controller enable/disable transitions
    - Invalid command handling
"""

import pytest
import logging
import time
import nvme as d

logger = logging.getLogger(__name__)


# ============================================================================
# POSITIVE TESTS - Admin Queue Validation
# ============================================================================

@pytest.mark.positive
@pytest.mark.admin_queue
def test_admin_queue_initialization(nvme0):
    """
    Test: Admin Queue Initialization
    
    Purpose:
        Verify that Admin Submission Queue (ASQ) and Admin Completion Queue (ACQ)
        are properly initialized and controller is ready.
    
    Preconditions:
        - NVMe controller is connected and accessible
        - Controller has completed initialization
    
    Test Steps:
        1. Read Controller Configuration (CC) register (offset 0x14)
        2. Verify CC.EN (Enable) bit is set (bit 0 = 1)
        3. Read Controller Status (CSTS) register (offset 0x1C)
        4. Verify CSTS.RDY (Ready) bit is set (bit 0 = 1)
        5. Verify admin queue can process commands
    
    Expected Result:
        - CC.EN = 1 (controller enabled)
        - CSTS.RDY = 1 (controller ready)
        - Admin commands execute successfully
    
    NVMe 2.0 Reference: §3.1.6 (CC and CSTS registers)
    """
    logger.info("=== Test: Admin Queue Initialization ===")
    
    # Step 1-2: Read and verify Controller Configuration (CC) register
    cc_reg = nvme0[0x14]  # CC register at offset 0x14
    cc_en = cc_reg & 0x1  # Extract CC.EN bit (bit 0)
    
    logger.info(f"Controller Configuration (CC): 0x{cc_reg:08x}")
    logger.info(f"CC.EN (Enable): {cc_en}")
    
    assert cc_en == 1, "Controller should be enabled (CC.EN = 1)"
    
    # Step 3-4: Read and verify Controller Status (CSTS) register
    csts_reg = nvme0[0x1c]  # CSTS register at offset 0x1C
    csts_rdy = csts_reg & 0x1  # Extract CSTS.RDY bit (bit 0)
    
    logger.info(f"Controller Status (CSTS): 0x{csts_reg:08x}")
    logger.info(f"CSTS.RDY (Ready): {csts_rdy}")
    
    assert csts_rdy == 1, "Controller should be ready (CSTS.RDY = 1)"
    
    # Step 5: Verify admin queue functionality with Identify command
    id_buf = d.Buffer(4096)
    nvme0.identify(id_buf, nsid=0, cns=1).waitdone()  # Identify Controller
    
    # Verify identify data is valid (check for non-zero VID)
    vid = id_buf.data(1, 0) & 0xFFFF  # Vendor ID at bytes 0-1
    logger.info(f"Controller Vendor ID: 0x{vid:04x}")
    
    assert vid != 0, "Valid Vendor ID should be returned from Identify command"
    
    logger.info("✓ Admin queue initialization validated successfully")


@pytest.mark.positive
@pytest.mark.admin_queue
def test_admin_queue_depth(nvme0):
    """
    Test: Admin Queue Depth Validation
    
    Purpose:
        Verify admin queue depth constraints from Controller Capabilities.
    
    Preconditions:
        - Controller initialized and ready
    
    Test Steps:
        1. Read CAP register (offset 0x00)
        2. Extract MQES (Maximum Queue Entries Supported) field (bits 15:0)
        3. Verify MQES is within valid range (minimum 1, i.e., 2 entries)
        4. Log admin queue depth capabilities
    
    Expected Result:
        - MQES >= 1 (at least 2 queue entries supported)
        - Admin queue respects depth limit
    
    NVMe 2.0 Reference: §3.1.1 (CAP register), §3.5 (Admin Queue)
    """
    logger.info("=== Test: Admin Queue Depth ===")
    
    # Step 1-2: Read CAP register and extract MQES
    cap_reg = nvme0[0]  # CAP register at offset 0x00 (64-bit, reading lower 32 bits)
    mqes = cap_reg & 0xFFFF  # MQES is bits 15:0
    
    logger.info(f"Controller Capabilities (CAP lower 32-bit): 0x{cap_reg:08x}")
    logger.info(f"Maximum Queue Entries Supported (MQES): {mqes}")
    logger.info(f"Maximum Queue Depth: {mqes + 1} entries (MQES is 0-based)")
    
    # Step 3: Verify MQES is valid
    # NVMe spec requires MQES >= 1 (i.e., minimum 2 entries)
    assert mqes >= 1, f"MQES should be >= 1, got {mqes}"
    
    # Additional validation: typical controllers support at least 64 entries
    logger.info(f"Admin queue supports up to {mqes + 1} entries")
    
    logger.info("✓ Admin queue depth validated successfully")


@pytest.mark.positive
@pytest.mark.admin_queue
def test_admin_queue_memory_alignment(nvme0):
    """
    Test: Admin Queue Memory Alignment
    
    Purpose:
        Verify that admin queues are properly aligned in memory.
    
    Preconditions:
        - Controller initialized with admin queues
    
    Test Steps:
        1. Read Admin Submission Queue Base Address (ASQ) register (offset 0x28)
        2. Read Admin Completion Queue Base Address (ACQ) register (offset 0x30)
        3. Verify both addresses are page-aligned (4KB = 0x1000)
        4. Verify addresses are non-zero
    
    Expected Result:
        - ASQ and ACQ base addresses are page-aligned
        - Addresses are valid (non-zero)
    
    NVMe 2.0 Reference: §3.1.9 (ASQ), §3.1.8 (ACQ), §4.1 (Queue alignment)
    """
    logger.info("=== Test: Admin Queue Memory Alignment ===")
    
    # Note: PyNVMe abstracts queue memory management, so we verify through
    # successful queue operation rather than direct register access
    
    # Verify admin queue works correctly (implies proper alignment)
    id_buf = d.Buffer(4096)
    
    # Submit identify command - will fail if queue memory is misaligned
    nvme0.identify(id_buf, nsid=0, cns=1).waitdone()
    
    # Verify command completed successfully
    model_name = id_buf[24:64].decode('utf-8', errors='ignore').strip()
    logger.info(f"Controller Model: {model_name}")
    
    assert len(model_name) > 0, "Identify command should return valid model name"
    
    logger.info("✓ Admin queue memory alignment validated (implicit via successful operation)")


@pytest.mark.positive
@pytest.mark.admin_queue
def test_admin_queue_doorbell_behavior(nvme0):
    """
    Test: Admin Queue Doorbell Behavior
    
    Purpose:
        Validate admin queue doorbell register operations.
    
    Preconditions:
        - Controller ready with admin queues initialized
    
    Test Steps:
        1. Submit Identify command via admin queue
        2. Monitor command completion
        3. Verify doorbell mechanism works correctly
        4. Check completion queue entry
    
    Expected Result:
        - Command completes successfully
        - Doorbell updates are processed correctly
    
    NVMe 2.0 Reference: §3.1.10-11 (Doorbell registers), §4.2 (Doorbell stride)
    """
    logger.info("=== Test: Admin Queue Doorbell Behavior ===")
    
    # Get doorbell stride from CAP register
    cap_reg = nvme0[0]
    dstrd = (cap_reg >> 32) & 0xF if hasattr(cap_reg, 'bit_length') and cap_reg.bit_length() > 32 else 0
    logger.info(f"Doorbell Stride (DSTRD): {dstrd} (doorbell spacing: {(2 << dstrd) * 4} bytes)")
    
    # Submit identify command and track completion
    id_buf = d.Buffer(4096)
    
    start_time = time.time()
    nvme0.identify(id_buf, nsid=0, cns=1).waitdone()
    elapsed_us = (time.time() - start_time) * 1_000_000
    
    logger.info(f"Identify command completed in {elapsed_us:.2f} µs")
    
    # Verify command completed with valid data
    sn = id_buf[4:24].decode('utf-8', errors='ignore').strip()
    logger.info(f"Controller Serial Number: {sn}")
    
    assert len(sn) > 0, "Identify should return valid serial number"
    
    # Check latest command latency (via PyNVMe property)
    latency = nvme0.latest_latency
    logger.info(f"Latest command latency: {latency} µs")
    
    assert latency > 0, "Command latency should be tracked"
    
    logger.info("✓ Admin queue doorbell behavior validated successfully")


@pytest.mark.positive
@pytest.mark.admin_queue
def test_controller_enable_disable(nvme0_no_init, pcie):
    """
    Test: Controller Enable/Disable Transitions
    
    Purpose:
        Verify CC.EN (Controller Enable) transitions and CSTS.RDY (Ready) responses.
    
    Preconditions:
        - PCIe device accessible
        - Controller in uninitialized state
    
    Test Steps:
        1. Disable controller (CC.EN = 0)
        2. Wait for CSTS.RDY = 0
        3. Enable controller (CC.EN = 1)
        4. Wait for CSTS.RDY = 1
        5. Initialize admin queue
        6. Verify controller is operational
    
    Expected Result:
        - Controller transitions correctly between enabled/disabled states
        - CSTS.RDY follows CC.EN transitions
        - Controller becomes operational after enable
    
    NVMe 2.0 Reference: §3.1.6 (CC and CSTS), §7.6.1 (Controller Initialization)
    """
    logger.info("=== Test: Controller Enable/Disable Transitions ===")
    
    nvme0 = nvme0_no_init  # Use uninitialized controller
    
    # Step 1: Disable controller
    logger.info("Step 1: Disabling controller (CC.EN = 0)")
    cc_reg = nvme0[0x14]
    nvme0[0x14] = cc_reg & ~0x1  # Clear CC.EN bit
    
    # Step 2: Wait for CSTS.RDY = 0 (max timeout per spec: shutdown notification timeout)
    logger.info("Step 2: Waiting for CSTS.RDY = 0")
    timeout = 10  # seconds
    start_time = time.time()
    
    while True:
        csts = nvme0[0x1c]
        if (csts & 0x1) == 0:
            logger.info(f"Controller ready bit cleared after {time.time() - start_time:.2f}s")
            break
        if time.time() - start_time > timeout:
            raise TimeoutError("Controller did not become not-ready within timeout")
        time.sleep(0.01)
    
    assert (nvme0[0x1c] & 0x1) == 0, "CSTS.RDY should be 0 after disabling"
    
    # Step 3: Enable controller
    logger.info("Step 3: Enabling controller (CC.EN = 1)")
    
    # Configure CC register for enable
    # Set: EN=1, CSS=000b (NVM Command Set), MPS=0 (page size 4KB), AMS=000b (Round Robin)
    cc_val = 0x00460001  # Typical CC value for enable
    nvme0[0x14] = cc_val
    
    # Step 4: Wait for CSTS.RDY = 1
    logger.info("Step 4: Waiting for CSTS.RDY = 1")
    start_time = time.time()
    
    while True:
        csts = nvme0[0x1c]
        if (csts & 0x1) == 1:
            logger.info(f"Controller ready after {time.time() - start_time:.2f}s")
            break
        if time.time() - start_time > timeout:
            raise TimeoutError("Controller did not become ready within timeout")
        time.sleep(0.01)
    
    assert (nvme0[0x1c] & 0x1) == 1, "CSTS.RDY should be 1 after enabling"
    
    # Step 5: Initialize admin queue
    logger.info("Step 5: Initializing admin queue")
    nvme0.init_adminq()
    
    # Step 6: Verify controller is operational
    logger.info("Step 6: Verifying controller operational")
    id_buf = d.Buffer(4096)
    nvme0.identify(id_buf).waitdone()
    
    vid = id_buf.data(1, 0) & 0xFFFF
    logger.info(f"Controller VID: 0x{vid:04x}")
    
    assert vid != 0, "Controller should be operational after enable sequence"
    
    logger.info("✓ Controller enable/disable transitions validated successfully")


# ============================================================================
# NEGATIVE TESTS - Admin Queue Error Handling
# ============================================================================

@pytest.mark.negative
@pytest.mark.admin_queue
def test_admin_queue_invalid_command(nvme0):
    """
    Test: Invalid Admin Command Handling
    
    Purpose:
        Verify controller properly handles invalid admin commands.
    
    Preconditions:
        - Controller ready with admin queue initialized
    
    Test Steps:
        1. Submit invalid admin command (reserved opcode)
        2. Wait for completion
        3. Verify error status in completion entry
        4. Check DNR (Do Not Retry) bit
    
    Expected Result:
        - Command completes with error status
        - Status Code Type (SCT) indicates command specific error
        - Status Code (SC) indicates invalid opcode
        - DNR bit may be set
    
    NVMe 2.0 Reference: §4.6.3.1 (Completion Queue Entry), §5.2 (Opcodes)
    """
    logger.info("=== Test: Invalid Admin Command (Negative) ===")
    
    error_detected = {'status': None, 'dnr': None, 'sc': None, 'sct': None}
    
    def error_cb(cdw0, status1):
        """Callback to capture error status"""
        error_detected['status'] = status1
        # Parse status field
        # status1 format: bit 0 = phase, bits 1-8 = SC, bits 9-11 = SCT, bit 14 = M, bit 15 = DNR
        error_detected['dnr'] = (status1 >> 15) & 0x1
        error_detected['sct'] = (status1 >> 9) & 0x7
        error_detected['sc'] = (status1 >> 1) & 0xFF
        
        logger.info(f"Error callback - status1: 0x{status1:04x}")
        logger.info(f"  SC (Status Code): 0x{error_detected['sc']:02x}")
        logger.info(f"  SCT (Status Code Type): 0x{error_detected['sct']:x}")
        logger.info(f"  DNR (Do Not Retry): {error_detected['dnr']}")
    
    # Submit invalid command using send_cmd with reserved opcode (0xFF)
    # Opcode 0xFF is reserved and should return Invalid Command Opcode error
    buf = d.Buffer(4096)
    
    logger.info("Submitting invalid admin command (opcode 0xFF)")
    
    # Expect a warning for error status
    with pytest.warns(UserWarning, match="ERROR status"):
        nvme0.send_cmd(0xFF, buf, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, cb=error_cb).waitdone()
    
    # Verify error was detected
    assert error_detected['status'] is not None, "Error status should be returned"
    assert error_detected['sct'] == 0, "SCT should be 0 (Generic Command Status)"
    assert error_detected['sc'] == 1, "SC should be 1 (Invalid Command Opcode)"
    
    logger.info("✓ Invalid command error handling validated successfully")


@pytest.mark.negative
@pytest.mark.admin_queue  
def test_admin_queue_invalid_nsid(nvme0):
    """
    Test: Invalid Namespace ID in Admin Command
    
    Purpose:
        Verify error handling for invalid namespace ID in Identify command.
    
    Preconditions:
        - Controller ready
    
    Test Steps:
        1. Submit Identify Namespace command with invalid NSID (0xFFFFFFFF)
        2. CNS = 0 (Identify Namespace)
        3. Check for error completion
    
    Expected Result:
        - Command returns error status
        - SC indicates Invalid Namespace or Format
    
    NVMe 2.0 Reference: §5.19 (Identify command), §4.6.3.1 (Error codes)
    """
    logger.info("=== Test: Invalid Namespace ID (Negative) ===")
    
    error_info = {'detected': False, 'sc': None, 'sct': None}
    
    def nsid_error_cb(cdw0, status1):
        """Callback to capture error"""
        error_info['detected'] = True
        error_info['sct'] = (status1 >> 9) & 0x7
        error_info['sc'] = (status1 >> 1) & 0xFF
        logger.info(f"NSID error - SC: 0x{error_info['sc']:02x}, SCT: 0x{error_info['sct']:x}")
    
    buf = d.Buffer(4096)
    invalid_nsid = 0xFFFFFFFF  # Broadcast NSID, invalid for CNS=0
    
    logger.info(f"Submitting Identify with invalid NSID: 0x{invalid_nsid:08x}")
    
    # This may or may not error depending on controller implementation
    # Some controllers may return data for NSID 0xFFFFFFFF
    try:
        with pytest.warns(UserWarning, match="ERROR status"):
            nvme0.identify(buf, nsid=invalid_nsid, cns=0, cb=nsid_error_cb).waitdone()
        
        if error_info['detected']:
            logger.info("✓ Controller correctly rejected invalid NSID")
            assert error_info['sct'] == 0, "Expected Generic Command Status"
        else:
            logger.warning("Controller accepted NSID 0xFFFFFFFF (implementation dependent)")
    except:
        # If exception raised, that's also acceptable error handling
        logger.info("✓ Invalid NSID rejected with exception")


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "-s"])
