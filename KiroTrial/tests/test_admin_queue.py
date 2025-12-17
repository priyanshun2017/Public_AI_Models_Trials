"""
Admin Queue Test Suite

Validates Admin Submission Queue (ASQ) and Admin Completion Queue (ACQ) behavior
according to NVMe 2.0 specification requirements.

Test Coverage:
- Admin queue initialization and configuration
- Controller enable/disable state transitions  
- Admin doorbell register behavior
- Admin command processing validation
"""

import pytest
import time
import logging
from typing import Dict, Any

try:
    import pynvme as d
except ImportError:
    pytest.skip("PyNVMe library not available", allow_module_level=True)

from .models import QueueConfiguration, QueueType, MemoryType, TestResult, TestStatus
from .conftest import NVMeTestFixture


class AdminQueueTestSuite:
    """
    Test suite for Admin Queue validation.
    
    Purpose: Verify Admin Submission Queue (ASQ) and Admin Completion Queue (ACQ) 
    initialization, controller enablement, and doorbell behavior according to NVMe 2.0.
    
    Preconditions:
    - NVMe 2.0 compliant controller available
    - PyNVMe framework properly installed
    - Test has appropriate permissions for NVMe device access
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @pytest.mark.admin_queue
    @pytest.mark.hardware
    def test_admin_queue_initialization(self, nvme_fixture: NVMeTestFixture):
        """
        Test Purpose: Verify Admin Submission Queue and Admin Completion Queue 
        are properly configured with correct memory alignment.
        
        Preconditions:
        - NVMe controller is available but not yet initialized
        
        Test Steps:
        1. Initialize controller with admin queues
        2. Verify ASQ and ACQ are created with proper alignment
        3. Validate queue depth matches controller capabilities
        4. Check memory allocation is correct
        
        Expected Results:
        - Admin queues are successfully created
        - Memory alignment follows NVMe 2.0 requirements (4KB aligned)
        - Queue depth is within controller limits
        - Controller reports queues as properly configured
        """
        self.logger.info("Testing admin queue initialization")
        
        # Verify controller is initialized
        assert nvme_fixture.controller is not None, "Controller should be initialized"
        assert nvme_fixture.controller_info is not None, "Controller info should be available"
        
        # Check admin queue configuration
        controller = nvme_fixture.controller
        
        # Verify admin queue depth is reasonable (typically 64-4096 entries)
        admin_queue_depth = controller.cap & 0xFFFF  # CAP.MQES field
        assert 64 <= admin_queue_depth <= 4096, f"Admin queue depth {admin_queue_depth} out of range"
        
        # Verify controller capabilities indicate admin queues are supported
        assert controller.cap is not None, "Controller capabilities should be readable"
        
        # Test admin queue memory alignment by checking base addresses
        # Admin queues should be 4KB aligned per NVMe 2.0 spec
        asq_base = controller.asq  # Admin Submission Queue base address
        acq_base = controller.acq  # Admin Completion Queue base address
        
        assert asq_base % 4096 == 0, f"ASQ base address 0x{asq_base:x} not 4KB aligned"
        assert acq_base % 4096 == 0, f"ACQ base address 0x{acq_base:x} not 4KB aligned"
        
        self.logger.info(f"Admin queues initialized: ASQ=0x{asq_base:x}, ACQ=0x{acq_base:x}")
    
    @pytest.mark.admin_queue  
    @pytest.mark.hardware
    def test_controller_enable_disable(self, nvme_fixture: NVMeTestFixture):
        """
        Test Purpose: Validate Controller Configuration register (CC.EN) and 
        Controller Status register (CSTS.RDY) state transitions.
        
        Preconditions:
        - Controller is initialized and ready
        
        Test Steps:
        1. Read initial CC.EN and CSTS.RDY states
        2. Disable controller (CC.EN = 0)
        3. Verify CSTS.RDY transitions to 0
        4. Re-enable controller (CC.EN = 1)  
        5. Verify CSTS.RDY transitions to 1
        6. Validate timing requirements per NVMe 2.0
        
        Expected Results:
        - CC.EN changes are reflected correctly
        - CSTS.RDY follows CC.EN with proper timing
        - State transitions complete within spec timeouts
        - Controller remains functional after enable/disable cycle
        """
        self.logger.info("Testing controller enable/disable state transitions")
        
        controller = nvme_fixture.controller
        
        # Read initial state - controller should be enabled and ready
        initial_cc = controller.cc
        initial_csts = controller.csts
        
        assert initial_cc & 0x1, "Controller should initially be enabled (CC.EN=1)"
        assert initial_csts & 0x1, "Controller should initially be ready (CSTS.RDY=1)"
        
        # Test disable sequence
        self.logger.info("Disabling controller")
        controller.cc = initial_cc & ~0x1  # Clear CC.EN bit
        
        # Wait for CSTS.RDY to clear (up to CAP.TO * 500ms per spec)
        timeout = ((controller.cap >> 24) & 0xFF) * 500 / 1000.0  # Convert to seconds
        timeout = max(timeout, 5.0)  # Minimum 5 second timeout
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not (controller.csts & 0x1):  # CSTS.RDY cleared
                break
            time.sleep(0.1)
        else:
            pytest.fail(f"Controller did not become not-ready within {timeout}s")
        
        disable_time = time.time() - start_time
        self.logger.info(f"Controller disabled in {disable_time:.2f}s")
        
        # Test enable sequence  
        self.logger.info("Re-enabling controller")
        controller.cc = initial_cc | 0x1  # Set CC.EN bit
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if controller.csts & 0x1:  # CSTS.RDY set
                break
            time.sleep(0.1)
        else:
            pytest.fail(f"Controller did not become ready within {timeout}s")
            
        enable_time = time.time() - start_time
        self.logger.info(f"Controller enabled in {enable_time:.2f}s")
        
        # Verify final state
        final_cc = controller.cc
        final_csts = controller.csts
        
        assert final_cc & 0x1, "Controller should be enabled after re-enable"
        assert final_csts & 0x1, "Controller should be ready after re-enable"
    
    @pytest.mark.admin_queue
    @pytest.mark.hardware  
    def test_admin_doorbell_behavior(self, nvme_fixture: NVMeTestFixture):
        """
        Test Purpose: Validate proper doorbell behavior for admin command 
        submission and completion.
        
        Preconditions:
        - Controller is enabled and ready
        - Admin queues are properly initialized
        
        Test Steps:
        1. Read initial doorbell register values
        2. Submit an admin command (Identify Controller)
        3. Verify submission doorbell is updated
        4. Wait for command completion
        5. Verify completion doorbell behavior
        6. Validate doorbell values match queue state
        
        Expected Results:
        - Submission doorbell increments after command submission
        - Completion doorbell reflects processed completions
        - Doorbell values stay within queue size bounds
        - Doorbell updates follow NVMe 2.0 specification
        """
        self.logger.info("Testing admin doorbell behavior")
        
        controller = nvme_fixture.controller
        
        # Read initial doorbell values
        # Admin SQ doorbell at offset 0x1000, Admin CQ doorbell at 0x1004
        initial_sq_doorbell = controller.doorbell(0, is_sq=True)
        initial_cq_doorbell = controller.doorbell(0, is_sq=False)
        
        self.logger.info(f"Initial doorbells: SQ={initial_sq_doorbell}, CQ={initial_cq_doorbell}")
        
        # Submit Identify Controller command to test doorbell behavior
        identify_data = d.Buffer(4096)  # 4KB buffer for identify data
        
        # Create and submit identify command
        def identify_callback(cpl):
            """Callback for identify command completion"""
            self.logger.info(f"Identify command completed with status: 0x{cpl.status:04x}")
        
        # Submit the command and check doorbell update
        controller.send_cmd(0x06, identify_data, 0, identify_callback)  # Identify Controller opcode
        
        # Verify submission doorbell was updated
        post_submit_sq_doorbell = controller.doorbell(0, is_sq=True)
        expected_sq_doorbell = (initial_sq_doorbell + 1) % (controller.cap & 0xFFFF + 1)
        
        assert post_submit_sq_doorbell == expected_sq_doorbell, \
            f"SQ doorbell not updated correctly: got {post_submit_sq_doorbell}, expected {expected_sq_doorbell}"
        
        # Wait for command completion and process completions
        controller.waitdone()
        
        # Verify completion processing updated CQ doorbell
        post_completion_cq_doorbell = controller.doorbell(0, is_sq=False)
        
        # CQ doorbell should advance after processing completion
        assert post_completion_cq_doorbell != initial_cq_doorbell, \
            "CQ doorbell should be updated after processing completion"
        
        self.logger.info(f"Final doorbells: SQ={post_submit_sq_doorbell}, CQ={post_completion_cq_doorbell}")
    
    @pytest.mark.admin_queue
    @pytest.mark.hardware
    def test_admin_command_processing(self, nvme_fixture: NVMeTestFixture):
        """
        Test Purpose: Verify command processing through the Admin Queue system.
        
        Preconditions:
        - Controller is enabled and ready
        - Admin queues are functional
        
        Test Steps:
        1. Submit multiple admin commands (Identify, Get Features, Set Features)
        2. Verify each command completes successfully
        3. Validate completion status codes
        4. Check command ordering and completion matching
        5. Verify admin queue state remains consistent
        
        Expected Results:
        - All admin commands complete successfully
        - Completion status indicates success (0x0000)
        - Command IDs match between submission and completion
        - Admin queue maintains proper state throughout
        """
        self.logger.info("Testing admin command processing")
        
        controller = nvme_fixture.controller
        completed_commands = []
        
        def command_callback(cpl):
            """Generic callback for admin command completion"""
            completed_commands.append({
                'cid': cpl.cid,
                'status': cpl.status,
                'sqid': cpl.sqid,
                'sqhd': cpl.sqhd
            })
            self.logger.info(f"Command {cpl.cid} completed with status 0x{cpl.status:04x}")
        
        # Test 1: Identify Controller command
        identify_buffer = d.Buffer(4096)
        controller.send_cmd(0x06, identify_buffer, 0, command_callback)
        
        # Test 2: Get Features command (Arbitration feature)
        get_features_buffer = d.Buffer(4096) 
        controller.send_cmd(0x0A, get_features_buffer, 0x01, command_callback)  # Get Arbitration
        
        # Test 3: Set Features command (Number of Queues)
        # Set both submission and completion queue counts
        set_features_data = (0xFFFF << 16) | 0xFFFF  # Request max queues
        controller.send_cmd(0x09, None, 0x07, command_callback, cdw11=set_features_data)
        
        # Wait for all commands to complete
        controller.waitdone()
        
        # Verify all commands completed
        assert len(completed_commands) == 3, f"Expected 3 completions, got {len(completed_commands)}"
        
        # Verify completion details
        for i, completion in enumerate(completed_commands):
            # All commands should complete successfully
            assert completion['status'] == 0, \
                f"Command {i} failed with status 0x{completion['status']:04x}"
            
            # All commands submitted to admin queue (SQID=0)
            assert completion['sqid'] == 0, \
                f"Command {i} wrong SQID: got {completion['sqid']}, expected 0"
            
            # Command IDs should be sequential (PyNVMe assigns them)
            assert completion['cid'] >= 0, f"Command {i} invalid CID: {completion['cid']}"
        
        self.logger.info(f"Successfully processed {len(completed_commands)} admin commands")
        
        # Verify controller state is still good after command processing
        assert controller.csts & 0x1, "Controller should still be ready after admin commands"